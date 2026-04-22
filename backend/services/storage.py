"""S3-compatible object storage (AWS S3, Cloudflare R2, etc.) for encrypted CV blobs."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from lib.encryption import decrypt_bytes, encrypt_bytes


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
        eff_region = region_name or ("auto" if endpoint_url else "eu-central-1")
        kw: dict = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "region_name": eff_region,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        }
        if endpoint_url:
            kw["endpoint_url"] = endpoint_url.rstrip("/")
        else:
            # Regional endpoint avoids odd DNS/CORS behaviour with bucket.s3.amazonaws.com on some buckets.
            sign_region = eff_region if eff_region not in ("", "auto") else "eu-central-1"
            kw["endpoint_url"] = f"https://s3.{sign_region}.amazonaws.com"
            if eff_region == "auto":
                kw["region_name"] = sign_region
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
        # Do not put ContentType in Params: it becomes a signed header (content-type;host) and
        # browsers' CORS preflight OPTIONS often get 403 on S3. The client still sends Content-Type on PUT.
        _ = content_type
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key},
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
