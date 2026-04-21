"""Azure Blob Storage for encrypted CV blobs (ephemeral)."""

from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from lib.encryption import decrypt_bytes, encrypt_bytes


class BlobStorageService:
    def __init__(
        self,
        connection_string: str,
        container_name: str,
        encryption_key_b64: str,
    ) -> None:
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container_name
        self._enc_key = encryption_key_b64
        self._container = self._service.get_container_client(container_name)

    def ensure_container(self) -> None:
        try:
            self._container.create_container()
        except Exception:
            pass

    def upload_cv(
        self,
        company_id: str,
        job_id: str,
        blob_name: str,
        file_bytes: bytes,
    ) -> str:
        """Encrypt and upload; return blob path key."""
        path = f"tenants/{company_id}/jobs/{job_id}/{blob_name}"
        encrypted = encrypt_bytes(file_bytes, self._enc_key)
        blob = self._service.get_blob_client(self._container_name, path)
        blob.upload_blob(encrypted, overwrite=True)
        return path

    def download_cv(self, blob_path: str) -> bytes:
        blob = self._service.get_blob_client(self._container_name, blob_path)
        data = blob.download_blob().readall()
        return decrypt_bytes(data, self._enc_key)

    def delete_blob(self, blob_path: str) -> None:
        blob = self._service.get_blob_client(self._container_name, blob_path)
        try:
            blob.delete_blob()
        except ResourceNotFoundError:
            pass

    def delete_all_for_job(self, company_id: str, job_id: str) -> None:
        prefix = f"tenants/{company_id}/jobs/{job_id}/"
        for b in self._container.list_blobs(name_starts_with=prefix):
            self.delete_blob(b.name)

    def delete_all_for_company(self, company_id: str) -> None:
        prefix = f"tenants/{company_id}/"
        for b in self._container.list_blobs(name_starts_with=prefix):
            self.delete_blob(b.name)


def delete_cv(storage: BlobStorageService, blob_path: str | None) -> None:
    if blob_path:
        storage.delete_blob(blob_path)
