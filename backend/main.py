"""
AI CV Scanner — FastAPI backend.
GDPR-oriented: tenant isolation via MongoDB queries (company_id), ephemeral CV blobs, DPA gate.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import stripe
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from lib.mongo import col_companies, col_cvs, col_jobs, col_transactions, connect
from services.extraction import extract_text_from_bytes
from services.ranking import rank_cv
from services.storage import ObjectStorage, delete_cv

FREE_CV_LIMIT = 10

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(10080, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: str = Field("http://localhost:3000", alias="CORS_ORIGINS")

    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_database: str = Field("ai_cv_scanner", alias="MONGODB_DATABASE")

    s3_bucket: str = Field(..., alias="S3_BUCKET")
    s3_access_key_id: str = Field(..., alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(..., alias="S3_SECRET_ACCESS_KEY")
    s3_endpoint_url: str | None = Field(None, alias="S3_ENDPOINT_URL")
    s3_region: str | None = Field(None, alias="S3_REGION")
    cv_encryption_key: str = Field(..., alias="CV_ENCRYPTION_KEY")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")

    stripe_secret_key: str = Field(..., alias="STRIPE_SECRET_KEY")
    # Empty until Stripe webhook is created; /health can boot without it.
    stripe_webhook_secret: str = Field("", alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_starter: str = Field(..., alias="STRIPE_PRICE_STARTER")
    stripe_price_professional: str = Field(..., alias="STRIPE_PRICE_PROFESSIONAL")
    starter_credits: int = Field(100, alias="STARTER_CREDITS")
    professional_credits: int = Field(1000, alias="PROFESSIONAL_CREDITS")
    public_app_url: str = Field("http://localhost:3000", alias="PUBLIC_APP_URL")


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
stripe.api_key = settings.stripe_secret_key

_init_lock = threading.Lock()
_backend_ready = False
_mongo_client: MongoClient | None = None
_db: Database | None = None
_companies: Any = None
_jobs: Any = None
_cvs: Any = None
_transactions: Any = None
_storage: ObjectStorage | None = None


def _ensure_backend() -> None:
    """Connect to MongoDB and S3 on first real request so /health can pass Railway before Atlas is reachable."""
    global _backend_ready, _mongo_client, _db, _companies, _jobs, _cvs, _transactions, _storage
    if _backend_ready:
        return
    with _init_lock:
        if _backend_ready:
            return
        _mongo_client, _db = connect(settings.mongodb_uri, settings.mongodb_database)
        _companies = col_companies(_db)
        _jobs = col_jobs(_db)
        _cvs = col_cvs(_db)
        _transactions = col_transactions(_db)
        _storage = ObjectStorage(
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            encryption_key_b64=settings.cv_encryption_key,
        )
        _storage.ensure_bucket_exists()
        _backend_ready = True


app = FastAPI(title="AI CV Scanner API")


@app.middleware("http")
async def lazy_init_backend(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if path != "/health":
        _ensure_backend()
    return await call_next(request)


def _allowed_cors_origins() -> list[str]:
    """Merge CORS_ORIGINS with PUBLIC_APP_URL so production works if only the latter is set."""
    seen: set[str] = set()
    out: list[str] = []
    for o in (x.strip() for x in settings.cors_origins.split(",") if x.strip()):
        if o not in seen:
            seen.add(o)
            out.append(o)
    pub = settings.public_app_url.rstrip("/")
    if pub and pub not in seen:
        out.append(pub)
    return out


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(sub: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_token_data(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        return sub
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def load_company(company_id: str) -> dict[str, Any]:
    doc = _companies.find_one({"id": company_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return doc


async def get_current_company(company_id: Annotated[str, Depends(get_token_data)]) -> dict[str, Any]:
    return load_company(company_id)


def require_dpa(company: dict[str, Any]) -> None:
    if not company.get("dpa_accepted"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Data Processing Agreement must be accepted before using this feature.",
        )


def trial_info(company: dict[str, Any]) -> dict[str, Any]:
    processed = int(company.get("cvs_processed", 0))
    free_used = min(processed, FREE_CV_LIMIT)
    free_remaining = max(0, FREE_CV_LIMIT - processed)
    is_trial_active = processed < FREE_CV_LIMIT
    return {
        "credits": int(company.get("credits", 0)),
        "free_cvs_remaining": free_remaining,
        "free_cvs_used": free_used,
        "free_cvs_total": FREE_CV_LIMIT,
        "is_trial_active": is_trial_active,
        "cvs_processed": processed,
        "dpa_accepted": bool(company.get("dpa_accepted")),
    }


def replace_company(doc: dict[str, Any]) -> None:
    _companies.replace_one({"id": doc["id"]}, doc)


# --- Pydantic models ---


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    company_name: str = Field(min_length=2, max_length=200)


class CompanyPublic(BaseModel):
    id: str
    email: EmailStr
    company_name: str
    dpa_accepted: bool
    credits: int
    cvs_processed: int


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    requirements: str = Field(min_length=1, max_length=50_000)


class JobOut(BaseModel):
    id: str
    company_id: str
    title: str
    requirements: str
    created_at: str


class CreditPurchaseBody(BaseModel):
    plan: str = Field(pattern="^(starter|professional)$")


def _reverse_cv_consumption(company: dict[str, Any], used_free_slot: bool) -> None:
    company["cvs_processed"] = max(0, int(company.get("cvs_processed", 0)) - 1)
    if not used_free_slot:
        company["credits"] = int(company.get("credits", 0)) + 1
    replace_company(company)


def process_cv_ranking(
    company_id: str,
    cv_id: str,
    used_free_slot: bool,
) -> None:
    company = load_company(company_id)
    cv = _cvs.find_one({"id": cv_id, "company_id": company_id})
    if not cv:
        return
    blob_path = cv.get("blob_path")
    if not blob_path:
        return
    try:
        raw = _storage.download_cv(blob_path)
        filename = cv.get("filename", "cv.pdf")
        text = extract_text_from_bytes(raw, filename)
        job = _jobs.find_one({"id": cv["job_id"], "company_id": company_id})
        if not job:
            raise RuntimeError("Job not found")
        result = rank_cv(
            text,
            job.get("title", ""),
            job.get("requirements", ""),
            settings.openai_api_key,
            settings.openai_model,
        )
        cv["status"] = "ranked"
        cv["score"] = result["score"]
        cv["reasoning"] = result["reasoning"]
        cv["blob_path"] = None
        cv["updated_at"] = utcnow()
        _cvs.replace_one({"id": cv_id, "company_id": company_id}, cv)
        delete_cv(_storage, blob_path)
    except Exception as exc:
        cv["status"] = "error"
        cv["error_message"] = str(exc)[:2000]
        cv["updated_at"] = utcnow()
        _cvs.replace_one({"id": cv_id, "company_id": company_id}, cv)
        if blob_path:
            delete_cv(_storage, blob_path)
        _reverse_cv_consumption(company, used_free_slot)


# --- Auth ---


@app.post("/auth/register", response_model=dict[str, Any])
def auth_register(body: RegisterBody):
    cid = str(uuid.uuid4())
    email_norm = body.email.lower().strip()
    if _companies.find_one({"email": email_norm}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    doc = {
        "id": cid,
        "email": email_norm,
        "password_hash": hash_password(body.password),
        "company_name": body.company_name.strip(),
        "dpa_accepted": False,
        "dpa_accepted_at": None,
        "credits": 0,
        "cvs_processed": 0,
        "created_at": utcnow(),
    }
    try:
        _companies.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")
    token = create_access_token(cid)
    return {"access_token": token, "token_type": "bearer", **trial_info(doc)}


@app.post("/auth/login")
def auth_login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    email = form.username.lower().strip()
    found = _companies.find_one({"email": email})
    if not found or not verify_password(form.password, found["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token = create_access_token(found["id"])
    return {"access_token": token, "token_type": "bearer", **trial_info(found)}


@app.get("/auth/me")
def auth_me(company: Annotated[dict[str, Any], Depends(get_current_company)]):
    return {
        "id": company["id"],
        "email": company["email"],
        "company_name": company["company_name"],
        **trial_info(company),
    }


# --- DPA ---


@app.post("/dpa/accept")
def dpa_accept(company: Annotated[dict[str, Any], Depends(get_current_company)]):
    company["dpa_accepted"] = True
    company["dpa_accepted_at"] = utcnow()
    replace_company(company)
    return {"ok": True, **trial_info(company)}


# --- Pricing info ---


@app.get("/pricing")
def pricing_public():
    return {
        "free_cvs": FREE_CV_LIMIT,
        "description": "First 10 CVs are always free",
        "plans": [
            {"id": "starter", "name": "Starter", "price_eur": 50, "credits": 100},
            {"id": "professional", "name": "Professional", "price_eur": 300, "credits": 1000},
        ],
    }


# --- Credits ---


@app.get("/credits/balance")
def credits_balance(company: Annotated[dict[str, Any], Depends(get_current_company)]):
    return trial_info(company)


@app.post("/credits/purchase")
def credits_purchase(
    body: CreditPurchaseBody,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    if body.plan == "starter":
        price = settings.stripe_price_starter
        credits = settings.starter_credits
    else:
        price = settings.stripe_price_professional
        credits = settings.professional_credits
    base = settings.public_app_url.rstrip("/")
    checkout = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price, "quantity": 1}],
        success_url=f"{base}/dashboard?paid=1",
        cancel_url=f"{base}/pricing?cancel=1",
        client_reference_id=company["id"],
        metadata={"company_id": company["id"], "credits": str(credits)},
    )
    return {"checkout_url": checkout.url, "session_id": checkout.id}


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    if not settings.stripe_webhook_secret.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stripe webhook signing secret is not set. Add STRIPE_WEBHOOK_SECRET in Railway, then redeploy.",
        )
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(400, "Missing stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig, secret=settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata") or {}
        cid = meta.get("company_id") or session.get("client_reference_id")
        credits_add = int(meta.get("credits", 0))
        if cid and credits_add > 0:
            company = load_company(cid)
            company["credits"] = int(company.get("credits", 0)) + credits_add
            replace_company(company)
            tx = {
                "id": str(uuid.uuid4()),
                "company_id": cid,
                "stripe_session_id": session.get("id"),
                "credits_added": credits_add,
                "created_at": utcnow(),
            }
            _transactions.insert_one(tx)
    return {"received": True}


# --- Jobs ---


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(company: Annotated[dict[str, Any], Depends(get_current_company)]):
    require_dpa(company)
    cid = company["id"]
    items = list(_jobs.find({"company_id": cid}).sort("created_at", -1))
    return [
        JobOut(
            id=i["id"],
            company_id=i["company_id"],
            title=i["title"],
            requirements=i["requirements"],
            created_at=i["created_at"],
        )
        for i in items
    ]


@app.post("/jobs", response_model=JobOut)
def create_job(
    body: JobCreate,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    require_dpa(company)
    jid = str(uuid.uuid4())
    cid = company["id"]
    doc = {
        "id": jid,
        "company_id": cid,
        "title": body.title.strip(),
        "requirements": body.requirements.strip(),
        "created_at": utcnow(),
    }
    _jobs.insert_one(doc)
    return JobOut(
        id=jid,
        company_id=cid,
        title=doc["title"],
        requirements=doc["requirements"],
        created_at=doc["created_at"],
    )


@app.delete("/jobs/{job_id}")
def delete_job(
    job_id: str,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    require_dpa(company)
    cid = company["id"]
    if not _jobs.find_one({"id": job_id, "company_id": cid}):
        raise HTTPException(404, "Job not found")
    cvs = list(_cvs.find({"company_id": cid, "job_id": job_id}))
    company_fresh = load_company(cid)
    refunds = 0
    trial_reversals = 0
    for cv in cvs:
        if cv.get("status") != "ranked":
            if cv.get("used_free_slot"):
                trial_reversals += 1
            else:
                refunds += 1
        bp = cv.get("blob_path")
        if bp:
            delete_cv(_storage, bp)
        _cvs.delete_one({"id": cv["id"], "company_id": cid})

    company_fresh["credits"] = int(company_fresh.get("credits", 0)) + refunds
    company_fresh["cvs_processed"] = max(
        0, int(company_fresh.get("cvs_processed", 0)) - refunds - trial_reversals
    )
    replace_company(company_fresh)
    _jobs.delete_one({"id": job_id, "company_id": cid})
    _storage.delete_all_for_job(cid, job_id)
    return {"ok": True, "credits_refunded": refunds, "trial_slots_restored": trial_reversals}


@app.post("/jobs/{job_id}/cvs")
async def upload_cv(
    job_id: str,
    background_tasks: BackgroundTasks,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
    file: UploadFile = File(...),
):
    require_dpa(company)
    cid = company["id"]
    if not _jobs.find_one({"id": job_id, "company_id": cid}):
        raise HTTPException(404, "Job not found")

    company_fresh = load_company(cid)
    processed = int(company_fresh.get("cvs_processed", 0))
    credits = int(company_fresh.get("credits", 0))

    if processed < FREE_CV_LIMIT:
        used_free_slot = True
        company_fresh["cvs_processed"] = processed + 1
    elif credits > 0:
        used_free_slot = False
        company_fresh["credits"] = credits - 1
        company_fresh["cvs_processed"] = processed + 1
    else:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "No credits remaining. Trial used (10 free CVs). Please purchase credits to continue.",
        )
    replace_company(company_fresh)

    raw = await file.read()
    if not raw:
        _reverse_cv_consumption(load_company(cid), used_free_slot)
        raise HTTPException(400, "Empty file")

    fname = file.filename or "cv.pdf"
    safe_name = fname.replace("\\", "_").replace("/", "_")[:200]
    blob_key = f"{uuid.uuid4()}_{safe_name}"

    try:
        path = _storage.upload_cv(cid, job_id, blob_key, raw)
    except Exception:
        _reverse_cv_consumption(load_company(cid), used_free_slot)
        raise

    cv_id = str(uuid.uuid4())
    cv_doc = {
        "id": cv_id,
        "company_id": cid,
        "job_id": job_id,
        "filename": safe_name,
        "blob_path": path,
        "status": "ranking",
        "score": None,
        "reasoning": None,
        "error_message": None,
        "used_free_slot": used_free_slot,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    _cvs.insert_one(cv_doc)
    background_tasks.add_task(process_cv_ranking, cid, cv_id, used_free_slot)
    return {"id": cv_id, "status": "ranking", "filename": safe_name}


@app.get("/jobs/{job_id}/cvs")
def list_cvs(
    job_id: str,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    require_dpa(company)
    cid = company["id"]
    if not _jobs.find_one({"id": job_id, "company_id": cid}):
        raise HTTPException(404, "Job not found")
    items = list(_cvs.find({"company_id": cid, "job_id": job_id}))

    def sort_key(i: dict[str, Any]) -> tuple[int, str]:
        sc = i.get("score")
        if sc is None:
            return (-1, i.get("created_at", ""))
        return (-int(sc), i.get("created_at", ""))

    items_sorted = sorted(items, key=sort_key)
    note = (
        "All CVs displayed. Ranking score is for prioritization only, not exclusion. "
        "GDPR Article 22 compliant."
    )
    return {
        "note": note,
        "cvs": [
            {
                "id": i["id"],
                "filename": i.get("filename"),
                "status": i.get("status"),
                "score": i.get("score"),
                "reasoning": i.get("reasoning"),
                "error_message": i.get("error_message"),
                "created_at": i.get("created_at"),
            }
            for i in items_sorted
        ],
    }


@app.delete("/account")
def delete_account(company: Annotated[dict[str, Any], Depends(get_current_company)]):
    cid = company["id"]
    _storage.delete_all_for_company(cid)
    _cvs.delete_many({"company_id": cid})
    _jobs.delete_many({"company_id": cid})
    _transactions.delete_many({"company_id": cid})
    _companies.delete_one({"id": cid})
    return {"ok": True, "message": "Account and associated data deletion initiated."}


@app.get("/health")
def health():
    return {"status": "ok"}


class LoginJson(BaseModel):
    email: EmailStr
    password: str


@app.post("/auth/login/json")
def auth_login_json(body: LoginJson):
    email = body.email.lower().strip()
    found = _companies.find_one({"email": email})
    if not found or not verify_password(body.password, found["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token = create_access_token(found["id"])
    return {"access_token": token, "token_type": "bearer", **trial_info(found)}
