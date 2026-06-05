"""Attachment model, service, and router.

An Attachment links a file stored in object storage (S3-compatible) to a
source document within CairnBooks (e.g. an invoice, journal entry, or company
record).

Storage layout
--------------
Files are stored under a key of the form::

    {tenant_id}/{source_type}/{source_id}/{attachment_id}/{filename}

This keeps attachments tenant-scoped at the storage level and makes it
straightforward to list or delete all files for a given source document.

API surface
-----------
POST   /api/v1/attachments/                              — upload a file
GET    /api/v1/attachments/{attachment_id}               — fetch metadata
GET    /api/v1/attachments/{attachment_id}/download-url  — presigned download URL
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Annotated

import boto3
from botocore.client import BaseClient
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import UUID, DateTime, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db.mixins import TenantMixin
from app.db.session import Base, get_db

# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------


class Attachment(TenantMixin, Base):
    """A file attachment linked to a source document.

    Attributes
    ----------
    id:
        Surrogate primary key (UUID v4), generated client-side on insert.
    tenant_id:
        Owning tenant (inherited from :class:`~app.db.mixins.TenantMixin`).
    source_type:
        Logical document type the file is attached to (e.g. ``"invoice"``).
        Max 64 characters, indexed for efficient filtering.
    source_id:
        UUID of the specific source document.
    filename:
        Original filename as provided by the uploader.
    content_type:
        MIME type of the file (e.g. ``"application/pdf"``).
    size_bytes:
        File size in bytes at upload time.
    object_key:
        Key used to store the file in object storage (unique per bucket).
    created_at / updated_at:
        Standard UTC audit timestamps.
    """

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Logical type of the linked source document (e.g. 'invoice').",
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="UUID of the specific source document.",
    )
    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Original filename as uploaded by the user.",
    )
    content_type: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        doc="MIME type of the uploaded file.",
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="File size in bytes.",
    )
    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
        doc="Key used to address the file in object storage.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Attachment id={self.id!r} filename={self.filename!r}>"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AttachmentRead(BaseModel):
    """Public representation of an :class:`Attachment` returned by the API."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    object_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DownloadUrlResponse(BaseModel):
    """Pre-signed download URL with its expiry duration."""

    url: str
    expires_in_seconds: int


# ---------------------------------------------------------------------------
# S3 client dependency
# ---------------------------------------------------------------------------

_PRESIGNED_URL_EXPIRY_SECONDS: int = 3_600  # 1 hour


