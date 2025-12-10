Demo instructions (hackathon)

1. Create a Python venv and install backend deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2. Start the backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

3. Health check:

```bash
curl http://localhost:8000/health
```

4. Upload a file (replace `sample.pdf`):

```bash
curl -F "file=@sample.pdf" http://localhost:8000/upload
```

This demo shows the upload → placeholder MCP pipeline start. Next steps: implement MCP server and agent orchestrator to show real tool calls and audit logs.