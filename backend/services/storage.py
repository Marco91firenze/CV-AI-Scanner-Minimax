"""S3-compatible object storage (AWS S3, Cloudflare R2, etc.) for encrypted CV blobs."""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from lib.encryption import decrypt_bytes, encrypt_bytes

logger = logging.getLogger(__name__)

# GetBucketLocation sometimes returns legacy codes; SigV4 must use the real region name.
_LEGACY_GET_BUCKET_LOCATION: dict[str, str] = {
    "EU": "eu-west-1",
    "US": "us-east-1",
}


def _normalize_s3_location_constraint(raw: str | None) -> str:
    if raw is None or raw == "":
        return "us-east-1"
    key = str(raw)
    return _LEGACY_GET_BUCKET_LOCATION.get(key, key)


def _clean_aws_credential(s: str) -> str:
    return s.strip().strip("\ufeff")


def _aws_bucket_region_from_api(bucket: str, access_key_id: str, secret_access_key: str) -> str | None:
    """Ask AWS which region the bucket lives in (fixes SignatureDoesNotMatch when S3_REGION is wrong).

    Uses GetBucketLocation (needs s3:GetBucketLocation on arn:aws:s3:::bucket-name). If that fails,
    returns None and the caller falls back to configured S3_REGION.
    """
    try:
        loc_cli = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        resp = loc_cli.get_bucket_location(Bucket=bucket)
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        logger.warning(
            "Could not resolve bucket region via GetBucketLocation (%s): %s",
            err.get("Code", "?"),
            e,
        )
        return None
    raw_loc = resp.get("LocationConstraint")
    return _normalize_s3_location_constraint(None if raw_loc is None else str(raw_loc))


class ObjectStorage:
    """Encrypt-then-upload to a single bucket; paths stay compatible with prior blob layout."""

    def __init__(
        self,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None,
        region_name: str | None,
        encryption_key_b64: str,
    ) -> None:
        access_key_id = _clean_aws_credential(access_key_id)
        secret_access_key = _clean_aws_credential(secret_access_key)
        bucket = bucket.strip()

        eff_region = region_name or ("auto" if endpoint_url else "eu-central-1")
        aws_region = eff_region if eff_region not in ("", "auto") else "eu-central-1"
        kw: dict = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
        }
        if endpoint_url:
            kw["endpoint_url"] = endpoint_url.rstrip("/")
            kw["region_name"] = eff_region
            kw["config"] = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
        else:
            # AWS: do not set endpoint_url — boto3 picks the correct host for SigV4.
            resolved = _aws_bucket_region_from_api(bucket, access_key_id, secret_access_key)
            if resolved:
                if resolved != aws_region:
                    logger.warning(
                        "S3 bucket %s is in %s; S3_REGION was %s — using detected region for signing",
                        bucket,
                        resolved,
                        aws_region,
                    )
                kw["region_name"] = resolved
            else:
                kw["region_name"] = aws_region
            # Let botocore pick SigV4 + endpoint style; "virtual" alone has caused SignatureDoesNotMatch.
            kw["config"] = Config(s3={"addressing_style": "auto"})
        self._client = boto3.client("s3", **kw)
        self._bucket = bucket
        self._enc_key = encryption_key_b64

    def ensure_bucket_exists(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            pass

    def upload_cv(
        self,
        company_id: str,
        job_id: str,
        object_name: str,
        file_bytes: bytes,
    ) -> str:
        key = f"tenants/{company_id}/jobs/{job_id}/{object_name}"
        encrypted = encrypt_bytes(file_bytes, self._enc_key)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=encrypted)
        return key

    def download_cv(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        data = resp["Body"].read()
        return decrypt_bytes(data, self._enc_key)

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError:
            pass

    def presigned_put_url(self, key: str, content_type: str, expires: int = 900) -> str:
        # Include ContentType in the signature. If the browser sends a different Content-Type on PUT
        # (e.g. application/octet-stream for ArrayBuffer), S3 returns 403; error bodies often lack
        # CORS headers, so XHR surfaces it as a generic "network/CORS" failure.
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires,
            HttpMethod="PUT",
        )

    def head_object_meta(self, key: str) -> dict[str, Any] | None:
        try:
            return self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError:
            return None

    def get_plaintext_object(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def delete_all_for_job(self, company_id: str, job_id: str) -> None:
        prefix = f"tenants/{company_id}/jobs/{job_id}/"
        self._delete_prefix(prefix)

    def delete_all_for_company(self, company_id: str) -> None:
        prefix = f"tenants/{company_id}/"
        self._delete_prefix(prefix)

    def _delete_prefix(self, prefix: str) -> None:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                k = obj.get("Key")
                if k:
                    self.delete_object(k)


def delete_cv(storage: ObjectStorage, key: str | None) -> None:
    if key:
        storage.delete_object(key)