def get_s3_client() -> BaseClient:
    """FastAPI dependency: return an S3 client from application settings.

    A new client is constructed on each call so that dependency overrides in
    tests work without module-level state.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key_id,
        aws_secret_access_key=settings.storage_secret_access_key,
        region_name=settings.storage_region,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AttachmentService:
    """Orchestrates upload, retrieval, and presigned-URL generation.

    All S3 calls are executed in a thread pool via :func:`asyncio.to_thread`
    so they do not block the event loop (boto3 is synchronous).

    Parameters
    ----------
    db:
        An open :class:`~sqlalchemy.ext.asyncio.AsyncSession`.
    s3:
        A boto3 S3 client.
    """

    def __init__(self, db: AsyncSession, s3: BaseClient) -> None:
        self._db = db
        self._s3 = s3

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_object_key(
        tenant_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        attachment_id: uuid.UUID,
        filename: str,
    ) -> str:
        """Compose the object-storage key for a new attachment."""
        return f"{tenant_id}/{source_type}/{source_id}/{attachment_id}/{filename}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload(
        self,
        *,
        tenant_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Attachment:
        """Store *data* in object storage and persist an :class:`Attachment` row.

        Parameters
        ----------
        tenant_id:
            Owning tenant UUID.
        source_type:
            Logical document type (e.g. ``"invoice"``).
        source_id:
            UUID of the linked document.
        filename:
            Original filename.
        content_type:
            MIME type of the uploaded content.
        data:
            Raw file bytes to store.

        Returns
        -------
        Attachment
            The newly created, flushed (but not yet committed) ORM instance.
        """
        attachment_id = uuid.uuid4()
        key = self._build_object_key(
            tenant_id, source_type, source_id, attachment_id, filename
        )

        await asyncio.to_thread(
            self._s3.put_object,
            Bucket=settings.storage_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        attachment = Attachment(
            id=attachment_id,
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            object_key=key,
        )
        self._db.add(attachment)
        await self._db.flush()
        return attachment

    async def get(
        self,
        *,
        tenant_id: uuid.UUID,
        attachment_id: uuid.UUID,
    ) -> Attachment:
        """Fetch an :class:`Attachment` by ID, scoped to *tenant_id*.

        Parameters
        ----------
        tenant_id:
            Owning tenant UUID — used to enforce row-level isolation.
        attachment_id:
            Primary key of the requested attachment.

        Raises
        ------
        HTTPException(404)
            If no matching row is found for this tenant.
        """
        stmt = select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        attachment = result.scalar_one_or_none()
        if attachment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment {attachment_id} not found.",
            )
        return attachment

    async def get_download_url(
        self,
        *,
        tenant_id: uuid.UUID,
        attachment_id: uuid.UUID,
        expires_in: int = _PRESIGNED_URL_EXPIRY_SECONDS,
    ) -> str:
        """Return a pre-signed URL for direct download from object storage.

        Parameters
        ----------
        tenant_id:
            Owning tenant — used to verify ownership before issuing the URL.
        attachment_id:
            UUID of the :class:`Attachment`.
        expires_in:
            URL validity in seconds (default: 3 600 s / 1 hour).

        Returns
        -------
        str
            Pre-signed S3 ``GetObject`` URL.
        """
        attachment = await self.get(tenant_id=tenant_id, attachment_id=attachment_id)
        url: str = await asyncio.to_thread(
            self._s3.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": settings.storage_bucket_name,
                "Key": attachment.object_key,
            },
            ExpiresIn=expires_in,
        )
        return url


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/attachments", tags=["attachments"])

# ---------------------------------------------------------------------------
# NOTE: tenant extraction is a placeholder until the JWT auth layer is wired
# up.  The fixed UUID allows the endpoint to be tested without a token.
# ---------------------------------------------------------------------------
_PLACEHOLDER_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_tenant_id() -> uuid.UUID:
    """Dependency: return the current tenant UUID.

    Replace this with real JWT-claim extraction once auth is integrated.
    """
    return _PLACEHOLDER_TENANT_ID


def _get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    s3: Annotated[BaseClient, Depends(get_s3_client)],
) -> AttachmentService:
    """FastAPI dependency factory for :class:`AttachmentService`."""
    return AttachmentService(db=db, s3=s3)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post(
    "/",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an attachment",
    description=(
        "Upload a file and link it to a source document. "
        "The file is stored in object storage; metadata is persisted in the "
        "database. Use ``source_type`` and ``source_id`` to identify the "
        "document the file belongs to."
    ),
)
async def upload_attachment(
    source_type: Annotated[str, Form(description="Logical type of the source document.")],
    source_id: Annotated[uuid.UUID, Form(description="UUID of the source document.")],
    file: Annotated[UploadFile, File(description="File to upload.")],
    service: Annotated[AttachmentService, Depends(_get_service)],
    tenant_id: Annotated[uuid.UUID, Depends(_get_tenant_id)],
) -> AttachmentRead:
    data = await file.read()
    attachment = await service.upload(
        tenant_id=tenant_id,
        source_type=source_type,
        source_id=source_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return AttachmentRead.model_validate(attachment)


@router.get(
    "/{attachment_id}",
    response_model=AttachmentRead,
    summary="Retrieve attachment metadata",
    description="Return metadata for a single attachment owned by the current tenant.",
)
async def get_attachment(
    attachment_id: uuid.UUID,
    service: Annotated[AttachmentService, Depends(_get_service)],
    tenant_id: Annotated[uuid.UUID, Depends(_get_tenant_id)],
) -> AttachmentRead:
    attachment = await service.get(tenant_id=tenant_id, attachment_id=attachment_id)
    return AttachmentRead.model_validate(attachment)


@router.get(
    "/{attachment_id}/download-url",
    response_model=DownloadUrlResponse,
    summary="Get a pre-signed download URL",
    description=(
        "Return a time-limited pre-signed URL that allows direct download of "
        "the attachment from object storage without going through the API."
    ),
)
async def get_download_url(
    attachment_id: uuid.UUID,
    service: Annotated[AttachmentService, Depends(_get_service)],
    tenant_id: Annotated[uuid.UUID, Depends(_get_tenant_id)],
) -> DownloadUrlResponse:
    url = await service.get_download_url(
        tenant_id=tenant_id,
        attachment_id=attachment_id,
    )
    return DownloadUrlResponse(
        url=url,
        expires_in_seconds=_PRESIGNED_URL_EXPIRY_SECONDS,
    )
