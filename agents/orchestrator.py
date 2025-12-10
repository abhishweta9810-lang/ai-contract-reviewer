"""Simple agent orchestrator that calls the MCP server tools.

This orchestrator is intentionally simple for a hackathon demo: it calls MCP tools
in a deterministic pipeline and aggregates results and audits into a report.
"""
import os
import requests
import json
from typing import Dict, Any, List

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8001")


def call_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{MCP_URL}/run_tool"
    payload = {"tool": tool, "params": params}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


class Orchestrator:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def run_pipeline(self, pdf_path: str) -> Dict[str, Any]:
        report: Dict[str, Any] = {"pipeline": [], "aggregated": {}} 

        # 1. Extract text
        r1 = call_tool("extract_text_from_pdf", {"path": pdf_path})
        self.calls.append({"tool": "extract_text_from_pdf", "resp": r1})
        report["pipeline"].append({"step": "extract_text", "resp": r1})

        text = r1.get("result", {}).get("text", "")

        # 2. Split into clauses
        r2 = call_tool("split_into_clauses", {"text": text})
        self.calls.append({"tool": "split_into_clauses", "resp": r2})
        report["pipeline"].append({"step": "split_into_clauses", "resp": r2})

        clauses = r2.get("result", [])

        # 3. Detect entities
        r3 = call_tool("detect_entities", {"text": text})
        self.calls.append({"tool": "detect_entities", "resp": r3})
        report["pipeline"].append({"step": "detect_entities", "resp": r3})

        entities = r3.get("result", {})

        # 4. Run validations (meaningful contract checks)
        checks = []
        
        # Check date consistency
        r4 = call_tool("validate_rule", {"name": "date_consistency", "context": entities})
        self.calls.append({"tool": "validate_rule", "resp": r4})
        report["pipeline"].append({"step": "validate_rule_date_consistency", "resp": r4})
        checks.append(r4.get("result"))
        
        # Check liability clauses
        r4b = call_tool("validate_rule", {"name": "liability_clause", "context": {"text": text}})
        self.calls.append({"tool": "validate_rule_liability", "resp": r4b})
        report["pipeline"].append({"step": "validate_rule_liability", "resp": r4b})
        checks.append(r4b.get("result"))
        
        # Check confidentiality
        r4c = call_tool("validate_rule", {"name": "confidentiality", "context": {"text": text}})
        self.calls.append({"tool": "validate_rule_confidentiality", "resp": r4c})
        report["pipeline"].append({"step": "validate_rule_confidentiality", "resp": r4c})
        checks.append(r4c.get("result"))
        
        # Check termination clauses
        r4d = call_tool("validate_rule", {"name": "termination", "context": {"text": text}})
        self.calls.append({"tool": "validate_rule_termination", "resp": r4d})
        report["pipeline"].append({"step": "validate_rule_termination", "resp": r4d})
        checks.append(r4d.get("result"))
        
        # Check indemnification
        r4e = call_tool("validate_rule", {"name": "indemnification", "context": {"text": text}})
        self.calls.append({"tool": "validate_rule_indemnification", "resp": r4e})
        report["pipeline"].append({"step": "validate_rule_indemnification", "resp": r4e})
        checks.append(r4e.get("result"))

        r5 = call_tool("calculate_amounts", {"lines": []})
        self.calls.append({"tool": "calculate_amounts", "resp": r5})
        report["pipeline"].append({"step": "calculate_amounts", "resp": r5})

        # 5. Suggest corrections for any issues (demo uses a placeholder issue)
        issue = {"id": "issue-1", "desc": "placeholder discrepancy"}
        r6 = call_tool("suggest_corrections", {"issue": issue})
        self.calls.append({"tool": "suggest_corrections", "resp": r6})
        report["pipeline"].append({"step": "suggest_corrections", "resp": r6})

        # 6. Generate summary PDF (write to temp path)
        out_path = os.path.join("/tmp", os.path.basename(pdf_path) + ".summary.pdf")
        r7 = call_tool("generate_summary_pdf", {"summary": {"checks": checks}, "out_path": out_path})
        self.calls.append({"tool": "generate_summary_pdf", "resp": r7})
        report["pipeline"].append({"step": "generate_summary_pdf", "resp": r7})

        # Aggregate small report
        report["aggregated"] = {
            "filename": os.path.basename(pdf_path),
            "clauses_count": len(clauses),
            "entities": entities,
            "checks": checks,
            "summary_pdf": r7.get("result", {}).get("out_path"),
        }

        return report

    def run_video_pipeline(self, video_path: str, max_frames: int = 120) -> Dict[str, Any]:
        """Process a video: decode frames, run detector, reason, check rules, and report.

        Returns an aggregated report with events and a summary PDF path.
        """
        report: Dict[str, Any] = {"pipeline": [], "events": []}

        # 1. Decode video to frames
        r1 = call_tool("decode_video", {"path": video_path, "max_frames": max_frames})
        self.calls.append({"tool": "decode_video", "resp": r1})
        report["pipeline"].append({"step": "decode_video", "resp": r1})

        frames = r1.get("result", {}).get("frames", [])

        # 2. Iterate frames and run detector
        for f in frames:
            rdet = call_tool("run_detector", {"frame_path": f})
            self.calls.append({"tool": "run_detector", "resp": rdet})
            report["pipeline"].append({"step": "run_detector", "frame": f, "resp": rdet})
            detections = rdet.get("result", [])
            for det in detections:
                # Reason about detection
                rreason = call_tool("run_vlm_reasoning", {"frame_path": f, "detection": det})
                self.calls.append({"tool": "run_vlm_reasoning", "resp": rreason})
                report["pipeline"].append({"step": "run_vlm_reasoning", "resp": rreason})

                # Lookup compliance rule
                rrule = call_tool("lookup_compliance_rule", {"detection_type": det.get("type")})
                self.calls.append({"tool": "lookup_compliance_rule", "resp": rrule})
                report["pipeline"].append({"step": "lookup_compliance_rule", "resp": rrule})

                event = {
                    "detection": det,
                    "explanation": rreason.get("result"),
                    "rule": rrule.get("result"),
                }

                # Save event log
                rlog = call_tool("save_event_log", {"event": event})
                self.calls.append({"tool": "save_event_log", "resp": rlog})
                report["pipeline"].append({"step": "save_event_log", "resp": rlog})

                event["log"] = rlog.get("result")
                report["events"].append(event)

        # 3. Generate report PDF
        out_path = os.path.join("/tmp", os.path.basename(video_path) + ".violation_report.pdf")
        rrep = call_tool("generate_report", {"events": report["events"], "out_path": out_path})
        self.calls.append({"tool": "generate_report", "resp": rrep})
        report["pipeline"].append({"step": "generate_report", "resp": rrep})

        report["report_pdf"] = rrep.get("result", {}).get("out_path")
        return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to sample PDF to run through the pipeline")
    parser.add_argument("--mcp", help="MCP server URL (default http://127.0.0.1:8001)")
    args = parser.parse_args()
    if args.mcp:
        MCP_URL = args.mcp

    orch = Orchestrator()
    rpt = orch.run_pipeline(args.pdf)
    print(json.dumps(rpt, indent=2))
