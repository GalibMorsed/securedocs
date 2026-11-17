from collections.abc import Iterator
from uuid import UUID
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models import OrganizationMember, User
from app.schemas.documents import DocumentCreate, DocumentResponse, DocumentUpdate
from app.services import document_service
from app.services.file_validation import InvalidUploadedFile, validate_file
from app.storage import FileStorage, StorageError, StorageNotFound, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_CHUNK_SIZE = 64 * 1024



def _require_membership(db: Session, user: User) -> OrganizationMember:
    membership = document_service.get_user_membership(db, user)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to an organization to access documents",
        )
    return membership


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create document metadata in your organization",
)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    membership = _require_membership(db, current_user)
    if membership.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot create documents",
        )
    return DocumentResponse.model_validate(
        document_service.create_document(
            db,
            organization_id=membership.organization_id,
            owner_id=current_user.id,
            payload=payload,
        )
    )


@router.get("", response_model=list[DocumentResponse], summary="List organization documents")
def list_documents(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    membership = _require_membership(db, current_user)
    documents = document_service.list_documents(
        db, membership.organization_id, offset=offset, limit=limit
    )
    return [DocumentResponse.model_validate(document) for document in documents]


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a private document file",
)
def upload_document(
    file: UploadFile = File(...),
    description: str | None = Form(default=None, max_length=10_000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: FileStorage = Depends(get_storage),
) -> DocumentResponse:
    membership = _require_membership(db, current_user)
    if membership.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot upload documents",
        )

    try:
        content = _read_upload(file)
        validated = validate_file(file.filename, file.content_type, content)
    except InvalidUploadedFile as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    finally:
        file.file.close()

    try:
        return DocumentResponse.model_validate(
            document_service.create_uploaded_document(
                db,
                organization_id=membership.organization_id,
                owner_id=current_user.id,
                name=validated.name,
                description=description,
                mime_type=validated.mime_type,
                content=content,
                storage=storage,
            )
        )
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private file storage is unavailable",
        ) from exc


@router.get(
    "/{document_id}/download",
    summary="Download a document after organization authorization",
    responses={
        200: {"content": {"application/octet-stream": {}}},
        404: {"description": "Document or stored file not found"},
    },
)
def download_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: FileStorage = Depends(get_storage),
) -> StreamingResponse:
    membership = _require_membership(db, current_user)
    document = document_service.get_document(
        db, membership.organization_id, document_id
    )
    if document is None or document.storage_key is None:
        raise HTTPException(status_code=404, detail="Document file not found")
    try:
        stored_file = storage.open(document.storage_key)
    except StorageNotFound as exc:
        raise HTTPException(status_code=404, detail="Document file not found") from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private file storage is unavailable",
        ) from exc

    safe_name = quote(document.name, safe="")
    return StreamingResponse(
        _stream_file(stored_file.stream),
        media_type=document.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document in your organization",
)
def read_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    membership = _require_membership(db, current_user)
    document = document_service.get_document(
        db, membership.organization_id, document_id
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
)
def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    membership = _require_membership(db, current_user)
    document = document_service.get_document(
        db, membership.organization_id, document_id
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document_service.can_edit_document(db, document, membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this document",
        )
    return DocumentResponse.model_validate(
        document_service.update_document(
            db, document=document, payload=payload, actor_id=current_user.id
        )
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document metadata and its versions",
)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: FileStorage = Depends(get_storage),
) -> Response:
    membership = _require_membership(db, current_user)
    document = document_service.get_document(
        db, membership.organization_id, document_id
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document_service.can_delete_document(db, document, membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this document",
        )
    try:
        document_service.delete_document(db, document, storage)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private file storage is unavailable",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _read_upload(file: UploadFile) -> bytes:
    max_size = settings.upload_max_bytes
    if file.size is not None and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {max_size}-byte upload limit",
        )

    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = file.file.read(min(UPLOAD_CHUNK_SIZE, max_size + 1 - total_size))
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds the {max_size}-byte upload limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _stream_file(stream: object) -> Iterator[bytes]:
    try:
        while True:
            chunk = stream.read(UPLOAD_CHUNK_SIZE)  # type: ignore[attr-defined]
            if not chunk:
                break
            yield chunk
    finally:
        stream.close()  # type: ignore[attr-defined]
