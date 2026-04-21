# Deployment Guide — AI CV Scanner

This guide covers Azure (Cosmos DB, Blob Storage, Azure OpenAI), Stripe, backend hosting (Railway or Render), and frontend hosting (Vercel).

---

## 1. Azure setup

### 1.1 Resource group and region

Create resources in an **EU region** (for example `westeurope`) to align with data residency commitments.

```bash
az group create --name rg-ai-cv-scanner --location westeurope
```

### 1.2 Cosmos DB (SQL API)

```bash
az cosmosdb create \
  --name cosmos-aicv-YOURNAME \
  --resource-group rg-ai-cv-scanner \
  --default-consistency-level Session \
  --locations regionName=westeurope failoverPriority=0 isZoneRedundant=False

az cosmosdb sql database create \
  --account-name cosmos-aicv-YOURNAME \
  --resource-group rg-ai-cv-scanner \
  --name ai_cv_scanner
```

Create containers (partition keys must match the backend):

```bash
# companies: partition key /id
az cosmosdb sql container create \
  --account-name cosmos-aicv-YOURNAME \
  --resource-group rg-ai-cv-scanner \
  --database-name ai_cv_scanner \
  --name companies \
  --partition-key-path "/id"

# jobs, cvs, transactions: partition key /company_id
for c in jobs cvs transactions; do
  az cosmosdb sql container create \
    --account-name cosmos-aicv-YOURNAME \
    --resource-group rg-ai-cv-scanner \
    --database-name ai_cv_scanner \
    --name "$c" \
    --partition-key-path "/company_id"
done
```

Copy **URI** and **PRIMARY KEY** from the Azure Portal → Cosmos DB → Keys. Set:

- `COSMOS_ENDPOINT`
- `COSMOS_KEY`
- `COSMOS_DATABASE=ai_cv_scanner` (or your chosen DB name, matching `.env`)

The backend also calls `create_container_if_not_exists` on startup for development convenience; production should use IaC or the CLI above.

### 1.3 Blob Storage

```bash
az storage account create \
  --name staicvYOURNAME \
  --resource-group rg-ai-cv-scanner \
  --location westeurope \
  --sku Standard_LRS

az storage container create \
  --account-name staicvYOURNAME \
  --name cvs \
  --auth-mode login
```

Create a **connection string** in the Portal (Access keys) and set `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_STORAGE_CONTAINER=cvs`.

### 1.4 Azure OpenAI (gpt-4o-mini)

In Azure AI Foundry / Azure OpenAI, create a resource in **EU**, deploy **`gpt-4o-mini`**, then set:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION` (for example `2024-02-15-preview` or your resource’s supported version)
- `AZURE_OPENAI_DEPLOYMENT` (deployment name, often `gpt-4o-mini`)

Confirm **content filtering** and **data processing** settings match your DPA commitments.

### 1.5 Encryption key

Generate a 32-byte base64 key for `CV_ENCRYPTION_KEY`:

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

---

## 2. Stripe setup

1. Create a Stripe account (test mode for staging).
2. **Products / Prices**
   - Product **Starter** — one-time **€50** price → note `price_...` ID.
   - Product **Professional** — one-time **€300** price → note `price_...` ID.
3. Map IDs in backend `.env`:
   - `STRIPE_PRICE_STARTER`
   - `STRIPE_PRICE_PROFESSIONAL`
4. **Webhook**
   - Endpoint URL: `https://YOUR-BACKEND/api/stripe/webhook`
   - Events: `checkout.session.completed`
   - Copy signing secret → `STRIPE_WEBHOOK_SECRET`
5. **Secret key** → `STRIPE_SECRET_KEY`

The checkout session stores `metadata.company_id` and `metadata.credits`; the webhook credits the company on successful payment.

---

## 3. Backend deployment

### 3.1 Railway (recommended)

1. New Project → Deploy from GitHub (or CLI).
2. **Root directory:** `backend`
3. **Start command:**

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

4. Add **all** variables from `backend/.env.example` in the Railway Variables UI.
5. Note the public URL (for example `https://yourapp.up.railway.app`).

### 3.2 Render

1. New **Web Service** → connect repo.
2. **Root Directory:** `backend`
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables from `backend/.env.example`.

---

## 4. Frontend deployment (Vercel + GitHub)

1. Push the repository to GitHub.
2. **Import** the repo in Vercel.
3. **Root Directory:** `frontend`
4. **Framework preset:** Next.js
5. **Environment variable:** `NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-URL` (no trailing slash)
6. Deploy.

GitHub Desktop workflow: commit from Desktop → push → Vercel auto-builds on `main`.

Set backend `PUBLIC_APP_URL` to your Vercel production URL so Stripe success/cancel redirects land on your site.

---

## 5. Environment variables (checklist)

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | HS256 signing secret |
| `CORS_ORIGINS` | Comma-separated allowed web origins |
| `COSMOS_*` | Cosmos endpoint, key, DB name, container names |
| `AZURE_STORAGE_*` | Blob connection string + container |
| `CV_ENCRYPTION_KEY` | Base64 32-byte AES key |
| `AZURE_OPENAI_*` | Endpoint, key, API version, deployment name |
| `STRIPE_*` | Secret key, webhook secret, price IDs |
| `STARTER_CREDITS` / `PROFESSIONAL_CREDITS` | Must match commercial terms (100 / 1000) |
| `PUBLIC_APP_URL` | Frontend URL for Stripe redirects |

### Frontend (`frontend/.env.local` or Vercel env)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Public backend base URL |

---

## 6. Post-deployment checklist

- [ ] Cosmos containers exist with correct **partition keys** (`/id` for companies, `/company_id` for others).
- [ ] Blob container `cvs` exists; backend can upload a test object.
- [ ] Azure OpenAI deployment answers a test chat completion from the server.
- [ ] Register → DPA accept → create job → upload PDF → score appears; blob deleted after rank.
- [ ] Stripe test checkout completes; webhook fires; `credits` increments.
- [ ] `CORS_ORIGINS` includes your Vercel domain.
- [ ] `PUBLIC_APP_URL` matches Vercel production URL.
- [ ] HTTPS only in production; rotate `JWT_SECRET` and `CV_ENCRYPTION_KEY` if leaked.
- [ ] Legal: replace template contact details and have counsel review `backend/LEGAL` and `frontend/content/legal` copies.

---

## 7. Monorepo note

Legal markdown is duplicated under `backend/LEGAL` (spec) and `frontend/content/legal` (so Next.js can read it when the Vercel root is `frontend`). Keep them in sync when you edit policies.
