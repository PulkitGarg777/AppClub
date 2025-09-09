"""app.py - FastAPI backend for Internship Application Organizer
A minimal, well-commented FastAPI app that stores parsed internship application metadata
and serves a tiny frontend for local review.

Usage:
    pip install -r requirements.txt
    uvicorn backend.app:app --reload

The API exposes:
 - POST /api/applications          : Create an application entry (JSON)
 - GET  /api/applications          : List stored applications
 - POST /api/parse_and_add         : Submit raw subject+body form to parse & add
 - GET  /api/export                : Export CSV of all applications
 - GET  /                           : Tiny demo frontend (served HTML)
"""
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select
from typing import Optional, List
from datetime import datetime
import csv, io, json, re, uuid

DATABASE_URL = "sqlite:///./applications.db"
engine = create_engine(DATABASE_URL, echo=False)

app = FastAPI(title="Internship Application Organizer - Backend")

# Allow any origin for dev/local testing. Restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Database model
# ---------------------------
class Application(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    company_name: Optional[str]
    title: Optional[str]
    job_id: Optional[str]
    platform: Optional[str]
    application_date: Optional[datetime]
    source_email_id: Optional[str]
    source_url: Optional[str]
    attachments_json: Optional[str] = "[]"
    status: Optional[str] = "Applied"
    notes: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Create tables
SQLModel.metadata.create_all(engine)

# ---------------------------
# Parsing helpers (heuristics)
# ---------------------------
job_id_regex = re.compile(r"(?:Req(?:\.|uisition)?|Requisition|Job\s*ID|Req#|Requisition\s*ID|Job\s*Req)[\s:]*#?([A-Za-z0-9\-\_/]+)", re.I)
confirmation_phrases = [
    r"thank you for (applying|your application)",
    r"we have received your application",
    r"application received",
    r"your submission has been received",
    r"application confirmation",
    r"thank you for submitting your application",
]
confirmation_regex = re.compile(r"|".join(confirmation_phrases), re.I)
subject_pattern = re.compile(r"(?P<title>.+?)\s*(?:-|:|\|)\s*(?P<company>.+)", re.I)

def parse_email_text(subject: str, body: str) -> dict:
    """Heuristic parser that extracts is_application, company, title, job_id from subject/body."""
    result = {"is_application": False, "company": None, "title": None, "job_id": None}
    if subject and confirmation_regex.search(subject):
        result["is_application"] = True
    if body and confirmation_regex.search(body):
        result["is_application"] = True
    m = job_id_regex.search(body) or job_id_regex.search(subject or "")
    if m:
        result["job_id"] = m.group(1).strip()
    m2 = subject_pattern.search(subject or "")
    if m2:
        result["title"] = m2.group("title").strip()
        result["company"] = m2.group("company").strip()
    if not result["company"]:
        m3 = re.search(r"Company[:\-]\s*(?P<c>[^\n\r]+)", body or "", re.I)
        if m3:
            result["company"] = m3.group("c").strip()
    return result

# ---------------------------
# API Endpoints
# ---------------------------
@app.post("/api/applications")
async def create_application(payload: dict):
    """Create an application entry from JSON payload. Intended for ingestion workers or extensions."""
    # Handle date parsing for application_date
    application_date = payload.get("application_date")
    if application_date and isinstance(application_date, str):
        try:
            application_date = datetime.fromisoformat(application_date.replace('Z', '+00:00'))
        except ValueError:
            application_date = None
    
    app_obj = Application(
        company_name=payload.get("company_name"),
        title=payload.get("title"),
        job_id=payload.get("job_id"),
        platform=payload.get("platform"),
        application_date=application_date,
        source_email_id=payload.get("source_email_id"),
        source_url=payload.get("source_url"),
        attachments_json=json.dumps(payload.get("attachments") or []),
        status=payload.get("status") or "Applied",
        notes=payload.get("notes") or "",
    )
    with Session(engine) as session:
        session.add(app_obj)
        session.commit()
        session.refresh(app_obj)
    return {"success": True, "id": app_obj.id}

@app.get("/api/applications", response_model=List[Application])
async def list_applications():
    with Session(engine) as session:
        results = session.exec(select(Application).order_by(Application.created_at.desc())).all()
    return results

@app.post("/api/parse_and_add")
async def parse_and_add(subject: str = Form(...), body: str = Form(...)):
    """Accept raw subject and body (form-data), parse using heuristics and add to DB."""
    parsed = parse_email_text(subject, body)
    if not parsed["is_application"]:
        raise HTTPException(status_code=400, detail="Not detected as an application email")
    app_obj = Application(
        company_name=parsed.get("company"),
        title=parsed.get("title"),
        job_id=parsed.get("job_id"),
        platform=None,
        application_date=datetime.utcnow(),
    )
    with Session(engine) as session:
        session.add(app_obj)
        session.commit()
        session.refresh(app_obj)
    return {"success": True, "id": app_obj.id}

@app.get("/api/export")
async def export_csv():
    """Export all applications to CSV (download stream)."""
    with Session(engine) as session:
        rows = session.exec(select(Application).order_by(Application.created_at.desc())).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "company_name", "title", "job_id", "platform", "application_date", "status", "notes"])
    for r in rows:
        writer.writerow([r.id, r.company_name, r.title, r.job_id, r.platform, (r.application_date.isoformat() if r.application_date else ""), r.status, (r.notes or "")])
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=applications_export.csv"})

# ---------------------------
# Minimal frontend served at '/'
# ---------------------------
INDEX_HTML = """<!doctype html>
<html>
<head><meta charset='utf-8'><title>Internship Application Organizer - Demo</title>
<style>body{font-family:Arial,Helvetica,sans-serif;margin:20px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px}th{background:#f2f2f2}</style>
</head>
<body>
<h1>Internship Application Organizer — Demo</h1>
<button id='refreshBtn'>Refresh</button> <a href='/api/export' target='_blank'><button>Export CSV</button></a>
<table><thead><tr><th>Company</th><th>Title</th><th>Job ID</th><th>Date</th><th>Status</th></tr></thead>
<tbody id='tbody'><tr><td colspan='5'>Loading...</td></tr></tbody></table>
<script>
async function load(){document.getElementById('tbody').innerHTML='<tr><td colspan=5>Loading...</td></tr>';const res=await fetch('/api/applications');const rows=await res.json();const t=rows.map(r=>`<tr><td>${r.company_name||''}</td><td>${r.title||''}</td><td>${r.job_id||''}</td><td>${r.application_date?new Date(r.application_date).toLocaleString():''}</td><td>${r.status||''}</td></tr>`).join('');document.getElementById('tbody').innerHTML=t||'<tr><td colspan=5>No applications yet</td></tr>';}
document.getElementById('refreshBtn').addEventListener('click',load);load();
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML
