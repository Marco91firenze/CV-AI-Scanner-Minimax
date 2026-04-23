"""
AI CV Scanner — FastAPI backend.
GDPR-oriented: tenant isolation via MongoDB queries (company_id), ephemeral CV blobs, DPA gate.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import bcrypt
import stripe
from botocore.exceptions import ClientError
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
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from lib.mongo import col_companies, col_cvs, col_jobs, col_transactions, connect
from services.extraction import extract_text_from_bytes
from services.ranking import rank_cv
from services.storage import ObjectStorage, delete_cv

FREE_CV_LIMIT = 10

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
logger = logging.getLogger("ai_cv_scanner")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(10080, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: str = Field("http://localhost:3000", alias="CORS_ORIGINS")
    # Allow any https://*.vercel.app origin (prod + preview URLs). Disable with CORS_ALLOW_VERCEL_APP=false.
    cors_allow_vercel_app: bool = Field(True, alias="CORS_ALLOW_VERCEL_APP")
    # Optional extra regex for custom domains, e.g. https://(www\.)?example\.com$
    cors_allow_origin_regex_extra: str = Field("", alias="CORS_ALLOW_ORIGIN_REGEX_EXTRA")

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
    # Browser uploads go directly to S3/R2 (presigned PUT); this caps size server-side at finalize.
    max_cv_upload_bytes: int = Field(55 * 1024 * 1024, alias="MAX_CV_UPLOAD_BYTES")

    @field_validator("s3_endpoint_url", mode="before")
    @classmethod
    def s3_endpoint_empty_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else None

    @field_validator("s3_region", mode="before")
    @classmethod
    def s3_region_empty_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else None

    @field_validator("s3_access_key_id", "s3_bucket", mode="before")
    @classmethod
    def strip_s3_strings(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().strip("\ufeff")
        return v

    @field_validator("s3_secret_access_key", mode="before")
    @classmethod
    def strip_s3_secret(cls, v: object) -> object:
        if isinstance(v, str):
            # Railway paste often adds newlines or BOM — breaks SigV4.
            return (
                v.strip()
                .strip("\ufeff")
                .replace("\r\n", "")
                .replace("\n", "")
                .replace("\r", "")
            )
        return v


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
stripe.api_key = settings.stripe_secret_key

_init_lock = threading.Lock()
_mongo_ready = False
_mongo_client: MongoClient | None = None
_db: Database | None = None
_companies: Any = None
_jobs: Any = None
_cvs: Any = None
_transactions: Any = None
_storage: ObjectStorage | None = None


def _ensure_mongo() -> None:
    """Connect to MongoDB on first request so /health can pass before Atlas is reachable."""
    global _mongo_ready, _mongo_client, _db, _companies, _jobs, _cvs, _transactions
    if _mongo_ready:
        return
    with _init_lock:
        if _mongo_ready:
            return
        _mongo_client, _db = connect(settings.mongodb_uri, settings.mongodb_database)
        _companies = col_companies(_db)
        _jobs = col_jobs(_db)
        _cvs = col_cvs(_db)
        _transactions = col_transactions(_db)
        _mongo_ready = True


def _ensure_storage() -> None:
    """S3 client only when uploads/deletes need it — keeps auth/register working if S3 env is wrong."""
    global _storage
    _ensure_mongo()
    if _storage is not None:
        return
    with _init_lock:
        if _storage is not None:
            return
        _storage = ObjectStorage(
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            encryption_key_b64=settings.cv_encryption_key,
        )
        _storage.ensure_bucket_exists()


app = FastAPI(title="AI CV Scanner API")


@app.middleware("http")
async def lazy_init_backend(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    # OPTIONS preflight must not block on DB init (and should match CORS before routes).
    # /health is liveness only; /health/ready checks Mongo and returns JSON errors (must not init here).
    skip_mongo = path in ("/health", "/health/ready") or request.method == "OPTIONS"
    if not skip_mongo:
        _ensure_mongo()
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


def _cors_allow_origin_regex() -> str | None:
    parts: list[str] = []
    if settings.cors_allow_vercel_app:
        parts.append(r"https://.*\.vercel\.app$")
    extra = settings.cors_allow_origin_regex_extra.strip()
    if extra:
        try:
            re.compile(extra)
        except re.error:
            logger.error("Invalid CORS_ALLOW_ORIGIN_REGEX_EXTRA — ignoring: %s", extra)
            extra = ""
        if extra:
            parts.append(extra)
    if not parts:
        return None
    return "|".join(parts) if len(parts) > 1 else parts[0]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_origin_regex=_cors_allow_origin_regex(),
    # JWT is sent via Authorization header, not cookies — omitting credentials avoids stricter CORS edge cases.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _log_cors_config() -> None:
    """So Railway logs show effective CORS after deploy (env changes need redeploy)."""
    logger.warning(
        "CORS allow_origins=%s allow_origin_regex=%s",
        _allowed_cors_origins(),
        _cors_allow_origin_regex(),
    )


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("ascii")


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


class LanguageReq(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    level: str = Field(pattern="^(A1|A2|B1|B2|C1|C2)$")
    name: str = Field(default="", max_length=120)


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    requirements: str = Field(min_length=1, max_length=50_000)
    location: str = Field(default="", max_length=500)
    remote_only: bool = False
    years_experience: str = Field(default="", max_length=500)
    mandatory_languages: list[LanguageReq] = Field(default_factory=list)
    bonus_languages: list[LanguageReq] = Field(default_factory=list)
    skills: str = Field(default="", max_length=10_000)


class JobOut(BaseModel):
    id: str
    company_id: str
    title: str
    requirements: str
    created_at: str
    location: str = ""
    remote_only: bool = False
    years_experience: str = ""
    mandatory_languages: list[dict[str, Any]] = Field(default_factory=list)
    bonus_languages: list[dict[str, Any]] = Field(default_factory=list)
    skills: str = ""


class CreditPurchaseBody(BaseModel):
    plan: str = Field(pattern="^(starter|professional)$")


_ALLOWED_CV_CT = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


class CvPresignBody(BaseModel):
    filename: str = Field(min_length=1, max_length=220)
    content_type: str = Field(default="", max_length=128)
    size_bytes: int = Field(ge=1)


class CvFinalizeBody(BaseModel):
    token: str = Field(min_length=20)


def _normalize_cv_content_type(filename: str, declared: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    d = (declared or "").strip() or "application/octet-stream"
    if d in _ALLOWED_CV_CT:
        return d
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "Only PDF and Word (.docx) CV uploads are supported.",
    )


def _lang_lines(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for x in items:
        label = (str(x.get("name") or "")).strip() or str(x.get("code") or "")
        lvl = str(x.get("level") or "")
        if label and lvl:
            parts.append(f"{label} (minimum {lvl})")
    return "; ".join(parts)


def build_job_ranking_brief(job: dict[str, Any]) -> str:
    """Single text block passed to the ranking model (role brief + structured fields)."""
    chunks: list[str] = []
    req = (job.get("requirements") or "").strip()
    if req:
        chunks.append(req)
    ye = (job.get("years_experience") or "").strip()
    if ye:
        chunks.append(f"Years of experience sought: {ye}")
    loc = (job.get("location") or "").strip()
    if job.get("remote_only"):
        if loc:
            chunks.append(f"Work arrangement: fully remote (note: {loc})")
        else:
            chunks.append("Work arrangement: fully remote")
    elif loc:
        chunks.append(f"Location: {loc}")
    mand = job.get("mandatory_languages") or []
    if mand:
        chunks.append("Mandatory languages (CEFR minimum): " + _lang_lines(mand))
    bonus = job.get("bonus_languages") or []
    if bonus:
        chunks.append("Languages that are a plus (CEFR minimum): " + _lang_lines(bonus))
    skills = (job.get("skills") or "").strip()
    if skills:
        chunks.append(f"Skills / keywords: {skills}")
    return "\n\n".join(chunks)


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
    _ensure_storage()
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
            build_job_ranking_brief(job),
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
    return [_mongo_job_to_out(i) for i in items]


def _mongo_job_to_out(i: dict[str, Any]) -> JobOut:
    return JobOut(
        id=i["id"],
        company_id=i["company_id"],
        title=i["title"],
        requirements=i["requirements"],
        created_at=i["created_at"],
        location=i.get("location") or "",
        remote_only=bool(i.get("remote_only", False)),
        years_experience=i.get("years_experience") or "",
        mandatory_languages=list(i.get("mandatory_languages") or []),
        bonus_languages=list(i.get("bonus_languages") or []),
        skills=i.get("skills") or "",
    )


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
        "location": body.location.strip(),
        "remote_only": body.remote_only,
        "years_experience": body.years_experience.strip(),
        "mandatory_languages": [x.model_dump() for x in body.mandatory_languages],
        "bonus_languages": [x.model_dump() for x in body.bonus_languages],
        "skills": body.skills.strip(),
        "created_at": utcnow(),
    }
    _jobs.insert_one(doc)
    return _mongo_job_to_out(doc)


@app.delete("/jobs/{job_id}")
def delete_job(
    job_id: str,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    _ensure_storage()
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


@app.post("/jobs/{job_id}/cvs/presign")
def presign_cv_upload(
    job_id: str,
    body: CvPresignBody,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    """Return a presigned PUT URL so the browser can upload large PDFs directly to S3/R2 (no Vercel body limit)."""
    require_dpa(company)
    _ensure_storage()
    cid = company["id"]
    if not _jobs.find_one({"id": job_id, "company_id": cid}):
        raise HTTPException(404, "Job not found")
    if body.size_bytes > settings.max_cv_upload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large (max {settings.max_cv_upload_bytes // (1024 * 1024)} MB).",
        )
    ct = _normalize_cv_content_type(body.filename, body.content_type)
    fname = body.filename.strip() or "cv.pdf"
    safe_name = fname.replace("\\", "_").replace("/", "_")[:200]
    blob_key = f"{uuid.uuid4()}_{safe_name}"
    temp_key = f"temp-uploads/{cid}/{uuid.uuid4()}/{blob_key}"
    assert _storage is not None
    put_url = _storage.presigned_put_url(temp_key, ct, expires=900)
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    tok = jwt.encode(
        {
            "typ": "cv_up",
            "sub": cid,
            "job_id": job_id,
            "temp_key": temp_key,
            "blob_key": blob_key,
            "safe_name": safe_name,
            "ct": ct,
            "exp": int(exp.timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"put_url": put_url, "token": tok, "headers": {"Content-Type": ct}}


@app.post("/jobs/{job_id}/cvs/finalize")
def finalize_cv_upload(
    job_id: str,
    body: CvFinalizeBody,
    background_tasks: BackgroundTasks,
    company: Annotated[dict[str, Any], Depends(get_current_company)],
):
    """After the browser PUTs the file to storage, encrypt, persist CV row, and queue ranking."""
    require_dpa(company)
    cid = company["id"]
    try:
        payload = jwt.decode(
            body.token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid or expired upload token. Start the upload again.",
        )
    if (
        payload.get("typ") != "cv_up"
        or payload.get("sub") != cid
        or payload.get("job_id") != job_id
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid upload token.")

    temp_key = str(payload["temp_key"])
    blob_key = str(payload["blob_key"])
    safe_name = str(payload["safe_name"])

    if not _jobs.find_one({"id": job_id, "company_id": cid}):
        raise HTTPException(404, "Job not found")

    _ensure_storage()
    assert _storage is not None
    meta = _storage.head_object_meta(temp_key)
    if not meta:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Uploaded file not found in storage. Complete the PUT to the presigned URL first. "
            "If it still fails, configure S3/R2 CORS to allow PUT from your frontend origin.",
        )
    clen = int(meta.get("ContentLength", 0))
    if clen == 0:
        _storage.delete_object(temp_key)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload.")
    if clen > settings.max_cv_upload_bytes:
        _storage.delete_object(temp_key)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large (max {settings.max_cv_upload_bytes // (1024 * 1024)} MB).",
        )

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

    try:
        raw = _storage.get_plaintext_object(temp_key)
        if not raw:
            raise ValueError("empty")
        path = _storage.upload_cv(cid, job_id, blob_key, raw)
    except Exception:
        _reverse_cv_consumption(load_company(cid), used_free_slot)
        raise
    finally:
        _storage.delete_object(temp_key)

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

    _ensure_storage()
    assert _storage is not None
    try:
        path = _storage.upload_cv(cid, job_id, blob_key, raw)
    except ClientError as e:
        _reverse_cv_consumption(load_company(cid), used_free_slot)
        err = e.response.get("Error", {}) if e.response else {}
        code = err.get("Code", "S3Error")
        msg = err.get("Message", str(e))
        logger.warning("S3 PutObject failed: %s %s", code, msg)
        if code == "SignatureDoesNotMatch":
            detail = (
                "S3 rejected the request signature. Create ONE new IAM access key and set both "
                "S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY from that key (no mixing two keys). "
                "In S3 → bucket → Properties confirm the real Region. Add IAM permission "
                "s3:GetBucketLocation on arn:aws:s3:::YOUR_BUCKET so the app can align signing. "
                "Strip any spaces in Railway variable values."
            )
        else:
            detail = (
                f"Object storage error ({code}). Check S3 bucket, IAM (PutObject), and region."
            )
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail) from e
    except ValueError as e:
        _reverse_cv_consumption(load_company(cid), used_free_slot)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)) from e
    except Exception as e:
        _reverse_cv_consumption(load_company(cid), used_free_slot)
        logger.exception("upload_cv failed after credits reserved")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Could not store CV ({type(e).__name__}). Check server logs.",
        ) from e

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
    _ensure_storage()
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


@app.get("/health/ready")
def health_ready():
    """Returns MongoDB connectivity; use this URL in the browser when /auth/register returns 500."""
    try:
        _ensure_mongo()
        if _mongo_client is None:
            raise RuntimeError("Mongo client not initialized")
        _mongo_client.admin.command("ping")
        return {"mongodb": "ok", "database": settings.mongodb_database}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "mongodb": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )


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
