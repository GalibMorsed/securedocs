from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.database import get_db
from app.models import OrganizationMember, User
from app.schemas.documents import DocumentCreate, DocumentResponse, DocumentUpdate
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


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
    return document_service.create_document(
        db,
        organization_id=membership.organization_id,
        owner_id=current_user.id,
        payload=payload,
    )


@router.get("", response_model=list[DocumentResponse], summary="List organization documents")
def list_documents(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    membership = _require_membership(db, current_user)
    return document_service.list_documents(
        db, membership.organization_id, offset=offset, limit=limit
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
    return document


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
    return document_service.update_document(
        db, document=document, payload=payload, actor_id=current_user.id
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
    document_service.delete_document(db, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
