# AI Agent (Collector → Filter → Prompt → Output)

This service tails Wazuh `archives.json` (JSONL), filters suspicious events, optionally sends them to an LLM for triage, and writes findings to a JSONL file.

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

