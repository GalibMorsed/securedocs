from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Document,
    DocumentPermission,
    DocumentVersion,
    OrganizationMember,
    User,
)
from app.schemas.documents import DocumentCreate, DocumentUpdate


def get_user_membership(db: Session, user: User) -> OrganizationMember | None:
    return db.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .order_by(OrganizationMember.created_at, OrganizationMember.id)
        .limit(1)
    )


def list_documents(
    db: Session,
    organization_id: UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.versions))
            .where(Document.organization_id == organization_id)
            .order_by(Document.updated_at.desc(), Document.id)
            .offset(offset)
            .limit(limit)
        ).all()
    )


def get_document(
    db: Session, organization_id: UUID, document_id: UUID
) -> Document | None:
    return db.scalar(
        select(Document)
        .options(selectinload(Document.versions))
        .where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )


def create_document(
    db: Session,
    *,
    organization_id: UUID,
    owner_id: UUID,
    payload: DocumentCreate,
) -> Document:
    document = Document(
        organization_id=organization_id,
        owner_id=owner_id,
        name=payload.name,
        description=payload.description,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        status="uploaded",
    )
    document.versions.append(
        DocumentVersion(
            version_number=1,
            name=document.name,
            description=document.description,
            mime_type=document.mime_type,
            file_size=document.file_size,
            created_by=owner_id,
        )
    )
    db.add(document)
    db.commit()
    return get_document(db, organization_id, document.id)  # type: ignore[return-value]


def can_edit_document(
    db: Session, document: Document, membership: OrganizationMember
) -> bool:
    if membership.role in {"owner", "admin"} or document.owner_id == membership.user_id:
        return True
    return (
        db.scalar(
            select(DocumentPermission.id).where(
                DocumentPermission.document_id == document.id,
                DocumentPermission.user_id == membership.user_id,
                DocumentPermission.permission.in_(["edit", "manage"]),
            )
        )
        is not None
    )


def can_delete_document(
    db: Session, document: Document, membership: OrganizationMember
) -> bool:
    if membership.role in {"owner", "admin"} or document.owner_id == membership.user_id:
        return True
    return (
        db.scalar(
            select(DocumentPermission.id).where(
                DocumentPermission.document_id == document.id,
                DocumentPermission.user_id == membership.user_id,
                DocumentPermission.permission == "manage",
            )
        )
        is not None
    )


def update_document(
    db: Session,
    *,
    document: Document,
    payload: DocumentUpdate,
    actor_id: UUID,
) -> Document:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(document, field, value)

    next_version = (document.versions[-1].version_number if document.versions else 0) + 1
    document.versions.append(
        DocumentVersion(
            version_number=next_version,
            name=document.name,
            description=document.description,
            mime_type=document.mime_type,
            file_size=document.file_size,
            storage_key=document.storage_key,
            created_by=actor_id,
        )
    )
    db.add(document)
    db.commit()
    return get_document(db, document.organization_id, document.id)  # type: ignore[return-value]


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()
