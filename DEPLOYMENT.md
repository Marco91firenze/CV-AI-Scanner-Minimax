# Deployment Guide — AI CV Scanner

This guide covers **MongoDB Atlas**, **S3-compatible object storage** (AWS S3, Cloudflare R2, etc.), **OpenAI API**, Stripe (live), backend hosting (Railway or Render), and frontend hosting (Vercel). **No Microsoft Azure subscription is required.**

---

## 1. MongoDB Atlas (database)

1. [MongoDB Atlas](https://www.mongodb.com/atlas) → **Create** a cluster (e.g. **M0** free tier) in an **EU** region (e.g. Frankfurt / Dublin).
2. **Database Access** → create a DB user (username + password).
3. **Network Access** → allow your backend host IPs, or **0.0.0.0/0** for quick start (tighten for production).
4. **Database** → **Connect** → **Drivers** → copy the **connection string** (`mongodb+srv://...`).
5. Set in backend env:
   - `MONGODB_URI` — full URI with user/password substituted.
   - `MONGODB_DATABASE` — e.g. `ai_cv_scanner` (collections `companies`, `jobs`, `cvs`, `transactions` are created automatically on first run with indexes).

---

## 2. Object storage (S3-compatible)

Create a **private** bucket in an **EU** region (or EU-capable provider).

**AWS S3:** create bucket (e.g. `eu-central-1`), IAM user with `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket` on that bucket. Set:

- `S3_BUCKET`
- `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`
- `S3_REGION` (e.g. `eu-central-1`)
- Leave `S3_ENDPOINT_URL` empty (default AWS endpoint).

**Cloudflare R2:** create bucket + API token with object read/write. Set:

- `S3_BUCKET`
- `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`
- `S3_ENDPOINT_URL` = `https://<account_id>.r2.cloudflarestorage.com`
- `S3_REGION` = `auto` (optional; defaults to `auto` when an endpoint URL is set).

The app **encrypts file bytes before upload**; the bucket stores ciphertext only.

---

## 3. OpenAI API

1. [OpenAI Platform](https://platform.openai.com/) → API keys → create a **secret key**.
2. Ensure billing is enabled and your org allows the model you pick (default **`gpt-4o-mini`**).
3. Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` (default `gpt-4o-mini`).

Review OpenAI’s data processing / retention settings so they match your DPA and customer commitments.

---

## 4. Encryption key

Generate a 32-byte base64 key for `CV_ENCRYPTION_KEY`:

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

**Back this up.** Losing it means encrypted blobs cannot be decrypted.

---

## 5. Stripe setup (Live)

1. In Stripe Dashboard, use **Live mode**.
2. **Products / Prices** — one-time **€50** (100 credits) and **€300** (1000 credits); copy each live **`price_...`** ID into `STRIPE_PRICE_STARTER` / `STRIPE_PRICE_PROFESSIONAL`.
3. **Developers → API keys** — copy **Secret key** `sk_live_...` → `STRIPE_SECRET_KEY`.
4. After the backend has a public URL: **Webhooks** → add endpoint `https://YOUR-BACKEND/api/stripe/webhook`, event **`checkout.session.completed`**, copy **Signing secret** `whsec_...` → `STRIPE_WEBHOOK_SECRET`.

The checkout session stores `metadata.company_id` and `metadata.credits`; the webhook credits the company on successful payment.

---

## 6. Backend deployment

### 6.1 Railway (recommended)

1. New Project → Deploy from GitHub (or CLI).
2. **Root directory:** `backend`
3. **Start command:**

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

4. Add **all** variables from `backend/.env.example` in the Railway Variables UI.
5. Note the public URL (for example `https://yourapp.up.railway.app`).

### 6.2 Render

1. New **Web Service** → connect repo.
2. **Root Directory:** `backend`
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables from `backend/.env.example`.

---

## 7. Frontend deployment (Vercel + GitHub)

1. Push the repository to GitHub.
2. **Import** the repo in Vercel.
3. **Root Directory:** `frontend`
4. **Framework preset:** Next.js
5. **Environment variable:** `NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-URL` (no trailing slash)
6. Deploy.

Set backend `PUBLIC_APP_URL` to your Vercel production URL so Stripe success/cancel redirects land on your site.

---

## 8. Environment variables (checklist)

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | HS256 signing secret |
| `CORS_ORIGINS` | Comma-separated allowed web origins |
| `MONGODB_URI` / `MONGODB_DATABASE` | Atlas connection string + database name |
| `S3_*` | Bucket, keys, optional endpoint + region |
| `CV_ENCRYPTION_KEY` | Base64 32-byte AES key |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Chat Completions for ranking |
| `STRIPE_*` | Secret key, webhook secret, price IDs |
| `STARTER_CREDITS` / `PROFESSIONAL_CREDITS` | Must match commercial terms (100 / 1000) |
| `PUBLIC_APP_URL` | Frontend URL for Stripe redirects |

### Frontend (`frontend/.env.local` or Vercel env)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Public backend base URL |

---

## 9. Post-deployment checklist

- [ ] MongoDB Atlas cluster reachable from backend (network allowlist); indexes created on first boot.
- [ ] S3/R2 bucket exists; backend can upload, read, and delete a test object.
- [ ] OpenAI API returns a successful chat completion from the server.
- [ ] Register → DPA accept → create job → upload PDF → score appears; blob deleted after rank.
- [ ] Stripe **live** checkout completes; webhook fires; `credits` increments.
- [ ] `CORS_ORIGINS` includes your Vercel domain.
- [ ] `PUBLIC_APP_URL` matches Vercel production URL.
- [ ] HTTPS only in production; rotate `JWT_SECRET` and `CV_ENCRYPTION_KEY` if leaked.
- [ ] Legal: replace template contact details and have counsel review `backend/LEGAL` and `frontend/content/legal` copies.

---

## 10. GitHub Actions (CI only)

The repository uses **`.github/workflows/ci.yml`**: it installs backend dependencies, compiles Python files, and runs `next lint` on the frontend. It does **not** deploy anywhere. Backend and frontend are deployed via **Railway/Render** and **Vercel** as described above.

If you previously connected this repo to **Azure App Service**, you can delete unused GitHub secrets such as `AZUREAPPSERVICE_CLIENTID_*`, `AZUREAPPSERVICE_TENANTID_*`, and `AZUREAPPSERVICE_SUBSCRIPTIONID_*` so nothing points at Azure anymore.

---

## 11. Monorepo note

Legal markdown is duplicated under `backend/LEGAL` (spec) and `frontend/content/legal` (so Next.js can read it when the Vercel root is `frontend`). Keep them in sync when you edit policies.
