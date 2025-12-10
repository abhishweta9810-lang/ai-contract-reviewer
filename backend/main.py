from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import logging
from fastapi.responses import FileResponse
from fastapi import Query
from typing import Dict, Any

app = FastAPI(title="AI Contract Reviewer - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("backend")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    """Save uploaded file, run the agent orchestrator pipeline, and return the report.

    This endpoint integrates the orchestrator (agents/orchestrator.py) so the demo is
    runnable as a single service: upload -> orchestrator -> aggregated JSON report.
    """
    suffix = file.filename.split('.')[-1] if file.filename else 'bin'
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Try to run the orchestrator pipeline (calls MCP server). If MCP isn't running
    # or orchestrator fails, return a helpful error with the upload path preserved.
    try:
        # Import here to keep startup lightweight if agents aren't needed immediately
        from agents.orchestrator import Orchestrator

        orch = Orchestrator()
        # If the uploaded file is a video (by extension), run video pipeline
        if suffix.lower() in ("mp4", "mov", "mkv", "avi"):
            report = orch.run_video_pipeline(tmp_path)
        else:
            report = orch.run_pipeline(tmp_path)
        return JSONResponse(content={"filename": file.filename, "tmp_path": tmp_path, "report": report})
    except Exception as e:
        logger.exception("Orchestrator run failed")
        return JSONResponse(status_code=500, content={
            "filename": file.filename,
            "tmp_path": tmp_path,
            "error": str(e),
            "note": "Uploaded file saved; start MCP server and run the orchestrator manually if needed."
        })


##### Asynchronous upload endpoints (simple in-memory job store) #####
import uuid
from fastapi import BackgroundTasks

# Simple in-memory job store: {job_id: {status: pending|running|done|failed, result: {...}}}
JOB_STORE: Dict[str, Dict[str, Any]] = {}


def _run_job(job_id: str, path: str):
    JOB_STORE[job_id]["status"] = "running"
    try:
        from agents.orchestrator import Orchestrator

        orch = Orchestrator()
        if path.split('.')[-1].lower() in ("mp4", "mov", "mkv", "avi"):
            report = orch.run_video_pipeline(path)
        else:
            report = orch.run_pipeline(path)
        JOB_STORE[job_id]["status"] = "done"
        JOB_STORE[job_id]["result"] = report
    except Exception as e:
        JOB_STORE[job_id]["status"] = "failed"
        JOB_STORE[job_id]["error"] = str(e)


@app.post("/upload_async")
async def upload_async(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    suffix = file.filename.split('.')[-1] if file.filename else 'bin'
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = {"status": "pending", "result": None}
    background_tasks.add_task(_run_job, job_id, tmp_path)
    return JSONResponse(content={"job_id": job_id, "status": "pending", "tmp_path": tmp_path})


@app.get("/status/{job_id}")
async def job_status(job_id: str):
    job = JOB_STORE.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "job not found"})
    return JSONResponse(content={"job_id": job_id, "status": job.get("status")})


@app.get("/result/{job_id}")
async def job_result(job_id: str):
    job = JOB_STORE.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "job not found"})
    if job.get("status") != "done":
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": job.get("status")})
    return JSONResponse(content={"job_id": job_id, "status": "done", "result": job.get("result")})


@app.get("/download_file")
async def download_file(path: str = Query(..., description="Absolute path to file on server")):
    """Serve a file from the server (used for demo to download generated PDFs).

    WARNING: This endpoint is for demo only and trusts the caller's `path`. Do not
    expose this in production without access controls and path sanitization.
    """
    if not path or not isinstance(path, str):
        return JSONResponse(status_code=400, content={"error": "invalid path"})
    try:
        return FileResponse(path, filename=path.split("/")[-1])
    except Exception as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
