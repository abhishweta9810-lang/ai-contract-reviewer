import streamlit as st
import requests
import json

BACKEND_URL = st.sidebar.text_input("Backend URL", value="http://127.0.0.1:8000")

st.title("AI Compliance Monitor — Demo UI")

uploaded = st.file_uploader("Upload a PDF or MP4 (sample) to run the pipeline (async)", type=["pdf", "mp4", "mov", "mkv", "avi"])

if uploaded is not None:
    with st.spinner("Uploading and starting background job..."):
        files = {"file": (uploaded.name, uploaded.getvalue())}
        try:
            resp = requests.post(f"{BACKEND_URL}/upload_async", files=files, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            job_id = data.get("job_id")
        except Exception as e:
            st.error(f"Upload failed: {e}")
            data = None
            job_id = None

    if job_id:
        st.success(f"Started job {job_id}. Polling for status...")
        status_placeholder = st.empty()
        result_placeholder = st.empty()
        import time
        while True:
            try:
                s = requests.get(f"{BACKEND_URL}/status/{job_id}", timeout=10).json()
                status = s.get("status")
            except Exception as e:
                status = "error"
            status_placeholder.info(f"Job {job_id} status: {status}")
            if status == "done":
                r = requests.get(f"{BACKEND_URL}/result/{job_id}", timeout=30).json()
                result = r.get("result")
                result_placeholder.subheader("Raw Report JSON")
                result_placeholder.json(result)
                # Offer PDF download if present
                pdf_path = result.get("report_pdf") or (result.get("aggregated") or {}).get("summary_pdf")
                if pdf_path:
                    try:
                        rr = requests.get(f"{BACKEND_URL}/download_file", params={"path": pdf_path}, timeout=30)
                        rr.raise_for_status()
                        st.download_button("Download Report PDF", rr.content, file_name=pdf_path.split("/")[-1], mime="application/pdf")
                    except Exception as e:
                        st.error(f"Could not download PDF: {e}")
                break
            if status == "failed":
                result_placeholder.error("Job failed; check backend logs.")
                break
            time.sleep(1)
