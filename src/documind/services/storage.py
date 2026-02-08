"""Cloud storage service with support for GCS and S3."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO

from documind.config import get_settings
from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("services.storage")


class StorageService(ABC):
    """Abstract base class for cloud storage services."""

    @abstractmethod
    async def upload_file(self, file_path: str | Path, object_name: str) -> str:
        """Upload a file to cloud storage.

        Args:
            file_path: Local file path to upload
            object_name: Destination object name in storage

        Returns:
            Public URL or object path
        """

    @abstractmethod
    async def upload_fileobj(self, file_obj: BinaryIO, object_name: str) -> str:
        """Upload a file object to cloud storage.

        Args:
            file_obj: File-like object to upload
            object_name: Destination object name in storage

        Returns:
            Public URL or object path
        """

    @abstractmethod
    async def download_file(self, object_name: str, file_path: str | Path) -> None:
        """Download a file from cloud storage.

        Args:
            object_name: Object name in storage
            file_path: Local destination file path
        """

    @abstractmethod
    async def delete_file(self, object_name: str) -> None:
        """Delete a file from cloud storage.

        Args:
            object_name: Object name to delete
        """

    @abstractmethod
    async def list_files(self, prefix: str = "") -> list[str]:
        """List files in cloud storage.

        Args:
            prefix: Optional prefix to filter files

        Returns:
            List of object names
        """

    @abstractmethod
    async def get_presigned_url(self, object_name: str, expiration: int = 3600) -> str:
        """Get a presigned URL for temporary access.

        Args:
            object_name: Object name
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL
        """


class GCSStorageService(StorageService):
    """Google Cloud Storage implementation."""

    def __init__(self) -> None:
        """Initialize GCS storage service."""
        self.settings = get_settings()
        self._client = None
        self._bucket = None

    def _get_client(self) -> Any:
        """Get or create GCS client."""
        if self._client is None:
            from google.cloud import storage

            # Use ADC or service account key
            if self.settings.storage.google_application_credentials:
                self._client = storage.Client.from_service_account_json(
                    self.settings.storage.google_application_credentials
                )
            else:
                # Uses Application Default Credentials
                self._client = storage.Client(project=self.settings.storage.gcp_project_id or None)

        return self._client

    def _get_bucket(self) -> Any:
        """Get or create bucket reference."""
        if self._bucket is None:
            client = self._get_client()
            self._bucket = client.bucket(self.settings.storage.gcs_bucket_name)
        return self._bucket

    async def upload_file(self, file_path: str | Path, object_name: str) -> str:
        """Upload a file to GCS."""
        bucket = self._get_bucket()
        blob = bucket.blob(object_name)

        blob.upload_from_filename(str(file_path))

        logger.info(
            "Uploaded file to GCS",
            file_path=str(file_path),
            object_name=object_name,
        )

        return f"gs://{self.settings.storage.gcs_bucket_name}/{object_name}"

    async def upload_fileobj(self, file_obj: BinaryIO, object_name: str) -> str:
        """Upload a file object to GCS."""
        bucket = self._get_bucket()
        blob = bucket.blob(object_name)

        file_obj.seek(0)
        blob.upload_from_file(file_obj)

        logger.info("Uploaded file object to GCS", object_name=object_name)

        return f"gs://{self.settings.storage.gcs_bucket_name}/{object_name}"

    async def download_file(self, object_name: str, file_path: str | Path) -> None:
        """Download a file from GCS."""
        bucket = self._get_bucket()
        blob = bucket.blob(object_name)

        blob.download_to_filename(str(file_path))

        logger.info(
            "Downloaded file from GCS",
            object_name=object_name,
            file_path=str(file_path),
        )

    async def delete_file(self, object_name: str) -> None:
        """Delete a file from GCS."""
        bucket = self._get_bucket()
        blob = bucket.blob(object_name)

        blob.delete()

        logger.info("Deleted file from GCS", object_name=object_name)

    async def list_files(self, prefix: str = "") -> list[str]:
        """List files in GCS."""
        bucket = self._get_bucket()
        blobs = bucket.list_blobs(prefix=prefix)

        files = [blob.name for blob in blobs]

        logger.debug("Listed files from GCS", prefix=prefix, count=len(files))

        return files

    async def get_presigned_url(self, object_name: str, expiration: int = 3600) -> str:
        """Get a signed URL for temporary access."""
        bucket = self._get_bucket()
        blob = bucket.blob(object_name)

        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET",
        )

        logger.debug(
            "Generated signed URL",
            object_name=object_name,
            expiration=expiration,
        )

        return url


class S3StorageService(StorageService):
    """AWS S3 implementation."""

    def __init__(self) -> None:
        """Initialize S3 storage service."""
        self.settings = get_settings()
        self._client = None

    def _get_client(self) -> Any:
        """Get or create S3 client."""
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                aws_access_key_id=self.settings.storage.aws_access_key_id.get_secret_value(),
                aws_secret_access_key=self.settings.storage.aws_secret_access_key.get_secret_value(),
                region_name=self.settings.storage.aws_region,
            )

        return self._client

    async def upload_file(self, file_path: str | Path, object_name: str) -> str:
        """Upload a file to S3."""
        client = self._get_client()

        client.upload_file(
            str(file_path),
            self.settings.storage.s3_bucket_name,
            object_name,
        )

        logger.info(
            "Uploaded file to S3",
            file_path=str(file_path),
            object_name=object_name,
        )

        return f"s3://{self.settings.storage.s3_bucket_name}/{object_name}"

    async def upload_fileobj(self, file_obj: BinaryIO, object_name: str) -> str:
        """Upload a file object to S3."""
        client = self._get_client()

        file_obj.seek(0)
        client.upload_fileobj(
            file_obj,
            self.settings.storage.s3_bucket_name,
            object_name,
        )

        logger.info("Uploaded file object to S3", object_name=object_name)

        return f"s3://{self.settings.storage.s3_bucket_name}/{object_name}"

    async def download_file(self, object_name: str, file_path: str | Path) -> None:
        """Download a file from S3."""
        client = self._get_client()

        client.download_file(
            self.settings.storage.s3_bucket_name,
            object_name,
            str(file_path),
        )

        logger.info(
            "Downloaded file from S3",
            object_name=object_name,
            file_path=str(file_path),
        )

    async def delete_file(self, object_name: str) -> None:
        """Delete a file from S3."""
        client = self._get_client()

        client.delete_object(
            Bucket=self.settings.storage.s3_bucket_name,
            Key=object_name,
        )

        logger.info("Deleted file from S3", object_name=object_name)

    async def list_files(self, prefix: str = "") -> list[str]:
        """List files in S3."""
        client = self._get_client()

        response = client.list_objects_v2(
            Bucket=self.settings.storage.s3_bucket_name,
            Prefix=prefix,
        )

        files = [obj["Key"] for obj in response.get("Contents", [])]

        logger.debug("Listed files from S3", prefix=prefix, count=len(files))

        return files

    async def get_presigned_url(self, object_name: str, expiration: int = 3600) -> str:
        """Get a presigned URL for temporary access."""
        client = self._get_client()

        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.settings.storage.s3_bucket_name,
                "Key": object_name,
            },
            ExpiresIn=expiration,
        )

        logger.debug(
            "Generated presigned URL",
            object_name=object_name,
            expiration=expiration,
        )

        return url


def get_storage_service() -> StorageService:
    """Get the configured storage service.

    Returns:
        StorageService instance based on configuration
    """
    settings = get_settings()

    if settings.storage.storage_provider == "gcs":
        logger.info("Using GCS storage service")
        return GCSStorageService()
    elif settings.storage.storage_provider == "s3":
        logger.info("Using S3 storage service")
        return S3StorageService()
    else:
        msg = f"Unknown storage provider: {settings.storage.storage_provider}"
        raise ValueError(msg)
