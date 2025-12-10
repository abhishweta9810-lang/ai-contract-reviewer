import json
import os
import threading
from typing import List, Dict, Any

_LOCK = threading.Lock()
_AUDIT_FILE = os.path.join(os.path.dirname(__file__), "audit.log")


def append_audit(record: Dict[str, Any]) -> Dict[str, Any]:
    """Append an audit record to the JSONL audit file. Returns the record with timestamp.

    This is intentionally simple: production should use a tamper-evident, append-only
    ledger or WORM storage.
    """
    with _LOCK:
        record.setdefault("timestamp", __import__("time").time())
        # Ensure directory exists
        os.makedirs(os.path.dirname(_AUDIT_FILE), exist_ok=True)
        with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_audits(limit: int = 100) -> List[Dict[str, Any]]:
    """Read the last `limit` audit records (naive implementation)."""
    if not os.path.exists(_AUDIT_FILE):
        return []
    with open(_AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    lines = lines[-limit:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except Exception:
            continue
    return out
