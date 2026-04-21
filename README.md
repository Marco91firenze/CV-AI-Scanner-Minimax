# AI CV Scanner

GDPR-compliant B2B SaaS for uploading CVs and ranking candidates against job requirements using Azure OpenAI. Frontend: Next.js 14 on Vercel. Backend: FastAPI on Railway/Render.

## Project location

The scaffold is created under **`ai-cv-scanner/`** in this workspace. To match `~/ai-cv-scanner` on your machine, copy or move the folder to your home directory (for example `C:\Users\<you>\ai-cv-scanner` on Windows).

## Structure

- `frontend/` — Next.js App Router, TypeScript, Tailwind
- `backend/` — FastAPI, Cosmos DB, Blob Storage, Stripe, JWT auth

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
# Fill .env with Azure, Stripe, JWT secret
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Trial & credits

- First **10 CVs** per company are free forever (no card).
- After that, credits are required (Starter: €50 / 100 credits, Professional: €300 / 1000 credits).

## Legal

See `backend/LEGAL/` for DPA, Terms, and Privacy Policy templates. Companies must accept the DPA before uploading CVs.

## Deploy

See [DEPLOYMENT.md](./DEPLOYMENT.md).

## Legal copy

Policy text lives in `backend/LEGAL/` and is mirrored in `frontend/content/legal/` for Next.js server rendering on Vercel. Update both copies together.
