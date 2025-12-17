# AI Agent (Collector → Filter → Prompt → Output)

This service tails Wazuh `archives.json` (JSONL), filters suspicious events, optionally sends them to an LLM for triage, and writes findings to a JSONL file.

## Pre-flight Checklist (before `docker compose up`)

### 1) Wazuh is actually writing `archives.json`

The agent reads **Wazuh Manager archives** (not Wazuh alerts). You must ensure archives logging is enabled and producing JSON.

- Check the file exists inside Wazuh Manager:
  - `docker exec -it wazuh.master sh -lc "ls -lah /var/ossec/logs/archives/archives.json"`
- Check it is receiving new events:
  - `docker exec -it wazuh.master sh -lc "tail -n 3 /var/ossec/logs/archives/archives.json"`
  - Generate a test event (e.g. browse DVWA/Juice Shop via Nginx-love) and re-run the `tail` command.
- If the file does not exist or stays empty:
  - Enable archives JSON in Wazuh config (commonly in `ossec.conf`):
    - `<logall>yes</logall>`
    - `<logall_json>yes</logall_json>`
  - Restart Wazuh Manager after changing config.

### 2) The path mounted into `ai-agent` matches what Wazuh writes

This compose setup mounts `master-wazuh-logs` to `/wazuh-logs` in `ai-agent` (read-only).

- Confirm the agent path matches:
  - Default: `WAZUH_ARCHIVES_PATH=/wazuh-logs/archives/archives.json`
- Verify the file is visible from `ai-agent` container:
  - `docker exec -it ai-agent sh -lc "ls -lah /wazuh-logs/archives/archives.json && tail -n 2 /wazuh-logs/archives/archives.json"`

### 3) Make sure `ai-agent` can persist state + findings

The agent writes:
- cursor/state: `/data/state.json`
- findings JSONL: `/data/findings.jsonl`

Checklist:
- `./logs/ai-agent` exists (Docker will usually create it automatically, but pre-creating avoids permission surprises on some hosts).
- Confirm output after running for a bit:
  - `Get-Content -Tail 5 .\\logs\\ai-agent\\findings.jsonl`

### 4) Filter settings are reasonable (avoid flooding)

- Start with defaults:
  - `AI_MIN_RULE_LEVEL=7`
  - `AI_START_AT_END=true` (avoids ingesting your entire historical archives on first boot)
- If you see no findings, lower `AI_MIN_RULE_LEVEL` (e.g. 3–5).
- If you see too many findings, raise it (e.g. 10–12).

### 5) LLM is optional, but if enabled you must configure it

By default the agent runs **heuristics only** (`AI_PROVIDER=none`) and does not call any external API.

To enable LLM calls:
- Set `AI_PROVIDER=openai_compatible`
- Set `AI_API_BASE` (example: `https://api.openai.com`)
- Set `AI_API_KEY` (must be non-empty)
- Set `AI_MODEL`

Then verify the agent reports `llm_enabled=true`:
- `curl http://localhost:8088/stats`

### 6) Port availability

- `ai-agent` exposes `8088` on the host. Ensure nothing else is using it, or change the mapping in `docker-compose.yml`.

## Data Flow

- **Collector**: follows `WAZUH_ARCHIVES_PATH`
- **Filter**: `AI_MIN_RULE_LEVEL` + heuristics (ModSecurity/web tokens)
- **Prompt**: requests JSON-only assessment (no numeric score)
- **Output**: appends JSONL to `AI_FINDINGS_PATH` and exposes an HTTP API

## HTTP Endpoints

- `GET /health`
- `GET /stats`
- `GET /findings`

## Environment Variables

- `WAZUH_ARCHIVES_PATH` (default: `/wazuh-logs/archives/archives.json`)
- `AI_MIN_RULE_LEVEL` (default: `7`)
- `AI_FINDINGS_PATH` (default: `/data/findings.jsonl`)
- `AI_STATE_PATH` (default: `/data/state.json`)
- `AI_START_AT_END` (default: `true`)
- `AI_PROVIDER` (default: `none`) set to `openai_compatible` to enable LLM calls
- `AI_API_BASE` (default: `http://localhost:11434`) OpenAI-compatible base URL
- `AI_API_KEY` (default: empty) required to enable LLM calls
- `AI_MODEL` (default: `gpt-4o-mini`)
