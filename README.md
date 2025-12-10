AI Contract Reviewer + Data Validator Agent System

Overview

A local, multi-agent, MCP-powered contract intelligence platform that extracts, validates, corrects, and summarizes contracts and invoices with full auditability and enterprise integration.

Hackathon deliverable

- Upload a contract PDF → extract structured data (clauses, amounts, parties, dates)
- Run validation rules → show issues and suggested corrections
- Produce a JSON payload + summary PDF and show MCP tool call logs
- Multi-agent collaboration view (debate / correction messages)

Folder layout

- `backend/` FastAPI service and upload endpoint
- `mcp/` MCP tool stubs (executable, auditable tools)
- `agents/` agent responsibilities and prompts
- `frontend/` UI placeholder and notes
- `docs/` architecture and design rationale
- `demo/` demo script and run instructions

Next steps

Run `python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt` then start the backend and try the demo curl upload.