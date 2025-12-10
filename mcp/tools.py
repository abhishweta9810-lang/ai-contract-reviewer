"""MCP tool implementations for AI Contract Reviewer.

These implementations use lightweight, local heuristics to make the hackathon demo
produce realistic outputs without heavy external dependencies.

Tools implemented:
- extract_text_from_pdf: uses pdfminer.six to extract text
- split_into_clauses: heuristic paragraph/heading splitter
- detect_entities: regex heuristics for dates, amounts, parties
- validate_rule: simple business-rule checks (date consistency)
- calculate_amounts: sums passed line items
- suggest_corrections: small templated suggestions
- generate_summary_pdf: renders summary text to a simple PDF using Pillow
"""
from typing import Dict, Any, List
import time
import re
import os
from pdfminer.high_level import extract_text
from PIL import Image, ImageDraw, ImageFont
import imageio
import math
from .audit_store import append_audit


def _audit(record: Dict[str, Any]) -> Dict[str, Any]:
    record.setdefault("timestamp", time.time())
    return record


def extract_text_from_pdf(path: str) -> Dict[str, Any]:
    """Extract text from a PDF file using pdfminer.six with OCR fallback.

    Returns result={"text": str, "pages": int}
    """
    text = ""
    pages = 1
    extraction_method = "failed"
    
    try:
        # Try pdfminer first for text-based PDFs
        text = extract_text(path)
        if text and len(text.strip()) > 20:  # Only use if we got meaningful text
            extraction_method = "pdfminer"
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                    pages = raw.count(b"/Type /Page") or 1
            except Exception:
                pages = 1
        else:
            text = ""  # Reset for fallback
    except Exception as pdfminer_err:
        text = ""
    
    # If pdfminer failed or got minimal text, try OCR
    if not text or len(text.strip()) < 20:
        try:
            # Try pdf2image + pytesseract for OCR
            try:
                from pdf2image import convert_from_path
                import pytesseract
                
                images = convert_from_path(path, dpi=150)
                pages = len(images)
                text_parts = []
                for idx, img in enumerate(images):
                    try:
                        ocr_text = pytesseract.image_to_string(img, lang='eng')
                        if ocr_text.strip():
                            text_parts.append(f"--- Page {idx+1} ---\n{ocr_text}")
                    except Exception:
                        pass
                
                if text_parts:
                    text = "\n".join(text_parts)
                    extraction_method = "ocr"
                else:
                    text = ""
            except ImportError:
                # OCR libraries not available, skip
                pass
        except Exception:
            pass
    
    # If still no text, try reading as plain text
    if not text:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
                if file_text.strip():
                    text = file_text
                    extraction_method = "plaintext"
                    pages = 1
        except Exception:
            pass
    
    # Last resort fallback
    if not text:
        text = "(Unable to extract text from file - file may be corrupted or in unsupported format)"
        pages = 1
        extraction_method = "failed"

    out = {"text": text, "pages": pages}
    return {"result": out, "audit": _audit({"tool": "extract_text_from_pdf", "path": path, "pages": pages, "method": extraction_method, "text_length": len(text)})}


def split_into_clauses(text: str) -> Dict[str, Any]:
    """Heuristic clause splitter: split by double newlines or numbered headings."""
    if not text:
        return {"result": [], "audit": _audit({"tool": "split_into_clauses", "length": 0})}

    # Normalize whitespace
    norm = re.sub(r"\r\n", "\n", text)
    parts = re.split(r"\n\s*\n", norm)

    clauses = []
    for i, p in enumerate(parts):
        title = None
        # try to detect heading like '1. Termination' or 'Termination:'
        lines = [l.strip() for l in p.splitlines() if l.strip()]
        if lines:
            first = lines[0]
            m = re.match(r"^(\d+\.|Section\s+\d+\.|[A-Z][A-Za-z ]{3,50}:?)\\s*(.*)$", first)
            if m:
                title = first
        clauses.append({"id": f"c{i+1}", "title": title or "", "text": p.strip()})

    return {"result": clauses, "audit": _audit({"tool": "split_into_clauses", "clauses": len(clauses)})}


