"""gmail_parser.py - Fetch and parse likely application-confirmation emails from Gmail

This script uses Gmail API (OAuth) to search recent messages, detect application confirmations
using simple heuristics, extract company/title/job-id, and write a CSV export.

Instructions:
  1. Create OAuth credentials (Desktop app) in Google Cloud Console -> download credentials.json (make sure to place credentials.json in the same directory as this script)
  2. pip install -r requirements_gmail.txt
  3. python gmail_parser.py

Security note: This script uses readonly scope for Gmail. Do not share your token.pickle.
"""
import os, base64, re, csv, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

job_id_regex = re.compile(r"(?:Req(?:\\.|uisition)?|Requisition|Job\\s*ID|Req#|Requisition\\s*ID|Job\\s*Req)[\\s:]*#?([A-Za-z0-9\\-\\_/]+)", re.I)
confirmation_phrases = [
    r"thank you for (applying|your application)",
    r"we have received your application",
    r"application received",
    r"your submission has been received",
    r"application confirmation",
    r"thank you for submitting your application",
]
confirmation_regex = re.compile(r"|".join(confirmation_phrases), re.I)

def gmail_authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle','rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError('credentials.json not found - create OAuth client in Google Cloud Console.')
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle','wb') as f:
            pickle.dump(creds, f)
    service = build('gmail', 'v1', credentials=creds)
    return service

def message_to_text(msg):
    parts = []
    payload = msg.get('payload', {})
    def walk(part):
        if part.get('parts'):
            for p in part['parts']:
                walk(p)
        else:
            body = part.get('body', {}).get('data')
            if body:
                text = base64.urlsafe_b64decode(body).decode('utf-8', errors='replace')
                parts.append(text)
    walk(payload)
    if not parts and payload.get('body', {}).get('data'):
        parts.append(base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace'))
    return "\\n\\n".join(parts)

def is_application_email(subject, body):
    if subject and confirmation_regex.search(subject):
        return True
    if body and confirmation_regex.search(body):
        return True
    return False

def extract_fields(subject, body):
    result = {'company': None, 'title': None, 'job_id': None}
    m = job_id_regex.search(body) or job_id_regex.search(subject or "")
    if m:
        result['job_id'] = m.group(1).strip()
    m2 = re.search(r"(?P<title>.+?)\\s*(?:-|:|\\|)\\s*(?P<company>.+)", subject or "", re.I)
    if m2:
        result['title'] = m2.group('title').strip()
        result['company'] = m2.group('company').strip()
    m3 = re.search(r"Company[:\\-]\\s*(?P<c>[^\\n\\r]+)", body or "", re.I)
    if m3 and not result['company']:
        result['company'] = m3.group('c').strip()
    return result

def main():
    service = gmail_authenticate()
    query = 'newer_than:365d OR subject:("application" OR "applied" OR "thank you for applying")'
    results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
    messages = results.get('messages', [])
    print(f"Found {len(messages)} candidate messages.")
    rows = []
    for m in messages:
        msg = service.users().messages().get(userId='me', id=m['id'], format='full').execute()
        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
        subject = headers.get('Subject', '')
        body = message_to_text(msg)
        if not is_application_email(subject, body):
            continue
        fields = extract_fields(subject, body)
        row = {'message_id': m['id'], 'subject': subject, 'company': fields.get('company'), 'title': fields.get('title'), 'job_id': fields.get('job_id')}
        rows.append(row)
    out = 'gmail_applications_export.csv'
    keys = ['message_id','subject','company','title','job_id']
    with open(out,'w',newline='',encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} parsed rows to {out}")

if __name__ == '__main__':
    main()
