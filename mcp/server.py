from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import importlib

from . import tools
from .audit_store import append_audit, read_audits

app = FastAPI(title="MCP Server - AI Contract Reviewer")


class RunToolRequest(BaseModel):
    tool: str
    params: Dict[str, Any] = {}


@app.get("/health")
async def health():
    return {"status": "ok", "mcp": True}


@app.post("/run_tool")
async def run_tool(req: RunToolRequest):
    # Resolve tool function
    func = getattr(tools, req.tool, None)
    if func is None:
        raise HTTPException(status_code=404, detail=f"Tool {req.tool} not found")

    # Execute the tool (tools should return dict with result and audit)
    try:
        res = func(**req.params) if isinstance(req.params, dict) else func(req.params)
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If tool returned an `audit` record, persist it
    try:
        audit = res.get("audit") if isinstance(res, dict) else None
        if audit:
            append_audit(audit)
    except Exception:
        pass

    return res


@app.get("/audits")
async def get_audits(limit: int = 100):
    return {"audits": read_audits(limit)}
