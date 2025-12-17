from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

from .http_api import HttpApi, health_payload
from .llm_client import LlmClient, load_llm_config_from_env
from .log_follow import follow_json_lines
from .pipeline import Pipeline, PipelineConfig


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def main() -> int:
    start_time = time.time()

    log_path = Path(os.getenv("WAZUH_ARCHIVES_PATH", "/wazuh-logs/archives/archives.json"))
    state_path = Path(os.getenv("AI_STATE_PATH", "/data/state.json"))
    findings_path = Path(os.getenv("AI_FINDINGS_PATH", "/data/findings.jsonl"))
    start_at_end = os.getenv("AI_START_AT_END", "true").lower() in ("1", "true", "yes")

    cfg = PipelineConfig(
        min_rule_level=_env_int("AI_MIN_RULE_LEVEL", 7),
        max_batch=_env_int("AI_MAX_BATCH", 1),
        max_batch_delay_s=_env_float("AI_MAX_BATCH_DELAY_S", 0.0),
        findings_path=findings_path,
    )

    llm = LlmClient(load_llm_config_from_env())
    pipeline = Pipeline(config=cfg, llm=llm)

    api_host = os.getenv("AI_HTTP_HOST", "0.0.0.0")
    api_port = _env_int("AI_HTTP_PORT", 8088)
    api = HttpApi(host=api_host, port=api_port)

    api.start(
        routes={
            "/health": lambda: health_payload(start_time),
            "/stats": pipeline.stats,
            "/findings": lambda: {"ok": True, "items": pipeline.recent_findings(limit=_env_int("AI_FINDINGS_LIMIT", 50))},
        }
    )

    stopping = False

    def _stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    print(
        f"[ai-agent] starting: archives={log_path} findings={findings_path} llm_enabled={llm.enabled()}",
        flush=True,
    )

    try:
        for event in follow_json_lines(
            log_path=log_path,
            state_path=state_path,
            poll_s=_env_float("AI_POLL_S", 0.5),
            start_at_end=start_at_end,
        ):
            if stopping:
                break
            pipeline.process_event(event)
    finally:
        api.stop()

    print("[ai-agent] stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

