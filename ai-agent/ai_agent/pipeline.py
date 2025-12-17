from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm_client import LlmClient


@dataclass(frozen=True)
class PipelineConfig:
    min_rule_level: int
    max_batch: int
    max_batch_delay_s: float
    findings_path: Path


SUSPICIOUS_TOKENS = [
    r"(?i)\bunion\b\s+\bselect\b",
    r"(?i)\bselect\b.+\bfrom\b",
    r"(?i)\bor\b\s+1=1\b",
    r"(?i)<script\b",
    r"(?i)\bjavascript:",
    r"(?i)\b(onerror|onload)\s*=",
    r"(?i)\.\./",
    r"(?i)\b/etc/passwd\b",
    r"(?i)\b(cmd=|command=)\b",
    r"(?i)\b(;|\\|\\||&&)\b",
    r"(?i)\b(base64|powershell|wget|curl)\b",
]
SUSPICIOUS_RE = re.compile("|".join(SUSPICIOUS_TOKENS))


def _get_rule_level(event: dict[str, Any]) -> int:
    try:
        return int((event.get("rule") or {}).get("level") or 0)
    except Exception:
        return 0


def _get_text_blob(event: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("full_log", "message", "data"):
        val = event.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, dict):
            try:
                parts.append(json.dumps(val, ensure_ascii=False))
            except Exception:
                continue
    return "\n".join(parts)


def should_analyze(event: dict[str, Any], min_rule_level: int) -> tuple[bool, str]:
    level = _get_rule_level(event)
    if level >= min_rule_level:
        return True, f"rule.level={level}>=min={min_rule_level}"

    decoder = (event.get("decoder") or {}).get("name")
    if isinstance(decoder, str) and "modsecurity" in decoder.lower():
        return True, "decoder=modsecurity"

    rule_groups = (event.get("rule") or {}).get("groups") or []
    if isinstance(rule_groups, list) and any(
        isinstance(g, str) and g.lower() in ("web", "attack", "ids", "pci_dss") for g in rule_groups
    ):
        return True, "rule.groups contains web/attack"

    blob = _get_text_blob(event)
    if blob and SUSPICIOUS_RE.search(blob):
        return True, "suspicious_token_match"

    return False, "filtered_out"


def build_prompt(event: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You are a SOC analyst agent for a cyber range. "
        "Analyze a single Wazuh event (JSON) and decide if it is normal or suspicious. "
        "Do NOT give a numeric score. "
        "Return ONLY a JSON object with keys: "
        "verdict(one of: normal,suspicious), "
        "summary(short), "
        "evidence(array of strings, quote suspicious snippets or fields), "
        "suspected_attack_type(one of: sqli,xss,file_upload,path_traversal,command_injection,auth_bruteforce,scanning,unknown), "
        "recommended_actions(array of strings), "
        "recommended_wazuh_hunt(array of strings)."
    )
    user = "Event JSON:\n" + json.dumps(event, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def heuristic_assessment(event: dict[str, Any]) -> dict[str, Any]:
    blob = _get_text_blob(event)
    match = SUSPICIOUS_RE.search(blob or "")
    level = _get_rule_level(event)

    verdict = "suspicious" if match or level >= 10 else "normal"
    evidence: list[str] = []
    if match:
        evidence.append(f"matched_pattern={match.group(0)[:80]}")
    if level:
        evidence.append(f"rule.level={level}")

    return {
        "verdict": verdict,
        "summary": "Heuristic triage (no LLM configured).",
        "evidence": evidence[:5],
        "suspected_attack_type": "unknown" if verdict == "normal" else "unknown",
        "recommended_actions": [
            "Verify source IP and requested URI in web logs.",
            "Correlate with ModSecurity audit logs if available.",
            "Review Wazuh rule and decoder details for false positives.",
        ]
        if verdict == "suspicious"
        else [],
        "recommended_wazuh_hunt": [
            "Search last 15m for same srcip and similar rule.id.",
            "Pivot on user agent and requested URL parameters.",
        ]
        if verdict == "suspicious"
        else [],
        "_meta": {"provider": "heuristic", "model": "none"},
    }


def write_finding(findings_path: Path, finding: dict[str, Any]) -> None:
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    with findings_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")


def build_finding(event: dict[str, Any], assessment: dict[str, Any], reason: str) -> dict[str, Any]:
    ts = event.get("timestamp")
    if not isinstance(ts, str):
        ts = datetime.now(timezone.utc).isoformat()

    rule = event.get("rule") or {}
    return {
        "timestamp": ts,
        "reason": reason,
        "rule": {
            "id": rule.get("id"),
            "level": (rule.get("level") if isinstance(rule, dict) else None),
            "description": (rule.get("description") if isinstance(rule, dict) else None),
            "groups": (rule.get("groups") if isinstance(rule, dict) else None),
        },
        "agent": event.get("agent"),
        "manager": event.get("manager"),
        "decoder": event.get("decoder"),
        "location": event.get("location"),
        "assessment": assessment,
        "event_excerpt": {
            "full_log": (event.get("full_log")[:2000] if isinstance(event.get("full_log"), str) else None),
            "data": event.get("data"),
        },
    }


class Pipeline:
    def __init__(self, config: PipelineConfig, llm: LlmClient) -> None:
        self._cfg = config
        self._llm = llm
        self._recent: list[dict[str, Any]] = []
        self._recent_max = 200
        self._last_finding_ts = 0.0

    def recent_findings(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        return list(self._recent[-limit:])

    def stats(self) -> dict[str, Any]:
        return {
            "min_rule_level": self._cfg.min_rule_level,
            "findings_path": str(self._cfg.findings_path),
            "llm_enabled": self._llm.enabled(),
            "recent_count": len(self._recent),
            "last_finding_ago_s": int(time.time() - self._last_finding_ts) if self._last_finding_ts else None,
        }

    def process_event(self, event: dict[str, Any]) -> None:
        ok, reason = should_analyze(event, min_rule_level=self._cfg.min_rule_level)
        if not ok:
            return

        if self._llm.enabled():
            messages = build_prompt(event)
            try:
                assessment = self._llm.chat_json(messages=messages, temperature=0.0)
            except Exception as exc:
                assessment = {"verdict": "unknown", "summary": f"LLM error: {exc}", "evidence": [], "_meta": {"provider": "error"}}
        else:
            assessment = heuristic_assessment(event)

        finding = build_finding(event=event, assessment=assessment, reason=reason)
        write_finding(self._cfg.findings_path, finding)

        self._recent.append(finding)
        if len(self._recent) > self._recent_max:
            self._recent = self._recent[-self._recent_max :]
        self._last_finding_ts = time.time()

