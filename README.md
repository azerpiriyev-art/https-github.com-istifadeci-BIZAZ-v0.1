# BIZAZ вЂ” B2B Business Platform

Version: **v0.1 Foundation**
Target: Azerbaijan B2B market
Stack: Next.js + React + TypeScript + Tailwind CSS / FastAPI + Python / PostgreSQL / REST / JWT + RBAC

## Product flow
Register в†’ Company в†’ Product в†’ Purchase Request в†’ Supplier Offer в†’ Offer Comparison в†’ Supplier Selection в†’ Order в†’ Payment в†’ Delivery в†’ Review

## v0.1 status
- Project Foundation: рџџў Ready
- Business Model: рџџЎ Defined at foundation level; commercial/legal decisions remain gated
- MVP Scope: рџџЎ Drafted
- Technical Architecture: рџџў Ready
- Database: рџџў Foundation migration ready and tested by static checks
- Backend/API: рџџЎ Foundation skeleton implemented
- Frontend: рџџЎ Foundation shell implemented

## Local run (Windows 11)
Prerequisites: Git, Docker Desktop, Node.js 20+, Python 3.12+.

1. `docker compose up -d db`
2. Backend: `cd backend && python -m venv .venv && .venv\\Scripts\\activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
3. Frontend: `cd frontend && npm install && npm run dev`
4. Open `http://localhost:3000`; API docs: `http://localhost:8000/docs`.

## Environment
Copy `.env.example` to `.env` and change secrets before any non-local deployment.

## Quality gate
A module is **Ready** only after implementation + automated tests + integration checks + security review. No production secrets are committed.
