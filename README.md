# Internship Application Organizer

This repository contains:
// Backend (FastAPI) + Gmail parser + React frontend (minimal) + TF-IDF training script

## Structure
- backend/app.py : FastAPI backend (SQLite)
- gmail_parser.py : Gmail ingestion script (OAuth)
- frontend/ : Minimal React scaffold (src/App.jsx, etc.)
- scripts/train_classifier.py : Train TF-IDF + LogisticRegression classifier
- data/sample_labels.csv : Small labeled dataset example
- requirements.txt, requirements_gmail.txt : Install dependencies for backend and Gmail script

## Quick start (dev)
1. Backend:
   - python -m venv venv && source venv/bin/activate
   - pip install -r requirements.txt
   - cd backend && uvicorn app:app --reload
   - Open http://127.0.0.1:8000

2. Gmail parser:
   - pip install -r requirements_gmail.txt
   - Place your credentials.json (OAuth Desktop client) in repo root
   - python gmail_parser.py

3. Frontend (optional):
   - cd frontend
   - npm install
   - npm start

## TF-IDF classifier (optional)
- Edit/expand data/sample_labels.csv with real examples (application vs non-application)
- pip install scikit-learn pandas
- python scripts/train_classifier.py

## Notes
- This is a personal tool: respect user privacy and Google's OAuth scopes.
- For production, store tokens securely and encrypt attachment data.
- See the included Word doc (documentation.docx) for a full workplan and flowcharts.
