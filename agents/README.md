Agents and responsibilities

1. Document Agent: Handles OCR, page segmentation, and physical structure detection.
2. Clause Agent: Extracts clauses, classifies clause types, and creates clause embeddings.
3. Consistency Agent: Cross-checks fields (dates, amounts, parties) and flags mismatches.
4. Compliance Agent: Runs policy rules and legal requirements checks.
5. Correction Agent: Proposes fixes and canonical rewrites for ambiguous or missing text.
6. Risk Agent: Ranks findings by severity and identifies contradictory clauses.
7. Reporting Agent: Constructs final JSON, summary PDF, and audit trail.

Each agent should call MCP tools (see `mcp/tools.py`) rather than performing side-effects directly.