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
    force_new_token = False  # Set to True to force new token generation
    
    # Try to load existing token
    if os.path.exists('token.pickle') and not force_new_token:
        try:
            with open('token.pickle','rb') as f:
                creds = pickle.load(f)
        except (pickle.UnpicklingError, EOFError, AttributeError):
            print("Warning: Corrupted token.pickle file. Will create a new token.")
            creds = None
    
    # Check if we need to refresh or create a new token
    if not creds or not creds.valid:
        # Try to refresh first if we have a valid refresh token
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("Refreshed existing token successfully.")
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print("Will generate a new token instead.")
                creds = None  # Force new token generation
        
        # If refresh failed or no token exists, create a new one
        if not creds:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError('credentials.json not found - create OAuth client in Google Cloud Console.')
            
            print("Launching browser for OAuth flow... (you may need to log in and authorize)")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            print("New token obtained successfully.")
        
        # Save the refreshed or new token
        with open('token.pickle','wb') as f:
            pickle.dump(creds, f)
            print(f"Saved token to {os.path.abspath('token.pickle')}")
    
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

def clean_company_name(name):
    """Clean and normalize company names"""
    if not name:
        return None
        
    # Remove trailing/leading whitespace
    name = name.strip()
    
    # Remove trailing punctuation
    name = re.sub(r'[.,;:!?]+$', '', name).strip()
    
    # Remove common trailing phrases
    for phrase in [" team", " careers", " recruiting", " talent acquisition", " hr", " hiring"]:
        if name.lower().endswith(phrase):
            name = name[:-(len(phrase))].strip()
            
    return name

def extract_fields(subject, body):
    """Extract job_id, company name, and title from email subject and body"""
    result = {'company': None, 'title': None, 'job_id': None}
    
    # Extract job ID using regex
    m = job_id_regex.search(body) or job_id_regex.search(subject or "")
    if m:
        result['job_id'] = m.group(1).strip()
    
    # Try multiple company extraction strategies
    
    # 1. Look for "Title - Company" pattern in subject
    m2 = re.search(r"(?P<title>.+?)\\s*(?:-|:|\\|)\\s*(?P<company>.+)", subject or "", re.I)
    if m2:
        result['title'] = m2.group('title').strip()
        result['company'] = clean_company_name(m2.group('company'))
    
    # 2. Look for explicit "Thank you for applying to X" patterns
    if not result['company']:
        thank_you_patterns = [
            r"thank you for (?:applying to|your application to|submitting your application to)\s+(?P<company>[^\.!,\n\r]+)",
            r"thanks for applying to\s+(?P<company>[^\.!,\n\r]+)",
            r"application received.*?(?:at|for|from)\s+(?P<company>[^\.!,\n\r]+)",
            r"your application (?:at|to|for)\s+(?P<company>[^\.!,\n\r]+)(?:\s+has been received|is being reviewed)",
            r"received your application.*?(?:at|for|with)\s+(?P<company>[^\.!,\n\r]+)"
        ]
        
        # Try each pattern on subject and body
        for pattern in thank_you_patterns:
            regex = re.compile(pattern, re.I | re.DOTALL)
            
            # Check subject first (usually cleaner)
            m = regex.search(subject)
            if m:
                result['company'] = clean_company_name(m.group('company'))
                break
                
            # Then try body
            m = regex.search(body)
            if m:
                result['company'] = clean_company_name(m.group('company'))
                break
    
    # 3. Look for Company: field in body
    if not result['company']:
        m3 = re.search(r"Company[:\\-]\\s*(?P<c>[^\\n\\r]+)", body or "", re.I)
        if m3:
            result['company'] = clean_company_name(m3.group('c'))
    
    # 4. Special case: extract from Gmail subject format
    if not result['company'] and subject and ":" in subject:
        parts = subject.split(":", 1)
        if len(parts) == 2 and len(parts[0].split()) <= 4:  # Company name likely in first part
            company_candidate = clean_company_name(parts[0])
            # Only use if it looks like a company name (not "Re", "Fwd", etc.)
            if company_candidate and len(company_candidate) > 2 and company_candidate.lower() not in ["re", "fwd", "fw"]:
                result['company'] = company_candidate
    
    return result

def main():
    try:
        # Try to authenticate
        print("Authenticating with Gmail API...")
        service = gmail_authenticate()
        
        # Build search query
        query = 'newer_than:365d OR subject:("application" OR "applied" OR "thank you for applying")'
        print(f"Searching Gmail with query: {query}")
        
        # Search for messages
        results = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
        messages = results.get('messages', [])
        
        if not messages:
            print("No matching messages found. Try broadening your search query.")
            return
            
        print(f"Found {len(messages)} candidate messages.")
        
        # Process each message
        rows = []
        parsed_count = 0
        for i, m in enumerate(messages):
            if i > 0 and i % 20 == 0:
                print(f"Processed {i}/{len(messages)} messages...")
                
            try:
                # Get full message
                msg = service.users().messages().get(userId='me', id=m['id'], format='full').execute()
                headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
                subject = headers.get('Subject', '')
                body = message_to_text(msg)
                
                # Skip if not an application email
                if not is_application_email(subject, body):
                    continue
                    
                # Parse and extract fields
                fields = extract_fields(subject, body)
                row = {
                    'message_id': m['id'], 
                    'subject': subject, 
                    'company': fields.get('company'), 
                    'title': fields.get('title'), 
                    'job_id': fields.get('job_id')
                }
                rows.append(row)
                parsed_count += 1
                
            except Exception as e:
                print(f"Error processing message {m['id']}: {e}")
                continue
        
        # Write results to CSV
        out = 'gmail_applications_export.csv'
        keys = ['message_id','subject','company','title','job_id']
        with open(out,'w',newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"Wrote {len(rows)} parsed rows to {out}")
        
        # Report parsing success rate
        if messages:
            print(f"Summary: Found {parsed_count} application emails out of {len(messages)} messages ({parsed_count/len(messages)*100:.1f}%)")
            
        # Company extraction report
        with_company = sum(1 for r in rows if r.get('company'))
        if rows:
            print(f"Company extraction: {with_company}/{len(rows)} ({with_company/len(rows)*100:.1f}%)")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nTo fix this issue:")
        print("1. Go to Google Cloud Console (https://console.cloud.google.com)")
        print("2. Create a project and enable the Gmail API")
        print("3. Create OAuth 2.0 Client ID (Desktop application)")
        print("4. Download the JSON and save as 'credentials.json' in this directory")
        
    except Exception as e:
        print(f"Error: {e}")
        
        # Special handling for common OAuth issues
        if "invalid_grant" in str(e).lower():
            print("\nAuthentication error detected. To fix:")
            print("1. Delete the token.pickle file")
            print("2. Run this script again")
            print("3. Follow the browser prompts to authenticate")
            
            # Offer to delete token automatically
            try:
                if os.path.exists('token.pickle'):
                    user_input = input("Would you like to delete token.pickle now? (y/n): ")
                    if user_input.lower() == 'y':
                        os.remove('token.pickle')
                        print("token.pickle deleted. Run the script again to re-authenticate.")
            except Exception:
                print("Could not delete token.pickle. Please delete it manually.")
                
        elif "credentials" in str(e).lower():
            print("\nCredentials issue detected. Make sure:")
            print("1. credentials.json is in the current directory")
            print("2. The OAuth client in Google Cloud Console has the correct redirect URI")
            print("3. The Gmail API is enabled for your project")

if __name__ == '__main__':
    main()
