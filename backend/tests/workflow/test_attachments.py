"""Tests for the attachment model, service, and router.

Test strategy
-------------
* **Service unit tests** — construct :class:`AttachmentService` with mocked
  ``AsyncSession`` and boto3 S3 client; assert DB and S3 interactions without
  any network or database connections.
* **Router integration tests** — override the ``_get_service`` FastAPI
  dependency so the ASGI test client never touches a real DB or S3 bucket.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.workflow.attachments import (
    _PLACEHOLDER_TENANT_ID,
    _PRESIGNED_URL_EXPIRY_SECONDS,
    _get_service,
    Attachment,
    AttachmentService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT_ID = _PLACEHOLDER_TENANT_ID
_SOURCE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_ATTACHMENT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)


def _make_attachment(
    attachment_id: uuid.UUID | None = None,
    object_key: str = "key/path/file.pdf",
) -> Attachment:
    """Build an :class:`Attachment` with every field populated for testing."""
    att = Attachment(
        id=attachment_id or _ATTACHMENT_ID,
        tenant_id=_TENANT_ID,
        source_type="invoice",
        source_id=_SOURCE_ID,
        filename="receipt.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        object_key=object_key,
    )
    # server_default columns are set by the DB; patch them manually here.
    att.created_at = _NOW
    att.updated_at = _NOW
    return att


def _make_db_mock(return_attachment: Attachment | None = None) -> MagicMock:
    """Return a mocked :class:`AsyncSession` that optionally yields *return_attachment*.

    ``add()`` is synchronous on :class:`AsyncSession`; only ``execute()`` and
    ``flush()`` are coroutines and therefore need :class:`AsyncMock`.
    """
    db = MagicMock()
    # synchronous method
    db.add = MagicMock()
    # async methods
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = return_attachment
    db.execute = AsyncMock(return_value=result_mock)
    db.flush = AsyncMock()
    return db


def _make_s3_mock(presigned_url: str = "https://s3.example.com/signed") -> MagicMock:
    """Return a mocked boto3 S3 client."""
    s3 = MagicMock()
    s3.put_object.return_value = {}
    s3.generate_presigned_url.return_value = presigned_url
    return s3


# ---------------------------------------------------------------------------
# Service: upload()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_upload_calls_s3_put_object() -> None:
    db = _make_db_mock()
    s3 = _make_s3_mock()
    service = AttachmentService(db=db, s3=s3)

    await service.upload(
        tenant_id=_TENANT_ID,
        source_type="invoice",
        source_id=_SOURCE_ID,
        filename="bill.pdf",
        content_type="application/pdf",
        data=b"hello",
    )

    s3.put_object.assert_called_once()
    call_kwargs = s3.put_object.call_args.kwargs
    assert call_kwargs["Body"] == b"hello"
    assert call_kwargs["ContentType"] == "application/pdf"
    assert "bill.pdf" in call_kwargs["Key"]


@pytest.mark.anyio
async def test_upload_persists_attachment_record() -> None:
    db = _make_db_mock()
    s3 = _make_s3_mock()
    service = AttachmentService(db=db, s3=s3)

    attachment = await service.upload(
        tenant_id=_TENANT_ID,
        source_type="receipt",
        source_id=_SOURCE_ID,
        filename="scan.png",
        content_type="image/png",
        data=b"png-bytes",
    )

    db.add.assert_called_once_with(attachment)
    db.flush.assert_awaited_once()

    assert attachment.tenant_id == _TENANT_ID
    assert attachment.source_type == "receipt"
    assert attachment.source_id == _SOURCE_ID
    assert attachment.filename == "scan.png"
    assert attachment.content_type == "image/png"
    assert attachment.size_bytes == len(b"png-bytes")


@pytest.mark.anyio
async def test_upload_object_key_includes_tenant_and_filename() -> None:
    db = _make_db_mock()
    s3 = _make_s3_mock()
    service = AttachmentService(db=db, s3=s3)

    attachment = await service.upload(
        tenant_id=_TENANT_ID,
        source_type="invoice",
        source_id=_SOURCE_ID,
        filename="document.pdf",
        content_type="application/pdf",
        data=b"x",
    )

    key = attachment.object_key
    assert str(_TENANT_ID) in key
    assert "invoice" in key
    assert str(_SOURCE_ID) in key
    assert "document.pdf" in key


@pytest.mark.anyio
async def test_upload_each_file_gets_unique_key() -> None:
    """Two uploads of the same filename must produce different object keys."""
    db = _make_db_mock()
    s3 = _make_s3_mock()
    service = AttachmentService(db=db, s3=s3)

    common_kwargs = dict(
        tenant_id=_TENANT_ID,
        source_type="invoice",
        source_id=_SOURCE_ID,
        filename="same.pdf",
        content_type="application/pdf",
        data=b"data",
    )
    a1 = await service.upload(**common_kwargs)
    a2 = await service.upload(**common_kwargs)

    assert a1.object_key != a2.object_key


# ---------------------------------------------------------------------------
# Service: get()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_returns_attachment_when_found() -> None:
    expected = _make_attachment()
    db = _make_db_mock(return_attachment=expected)
    service = AttachmentService(db=db, s3=_make_s3_mock())

    result = await service.get(tenant_id=_TENANT_ID, attachment_id=_ATTACHMENT_ID)

    assert result is expected
    db.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_get_raises_404_when_not_found() -> None:
    db = _make_db_mock(return_attachment=None)
    service = AttachmentService(db=db, s3=_make_s3_mock())

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.get(tenant_id=_TENANT_ID, attachment_id=_ATTACHMENT_ID)

    assert exc_info.value.status_code == 404
    assert str(_ATTACHMENT_ID) in exc_info.value.detail


# ---------------------------------------------------------------------------
# Service: get_download_url()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_download_url_returns_presigned_url() -> None:
    expected_url = "https://s3.example.com/presigned?sig=abc"
    attachment = _make_attachment()
    db = _make_db_mock(return_attachment=attachment)
    s3 = _make_s3_mock(presigned_url=expected_url)
    service = AttachmentService(db=db, s3=s3)

    url = await service.get_download_url(
        tenant_id=_TENANT_ID,
        attachment_id=_ATTACHMENT_ID,
    )

    assert url == expected_url


@pytest.mark.anyio
async def test_get_download_url_passes_correct_key_to_s3() -> None:
    obj_key = f"{_TENANT_ID}/invoice/{_SOURCE_ID}/{_ATTACHMENT_ID}/file.pdf"
    attachment = _make_attachment(object_key=obj_key)
    db = _make_db_mock(return_attachment=attachment)
    s3 = _make_s3_mock()
    service = AttachmentService(db=db, s3=s3)

    await service.get_download_url(tenant_id=_TENANT_ID, attachment_id=_ATTACHMENT_ID)

    s3.generate_presigned_url.assert_called_once()
    call_kwargs = s3.generate_presigned_url.call_args
    params = call_kwargs[1]["Params"] if call_kwargs[1] else call_kwargs[0][1]
    assert params["Key"] == obj_key


@pytest.mark.anyio
async def test_get_download_url_raises_404_when_attachment_missing() -> None:
    db = _make_db_mock(return_attachment=None)
    service = AttachmentService(db=db, s3=_make_s3_mock())

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await service.get_download_url(
            tenant_id=_TENANT_ID, attachment_id=_ATTACHMENT_ID
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Router: POST /api/v1/attachments/
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_upload_endpoint_returns_201() -> None:
    attachment = _make_attachment()
    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.upload.return_value = attachment

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/attachments/",
                data={"source_type": "invoice", "source_id": str(_SOURCE_ID)},
                files={"file": ("receipt.pdf", b"pdf-content", "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(_get_service)

    assert response.status_code == 201


@pytest.mark.anyio
async def test_upload_endpoint_response_body() -> None:
    attachment = _make_attachment()
    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.upload.return_value = attachment

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/attachments/",
                data={"source_type": "invoice", "source_id": str(_SOURCE_ID)},
                files={"file": ("receipt.pdf", b"pdf-content", "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(_get_service)

    body = response.json()
    assert body["id"] == str(_ATTACHMENT_ID)
    assert body["source_type"] == "invoice"
    assert body["filename"] == "receipt.pdf"
    assert body["size_bytes"] == 1024
    assert body["content_type"] == "application/pdf"


@pytest.mark.anyio
async def test_upload_endpoint_calls_service_with_correct_args() -> None:
    attachment = _make_attachment()
    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.upload.return_value = attachment

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/attachments/",
                data={"source_type": "contract", "source_id": str(_SOURCE_ID)},
                files={"file": ("contract.pdf", b"bytes", "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(_get_service)

    mock_service.upload.assert_awaited_once()
    call_kwargs = mock_service.upload.call_args.kwargs
    assert call_kwargs["source_type"] == "contract"
    assert call_kwargs["source_id"] == _SOURCE_ID
    assert call_kwargs["filename"] == "contract.pdf"
    assert call_kwargs["data"] == b"bytes"


# ---------------------------------------------------------------------------
# Router: GET /api/v1/attachments/{attachment_id}
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_attachment_endpoint_returns_200() -> None:
    attachment = _make_attachment()
    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.get.return_value = attachment

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/attachments/{_ATTACHMENT_ID}")
    finally:
        app.dependency_overrides.pop(_get_service)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(_ATTACHMENT_ID)


@pytest.mark.anyio
async def test_get_attachment_endpoint_returns_404_when_missing() -> None:
    from fastapi import HTTPException

    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.get.side_effect = HTTPException(
        status_code=404, detail="Attachment not found."
    )

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/attachments/{_ATTACHMENT_ID}")
    finally:
        app.dependency_overrides.pop(_get_service)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Router: GET /api/v1/attachments/{attachment_id}/download-url
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_download_url_endpoint_returns_200() -> None:
    expected_url = "https://s3.example.com/file?sig=xyz"
    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.get_download_url.return_value = expected_url

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/attachments/{_ATTACHMENT_ID}/download-url"
            )
    finally:
        app.dependency_overrides.pop(_get_service)

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == expected_url
    assert body["expires_in_seconds"] == _PRESIGNED_URL_EXPIRY_SECONDS


@pytest.mark.anyio
async def test_download_url_endpoint_404_when_attachment_missing() -> None:
    from fastapi import HTTPException

    mock_service = AsyncMock(spec=AttachmentService)
    mock_service.get_download_url.side_effect = HTTPException(
        status_code=404, detail="Attachment not found."
    )

    app.dependency_overrides[_get_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/attachments/{_ATTACHMENT_ID}/download-url"
            )
    finally:
        app.dependency_overrides.pop(_get_service)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Model: build_object_key
# ---------------------------------------------------------------------------


def test_build_object_key_format() -> None:
    key = AttachmentService._build_object_key(
        tenant_id=_TENANT_ID,
        source_type="invoice",
        source_id=_SOURCE_ID,
        attachment_id=_ATTACHMENT_ID,
        filename="doc.pdf",
    )
    expected = f"{_TENANT_ID}/invoice/{_SOURCE_ID}/{_ATTACHMENT_ID}/doc.pdf"
    assert key == expected