def detect_entities(text: str) -> Dict[str, Any]:
    """Detect simple entities: dates, amounts, and party names via heuristics."""
    dates = []
    amounts = []
    parties = []

    # dates: YYYY-MM-DD, DD Month YYYY, Month DD, YYYY
    date_patterns = [r"\b\d{4}-\d{2}-\d{2}\b", r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b", r"\b[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\b"]
    for pat in date_patterns:
        for m in re.findall(pat, text):
            if m not in dates:
                dates.append(m)

    # amounts: currency symbols or numbers with commas and decimal
    for m in re.findall(r"\b\$?\d{1,3}(?:[\,\d]*)(?:\.\d{2})\b", text):
        if m not in amounts:
            amounts.append(m)

    # parties: look for 'between X and Y' or 'This Agreement is between'
    between = re.search(r"between\s+([^,\n]+?)\s+and\s+([^,\n]+?)\b", text, re.IGNORECASE)
    if between:
        a, b = between.groups()
        parties.extend([a.strip(), b.strip()])
    else:
        # fallback: detect lines that contain 'Inc' or 'LLC' or 'Ltd' or 'Corporation'
        for m in re.findall(r"([A-Z][A-Za-z0-9\.,&\- ]{2,50}?(?:Inc|LLC|Ltd|Corporation|Corp|GmbH|S\.A\.|Pvt))", text):
            if m.strip() not in parties:
                parties.append(m.strip())

    result = {"parties": parties, "dates": dates, "amounts": amounts}
    return {"result": result, "audit": _audit({"tool": "detect_entities", "found": {"dates": len(dates), "amounts": len(amounts), "parties": len(parties)}})}


def validate_rule(name: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Contract validation rules with actual analysis of content."""
    if name == "date_consistency":
        dates = context.get("dates") or []
        parsed = []
        from datetime import datetime

        def try_parse(s: str):
            for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(s, fmt)
                except Exception:
                    continue
            return None

        for d in dates:
            p = try_parse(d)
            if p:
                parsed.append(p)

        ok = True
        explanation = "no date issues found"
        if len(parsed) >= 2:
            if parsed[0] > parsed[1]:
                ok = False
                explanation = "start date is after end date"
        elif len(parsed) == 1:
            explanation = "only one parseable date found"
        else:
            explanation = "no parseable dates found"

        details = {"rule": name, "ok": ok, "explanation": explanation, "parsed_dates": [d.isoformat() for d in parsed]}
        return {"result": details, "audit": _audit({"tool": "validate_rule", "rule": name, "ok": ok})}
    
    elif name == "liability_clause":
        text = context.get("text", "").lower()
        has_liability = "liability" in text
        has_limitation = "limitation" in text
        has_indemnity = "indemnif" in text
        
        ok = has_liability or has_limitation
        explanation = []
        if has_liability:
            explanation.append("✓ Liability clause found")
        else:
            explanation.append("⚠ No explicit liability clause")
        if has_limitation:
            explanation.append("✓ Limitation of liability present")
        else:
            explanation.append("⚠ No liability limitation found")
        if has_indemnity:
            explanation.append("✓ Indemnification clause detected")
            
        details = {"rule": name, "ok": ok, "explanation": "; ".join(explanation), "findings": {"liability": has_liability, "limitation": has_limitation, "indemnity": has_indemnity}}
        return {"result": details, "audit": _audit({"tool": "validate_rule", "rule": name, "ok": ok})}
    
    elif name == "confidentiality":
        text = context.get("text", "").lower()
        has_confidentiality = "confidential" in text or "proprietary" in text or "secret" in text
        has_disclosure = "disclose" in text or "disclosure" in text
        has_term = "year" in text or "month" in text
        
        ok = has_confidentiality
        explanation = []
        if has_confidentiality:
            explanation.append("✓ Confidentiality obligations defined")
        else:
            explanation.append("⚠ No confidentiality clause found")
        if has_disclosure:
            explanation.append("✓ Permitted disclosure rules present")
        if has_term:
            explanation.append("✓ Confidentiality term specified")
        else:
            explanation.append("⚠ Confidentiality duration unclear")
            
        details = {"rule": name, "ok": ok, "explanation": "; ".join(explanation), "findings": {"has_confidentiality": has_confidentiality, "has_disclosure": has_disclosure, "has_term": has_term}}
        return {"result": details, "audit": _audit({"tool": "validate_rule", "rule": name, "ok": ok})}
    
    elif name == "termination":
        text = context.get("text", "").lower()
        has_termination = "terminat" in text
        has_notice = "notice" in text and ("day" in text or "month" in text)
        has_cause = "cause" in text or "breach" in text
        
        ok = has_termination
        explanation = []
        if has_termination:
            explanation.append("✓ Termination clause present")
        else:
            explanation.append("⚠ No termination clause")
        if has_notice:
            explanation.append("✓ Notice period defined")
        else:
            explanation.append("⚠ Notice requirements unclear")
        if has_cause:
            explanation.append("✓ Termination for cause addressed")
            
        details = {"rule": name, "ok": ok, "explanation": "; ".join(explanation), "findings": {"has_termination": has_termination, "has_notice": has_notice, "has_cause": has_cause}}
        return {"result": details, "audit": _audit({"tool": "validate_rule", "rule": name, "ok": ok})}
    
    elif name == "indemnification":
        text = context.get("text", "").lower()
        has_indemnity = "indemnif" in text or "hold harmless" in text
        has_insurance = "insur" in text
        
        ok = has_indemnity
        explanation = []
        if has_indemnity:
            explanation.append("✓ Indemnification obligation found")
        else:
            explanation.append("⚠ No indemnification clause")
        if has_insurance:
            explanation.append("✓ Insurance requirements mentioned")
            
        details = {"rule": name, "ok": ok, "explanation": "; ".join(explanation), "findings": {"has_indemnity": has_indemnity, "has_insurance": has_insurance}}
        return {"result": details, "audit": _audit({"tool": "validate_rule", "rule": name, "ok": ok})}
    
    # default: unknown rule
    details = {"rule": name, "ok": False, "explanation": "unknown rule"}
    return {"result": details, "audit": _audit({"tool": "validate_rule", "rule": name, "ok": False})}


def calculate_amounts(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum amounts from line items. Expects `lines` like [{"amount": "123.45"}, ...]

    For the demo, if lines is empty we return zero.
    """
    total = 0.0
    for ln in lines or []:
        a = ln.get("amount")
        if a is None:
            continue
        # remove currency symbols and commas
        s = re.sub(r"[^0-9\.\-]", "", str(a))
        try:
            total += float(s)
        except Exception:
            continue

    return {"result": {"sum": total}, "audit": _audit({"tool": "calculate_amounts", "lines": len(lines or [])})}


def suggest_corrections(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a small templated suggestion for a flagged issue."""
    issue_id = issue.get("id", "unknown")
    desc = issue.get("desc", "unspecified issue")
    suggestion = f"Review issue {issue_id}: {desc}. Suggested action: verify source data and correct the clause or amount." 
    return {"result": {"suggestion": suggestion}, "audit": _audit({"tool": "suggest_corrections", "issue": issue_id})}


def generate_summary_pdf(summary: Dict[str, Any], out_path: str = None) -> Dict[str, Any]:
    """Render a summary PDF that includes a textual summary page and one thumbnail per event
    with bounding boxes drawn.

    `summary` is expected to be a dict with key `checks` or `events` containing detected events.
    """
    events = summary.get("events") or summary.get("checks") or []
    # First page: textual summary
    lines = ["Compliance Report", "=", f"Total items: {len(events)}", ""]
    for i, ev in enumerate(events):
        if isinstance(ev, dict):
            # Handle video violations with 'detection' field
            det = ev.get("detection")
            if det:
                lines.append(f"{i+1}. {det.get('type')} score={det.get('score')} frame_index={det.get('frame_index')}")
            else:
                # Handle contract review checks (no detection field)
                rule_id = ev.get("rule_id", "N/A")
                severity = ev.get("severity", "INFO")
                description = ev.get("description", ev.get("text", "Check performed"))
                lines.append(f"{i+1}. [{rule_id}] {severity}: {description[:80]}")
        else:
            lines.append(f"{i+1}. {str(ev)[:100]}")

    body = "\n".join(lines)

    pages = []
    try:
        # Text page
        text_img = Image.new("RGB", (1200, 1600), color=(255, 255, 255))
        d = ImageDraw.Draw(text_img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        d.multiline_text((50, 50), body, fill=(0, 0, 0), font=font)
        pages.append(text_img)

        # For each event, create a thumbnail with bbox (for video) or detail page (for contract)
        for ev in events:
            if isinstance(ev, dict):
                det = ev.get("detection")
                if det and "frame" in det:
                    # Video violation with frame thumbnail
                    frame_path = det.get("frame")
                    bbox = det.get("bbox")
                    try:
                        img = Image.open(frame_path).convert("RGB")
                        draw = ImageDraw.Draw(img)
                        if bbox and len(bbox) == 4:
                            draw.rectangle(bbox, outline="red", width=4)
                        # Resize to fit page width
                        img.thumbnail((1100, 1400))
                        pages.append(img)
                    except Exception:
                        # If frame not available, create placeholder
                        ph = Image.new("RGB", (1200, 800), color=(240, 240, 240))
                        pd = ImageDraw.Draw(ph)
                        pd.text((50, 50), f"Frame not available", fill=(0, 0, 0), font=font)
                        pages.append(ph)
                elif "clause_id" in ev or "rule_id" in ev:
                    # Contract review check - create detail page
                    detail_lines = [
                        f"Check: {ev.get('rule_id', 'N/A')}",
                        f"Severity: {ev.get('severity', 'INFO')}",
                        "",
                        f"Description: {ev.get('description', ev.get('text', 'N/A'))[:200]}",
                        "",
                        f"Clause: {ev.get('clause_id', 'N/A')}"
                    ]
                    detail_page = Image.new("RGB", (1200, 800), color=(245, 245, 245))
                    dd = ImageDraw.Draw(detail_page)
                    dd.multiline_text((50, 50), "\n".join(detail_lines), fill=(0, 0, 0), font=font)
                    pages.append(detail_page)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        # Save multi-page PDF
        pages[0].save(out_path, "PDF", resolution=100.0, save_all=True, append_images=pages[1:])
    except Exception as e:
        return {"result": {"out_path": out_path, "error": str(e)}, "audit": _audit({"tool": "generate_summary_pdf", "ok": False})}

    return {"result": {"out_path": out_path}, "audit": _audit({"tool": "generate_summary_pdf", "out_path": out_path})}


def decode_video(path: str, max_frames: int = 120) -> Dict[str, Any]:
    """Decode video using imageio (ffmpeg) and save sampled frames to a temp directory.

    Returns list of saved frame paths in result.frames.
    """
    frames_out = []
    try:
        reader = imageio.get_reader(path, "ffmpeg")
        meta = reader.get_meta_data()
        fps = meta.get("fps", 30)
        total = meta.get("nframes", None)
    except Exception:
        # fallback values if ffmpeg metadata isn't available
        fps = 30
        total = None

    tmpdir = os.path.join("/tmp", f"mcp_frames_{os.path.basename(path)}")
    os.makedirs(tmpdir, exist_ok=True)

    try:
        reader = imageio.get_reader(path, "ffmpeg")
        i = 0
        # Defensive handling of `total` (nframes) which may be None or inf
        if total is None or not isinstance(total, (int, float)) or not math.isfinite(total) or total <= 0:
            total_for_calc = max_frames
        else:
            total_for_calc = int(total)

        step = max(1, math.floor(total_for_calc / max_frames))
        for frame in reader:
            try:
                if i % step == 0:
                    out_path = os.path.join(tmpdir, f"frame_{i:06d}.png")
                    imageio.imwrite(out_path, frame)
                    frames_out.append(out_path)
                    if len(frames_out) >= max_frames:
                        break
                i += 1
            except Exception:
                # skip problematic frames but continue
                i += 1
                continue
    except Exception as e:
        return {"result": {"frames": frames_out, "error": str(e)}, "audit": _audit({"tool": "decode_video", "ok": False})}

    return {"result": {"frames": frames_out, "fps": fps}, "audit": _audit({"tool": "decode_video", "frames": len(frames_out)})}


def run_detector(frame_path: str) -> Dict[str, Any]:
    """Simple heuristic detector for demo: simulate detection events on sampled frames.

    For demo purposes, this creates an event when the frame index modulo 15 is zero.
    """
    basename = os.path.basename(frame_path)
    m = re.search(r"frame_(\d+)", basename)
    idx = int(m.group(1)) if m else 0
    detections = []

    """Detector that uses a YOLOv8 ONNX model if available, otherwise falls back to the demo detector.

    Behavior:
    - If file `models/yolov8n.onnx` exists, uses OpenCV DNN to run it (assumes standard Ultralytics ONNX output: [1, N, 85]).
    - Otherwise uses the previous simulated detector for deterministic demo output.
    """
    detections = []
    # Attempt ONNX model
    model_path = os.path.join(os.path.dirname(__file__), "..", "models", "yolov8n.onnx")
    model_path = os.path.normpath(model_path)
    if os.path.exists(model_path):
        try:
            net = cv2.dnn.readNet(model_path)
            img = cv2.imread(frame_path)
            h0, w0 = img.shape[:2]
            # YOLOv8 standard input size is 640; adjust as needed
            inp_size = 640
            blob = cv2.dnn.blobFromImage(img, 1/255.0, (inp_size, inp_size), swapRB=True, crop=False)
            net.setInput(blob)
            preds = net.forward()
            # preds shape may be (1, N, 85) or (N,85)
            arr = np.array(preds)
            if arr.ndim == 3:
                arr = arr[0]
            # each row: [x, y, w, h, conf, cls0, cls1... ] OR [x_center, y_center, w, h, conf, class]
            for row in arr:
                conf = float(row[4])
                if conf < 0.25:
                    continue
                # find class id with max score in remaining cols
                cls_scores = row[5:]
                cls_id = int(np.argmax(cls_scores)) if len(cls_scores) > 0 else 0
                score = float(conf)
                # Convert box from xywh (normalized?) to pixel coords — assume xywh relative to inp_size
                x_c, y_c, w, h = row[0:4]
                # If values look <=1, assume normalized
                if x_c <= 1.0 and w <= 1.0:
                    x_c *= w0
                    y_c *= h0
                    w *= w0
                    h *= h0
                x1 = max(0, int(x_c - w/2))
                y1 = max(0, int(y_c - h/2))
                x2 = min(w0, int(x_c + w/2))
                y2 = min(h0, int(y_c + h/2))
                detections.append({
                    "type": f"class_{cls_id}",
                    "score": score,
                    "bbox": [x1, y1, x2, y2],
                    "frame": frame_path,
                    "frame_index": idx,
                })
        except Exception:
            # fallback to demo detector if model fails
            pass

    # If no detections from model, fallback to deterministic simulated detector (every 15 frames)
    if not detections:
        if idx % 15 == 0:
            detections.append({
                "type": "missing_helmet",
                "score": 0.92,
                "bbox": [100, 120, 300, 480],
                "frame": frame_path,
                "frame_index": idx,
            })

    return {"result": detections, "audit": _audit({"tool": "run_detector", "frame": frame_path, "detections": len(detections)})}


def run_vlm_reasoning(frame_path: str, detection: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a natural-language explanation for a detection (stubbed).

    In production, this would call a local VLM/LLM. For demo we generate templated text.
    """
    d_type = detection.get("type")
    if d_type == "missing_helmet":
        text = (
            "Detected operator without required safety helmet while in a restricted area. "
            "This increases risk of head injury near heavy machinery."
        )
        severity = "high"
    else:
        text = "Detected event requiring attention."
        severity = "medium"

    return {"result": {"explanation": text, "severity": severity}, "audit": _audit({"tool": "run_vlm_reasoning", "type": d_type})}


def lookup_compliance_rule(detection_type: str) -> Dict[str, Any]:
    """Map detection types to compliance rules (demo mapping)."""
    rules = {
        "missing_helmet": {"rule_id": "PPE-1", "desc": "Hardhats mandatory in Zone A", "required": True},
    }
    r = rules.get(detection_type, {"rule_id": "GEN-1", "desc": "General safety rule", "required": False})
    return {"result": r, "audit": _audit({"tool": "lookup_compliance_rule", "type": detection_type})}


def save_event_log(event: Dict[str, Any]) -> Dict[str, Any]:
    """Save event to append-only audit store via append_audit. Returns event id.

    This ensures events are traceable and timestamped.
    """
    log = append_audit({"tool": "event_log", "event": event})
    return {"result": {"log": log}, "audit": _audit({"tool": "save_event_log"})}


def generate_report(events: List[Dict[str, Any]], out_path: str) -> Dict[str, Any]:
    """Generate a PDF report summarizing the events using existing PDF generator."""
    summary = {"checks": events}
    return generate_summary_pdf(summary, out_path)

