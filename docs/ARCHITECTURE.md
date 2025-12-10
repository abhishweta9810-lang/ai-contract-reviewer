Architecture Overview

Components

- Frontend: Upload UI, live validation progress, clause map, risk chart. (Next.js/Streamlit)
- Backend: FastAPI service that accepts files and orchestrates MCP runs.
- MCP Server: Execution layer that exposes tools (extract_text_from_pdf, validate_rule, etc.).
- Agents: LLM-driven orchestrator that calls MCP tools and performs debate/verification loops.
- Storage: Document store for originals, embeddings DB for clauses, and an immutable audit trail.

Data Flow

1. User uploads PDF → Backend accepts file
2. Backend invokes MCP tool `extract_text_from_pdf`
3. Document Agent breaks into clauses via `split_into_clauses`
4. Clause Agent extracts entities and embeddings (`detect_entities` + embedding service)
5. Consistency & Compliance Agents validate and call `validate_rule` / `calculate_amounts`
6. Correction Agent proposes fixes via `suggest_corrections` and commits suggestions to report
7. Reporting Agent calls `generate_summary_pdf` and returns JSON + summary PDF to user

Notes on Auditability

- Every MCP tool call returns an `audit` record.
- Audit records should be stored in an append-only, tamper-evident store (e.g. WORM storage or ledger).
- Agents should reference audit ids in summaries for full traceability.