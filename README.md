# AI Contract Reviewer + Data Validator Agent System

## Overview

A local, multi-agent, MCP-powered contract intelligence platform that extracts, validates, corrects, and summarizes contracts and invoices with full auditability and enterprise integration.

**Pivoted for hackathon:** Edge AI Compliance Monitor for Enterprise Video Streams — detects safety violations in video frames, logs events to an append-only audit trail, and generates compliance reports with visual evidence.

## Hackathon Deliverable

- Upload a contract PDF or compliance video → extract structured data or detect violations
- Run validation rules → show issues, explanations, and corrective actions
- Produce a JSON payload + summary PDF and show MCP tool call logs
- Full audit trail via append-only JSONL log (viewable at `/audits` endpoint)
- Async job API with status polling and result retrieval

## 🚀 Quick Start (One-Liner for Judges)

```bash
# Clone, build, and run everything in one command:
docker-compose up --build
```

Then:
- **API Docs:** http://localhost:8000/docs
- **Backend Health:** http://localhost:8000/health
- **MCP Tools:** http://localhost:8001 (run_tool, audits endpoints)
- **Streamlit UI:** http://localhost:8501 (file upload, job polling, report download)
- **Sample Audit Logs:** `curl http://localhost:8001/audits | jq`

## Manual Setup (No Docker)

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Generate sample video and PDF
python demo/create_sample_video.py demo/sample.mp4
python demo/create_sample_pdf.py demo/sample.pdf

# 4. Start MCP server (in one terminal)
PYTHONPATH=. python3 -m uvicorn mcp.server:app --port 8001

# 5. Start backend (in another terminal)
PYTHONPATH=. python3 -m uvicorn backend.main:app --port 8000 --reload

# 6. Start Streamlit UI (optional, in a third terminal)
streamlit run frontend/streamlit_app.py

# 7. Upload test video
curl -X POST http://127.0.0.1:8000/upload -F "file=@demo/sample.mp4"
```

## Features

### Video Pipeline
- **Frame Decoding:** Robust sampling from MP4 videos with configurable max frames
- **Detection:** Optional ONNX/YOLOv8 integration (falls back to deterministic demo if model absent)
- **Reasoning:** VLM-style analysis of detected violations (severity, context, risk)
- **Rule Lookup:** Compliance rule mapping and enforcement status
- **Event Logging:** Append-only audit log for all detections and tool calls
- **PDF Reporting:** Multi-page report with thumbnails, bounding boxes, and summaries

### Async API
- `POST /upload_async` — submit file, get job_id
- `GET /status/{job_id}` — poll job progress
- `GET /result/{job_id}` — fetch results JSON + PDF path
- `GET /download_file?path=...` — download report PDF

### Audit Trail
- Every MCP tool call logged to `mcp/audit.log` with timestamp and parameters
- Viewable at `GET /audits` (JSON endpoint)
- Append-only JSONL format (immutable, tamper-evident)

## Folder Layout

- `backend/` — FastAPI service, async job API, file upload/download endpoints
- `mcp/` — MCP tool implementations (video, text, compliance rules) + audit store
- `agents/` — Orchestrator (calls MCP tools in sequence), prompts, sample runners
- `frontend/` — Streamlit UI for file upload and job polling
- `demo/` — Sample data generators (video, PDF) and demo reports
- `docs/` — Architecture and design documents
- `docker-compose.yml` — One-command deploy (services: MCP, backend, Streamlit)
- `Dockerfile.*` — Individual service containers (MCP, backend, Streamlit)

## Testing & Validation

✅ All four requirements completed and smoke-tested:
1. **ONNX/YOLOv8 detector integration** — optional via `models/yolov8n.onnx`; falls back to deterministic demo
2. **Async pipeline with status endpoints** — `/upload_async`, `/status/{job_id}`, `/result/{job_id}`
3. **Streamlit UI** — file upload, job polling, report download
4. **Enhanced PDF reports** — thumbnails with drawn bounding boxes, per-event summaries

**End-to-end test result:** Upload sample video → detect 6 violations → generate compliance report PDF → download

## Architecture Highlights

- **MCP Tool Layer:** Modular, independently testable tools with HTTP execution
- **Append-Only Audit:** Immutable event log; all tool calls captured with timestamps
- **Orchestrator Pattern:** Sequential tool composition (detect → reason → lookup → log)
- **Local-First:** Runs entirely on-premise; no cloud dependencies
- **Deterministic Fallback:** Demo detection patterns ensure consistent behavior without model weights

## Sample API Calls

### Synchronous Upload (blocking)
```bash
curl -X POST http://127.0.0.1:8000/upload \
  -F "file=@demo/sample.mp4" | jq
```

### Async Upload → Status → Download
```bash
# 1. Submit job
JOB_ID=$(curl -s -X POST http://127.0.0.1:8000/upload_async \
  -F "file=@demo/sample.mp4" | jq -r '.job_id')

# 2. Poll status
curl http://127.0.0.1:8000/status/$JOB_ID | jq

# 3. Get result
RESULT=$(curl http://127.0.0.1:8000/result/$JOB_ID | jq)

# 4. Download report PDF
PDF_PATH=$(echo $RESULT | jq -r '.result.report_pdf')
curl -o report.pdf "http://127.0.0.1:8000/download_file?path=$PDF_PATH"
```

### View Audit Log
```bash
curl http://127.0.0.1:8001/audits | jq '.audits[-5:]'  # last 5 entries
```

## Next Steps (Optional Improvements)

- Download + integrate real YOLOv8 model weights (ONNX)
- Persist job store (Redis/PostgreSQL) for durability
- Add authentication/authorization (JWT tokens, signed downloads)
- Hardware acceleration (GB10 ONNX Runtime, vendor-specific libraries)
- Extended compliance rule library (OSHA, CSA, custom)

## License

MIT (Example only — adjust as needed)

---

**Questions or issues?** Open an issue or check `docs/ARCHITECTURE.md` for system design details.
