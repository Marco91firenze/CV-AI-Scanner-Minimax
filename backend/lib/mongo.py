"""MongoDB connection and indexes. Tenant isolation: always filter by company_id (and id where applicable)."""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


def connect(uri: str, db_name: str) -> tuple[MongoClient, Database]:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    _ensure_indexes(db)
    return client, db


def _ensure_indexes(db: Database) -> None:
    db.companies.create_index("id", unique=True)
    db.companies.create_index("email", unique=True)
    db.jobs.create_index([("company_id", ASCENDING), ("id", ASCENDING)], unique=True)
    db.jobs.create_index([("company_id", ASCENDING), ("created_at", DESCENDING)])
    db.cvs.create_index([("company_id", ASCENDING), ("id", ASCENDING)], unique=True)
    db.cvs.create_index([("company_id", ASCENDING), ("job_id", ASCENDING)])
    db.transactions.create_index([("company_id", ASCENDING), ("id", ASCENDING)], unique=True)
    db.transactions.create_index("company_id")


def col_companies(db: Database) -> Collection:
    return db.companies


def col_jobs(db: Database) -> Collection:
    return db.jobs


def col_cvs(db: Database) -> Collection:
    return db.cvs


def col_transactions(db: Database) -> Collection:
    return db.transactions
