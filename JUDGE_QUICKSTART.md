# Judge Quick Start Guide

## What This Is

An **on-premise, MCP-powered multi-agent compliance monitoring system** that detects safety violations in video streams, logs all decisions to an append-only audit trail, and generates compliance reports with visual evidence.

**Time to demo: ~2 minutes** (Docker) or ~5 minutes (manual)

---

## One-Liner Quickstart ✨

```bash
docker-compose up --build
```

**That's it.** Services start on:
- Backend API: `http://localhost:8000`
- MCP Server: `http://localhost:8001`
- Streamlit UI: `http://localhost:8501`

---

## What You'll See

### 1. **API Documentation** (Judge: Try the interactive docs)
```
http://localhost:8000/docs
```
Swagger UI shows all endpoints. Try `/upload` or `/upload_async` with `demo/sample.mp4`.

### 2. **Streamlit UI** (Judge: Visual demo)
```
http://localhost:8501
```
- Drag & drop a video file
- Watch the job status update in real-time
- Download the generated compliance report (PDF with visual evidence)

### 3. **Audit Trail** (Judge: Verify auditability)
```bash
curl http://localhost:8001/audits | jq
```
Every tool call is logged with timestamp, parameters, and results. Immutable, append-only JSONL.

---

## Testing Without Docker

If Docker is unavailable:

```bash
# Setup (one-time)
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python demo/create_sample_video.py demo/sample.mp4

# Terminal 1: MCP Server
PYTHONPATH=. python3 -m uvicorn mcp.server:app --port 8001

# Terminal 2: Backend
PYTHONPATH=. python3 -m uvicorn backend.main:app --port 8000

# Terminal 3: Upload (via curl or Streamlit)
curl -X POST http://127.0.0.1:8000/upload -F "file=@demo/sample.mp4"
```

---

## What Gets Evaluated

### ✅ Async Pipeline
- Submit job: `POST /upload_async` → returns `job_id`
- Poll progress: `GET /status/{job_id}` → returns `status`, `progress`
- Fetch results: `GET /result/{job_id}` → returns JSON + PDF path

### ✅ Video Processing
- Decodes MP4 frames robustly (handles missing metadata, variable frame counts)
- Detects violations (safety helmets in demo; falls back to deterministic detector)
- Performs compliance reasoning (severity, risk context)
- Looks up enforcement rules (PPE-1, zone compliance, etc.)
- Logs all events to immutable audit trail

### ✅ Enhanced PDF Reports
- Summary page with violation counts and severity breakdown
- Per-violation thumbnails with bounding boxes drawn on frames
- Timestamps, rule references, and remediation recommendations

### ✅ Audit Trail
- Every tool call captured in `mcp/audit.log`
- Queryable via `/audits` endpoint
- Immutable append-only format (each line is a complete JSON record)

### ✅ UI / UX
- Streamlit app for visual file upload and polling
- Real-time job status updates
- Direct PDF download to local machine

---

## Example Output

**Upload response:**
```json
{
  "job_id": "uuid-here",
  "status": "pending"
}
```

**Status response (polling):**
```json
{
  "status": "processing",
  "progress": "decoded 90 frames, detected 6 violations",
  "job_id": "uuid-here"
}
```

**Result response (when done):**
```json
{
  "status": "done",
  "result": {
    "pipeline": [...],
    "events": [
      {
        "detection": {"type": "missing_helmet", "score": 0.92, "bbox": [100,120,300,480]},
        "explanation": "Detected operator without required safety helmet...",
        "rule": {"rule_id": "PPE-1", "desc": "Hardhats mandatory in Zone A"},
        "log": {...}
      },
      ...
    ],
    "report_pdf": "/tmp/sample.mp4.violation_report.pdf"
  }
}
```

**Audit log sample:**
```json
{"tool": "decode_video", "status": "ok", "frames": 90, "timestamp": 1765384836.1}
{"tool": "run_detector", "frame": "...", "detections": 1, "timestamp": 1765384836.2}
{"tool": "run_vlm_reasoning", "type": "missing_helmet", "timestamp": 1765384836.3}
...
```

---

## Optional: Real YOLOv8 Detection

By default, the system uses a **deterministic demo detector** (consistent, no model required).

To enable real ONNX/YOLOv8 detection:
1. Download `yolov8n.onnx` from Ultralytics
2. Place it at `models/yolov8n.onnx`
3. Restart the MCP server
4. Detections will use the real model (falls back gracefully if model is unavailable)

---

## System Architecture

```
[Upload file]
      ↓
[FastAPI Backend] ← HTTP ← [MCP Server]
      ↓                           ↓
  [Job Queue]              [Tool Implementations]
      ↓                      - decode_video
  [Orchestrator]           - run_detector (ONNX or demo)
      ↓                      - run_vlm_reasoning
  [Tool Calls]             - lookup_compliance_rule
      ↓                      - save_event_log
  [Audit Log]              - generate_report
      ↓
  [PDF Report]
```

Every tool call is:
1. Recorded in append-only audit log (`mcp/audit.log`)
2. Exposed via `/audits` endpoint (queryable, JSON)
3. Included in final result JSON

---

## Scoring Checklist (for judges)

- [ ] Docker Compose starts all services
- [ ] Async upload endpoint works (`/upload_async`)
- [ ] Status polling shows progress (`/status/{job_id}`)
- [ ] Result endpoint returns JSON + PDF path (`/result/{job_id}`)
- [ ] PDF report contains thumbnails + bounding boxes
- [ ] Audit log is immutable and queryable (`/audits`)
- [ ] Streamlit UI is functional (file upload, polling, download)
- [ ] End-to-end: upload → detect → log → report → download works

---

## Troubleshooting

**"Port 8000/8001/8501 already in use?"**
```bash
# Kill existing services
pkill -f "uvicorn"
pkill -f "streamlit"
# Then restart docker-compose
```

**"Docker build fails?"**
```bash
# Ensure requirements.txt exists
ls backend/requirements.txt
# Rebuild with verbose output
docker-compose up --build --verbose
```

**"No detections in the report?"**
```bash
# Check MCP server logs
curl http://localhost:8001/audits | jq '.audits[] | select(.tool=="run_detector")'
# Verify video was decoded
curl http://localhost:8001/audits | jq '.audits[] | select(.tool=="decode_video")'
```

**"PDF won't download?"**
```bash
# Check the result JSON for the correct path
curl http://127.0.0.1:8000/result/{job_id} | jq '.result.report_pdf'
# Verify file exists (in container or local /tmp)
ls /tmp/*.violation_report.pdf
```

---

## Next Steps (Post-Hackathon)

- Integrate real YOLO model weights
- Add Redis job queue for durability & scaling
- Implement authentication & signed download URLs
- Extend compliance rule library (OSHA, ISO, custom)
- Add support for live streams (RTSP/HLS)

---

**Questions?** Check `docs/ARCHITECTURE.md` or open an issue.

**Good luck! 🎯**
