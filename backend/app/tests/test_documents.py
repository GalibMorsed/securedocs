from io import BytesIO
from uuid import UUID

import pytest
from docx import Document as WordDocument

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models import Document, DocumentPermission, OrganizationMember, User
from app.services import document_service
from app.services.file_validation import validate_file
from app.storage import StorageError


def _register(client, *, email: str, organization: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": email.split("@", maxsplit=1)[0],
            "organization_name": organization,
        },
    )
    assert response.status_code == 201
    return response.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_document_metadata_crud_and_version_history(auth_client):
    account = _register(
        auth_client, email="writer@example.com", organization="Writer Org"
    )
    headers = _headers(account["access_token"])

    created = auth_client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "name": "  Security handbook.pdf  ",
            "description": "Internal reference",
            "mime_type": "application/pdf",
            "file_size": 2048,
        },
    )
    assert created.status_code == 201
    document = created.json()
    assert document["name"] == "Security handbook.pdf"
    assert document["status"] == "uploaded"
    assert document["organization_id"]
    assert document["owner_id"] == account["user"]["id"]
    assert len(document["versions"]) == 1
    assert document["versions"][0]["version_number"] == 1
    assert document["has_file"] is False

    listed = auth_client.get("/api/v1/documents", headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [document["id"]]

    detail = auth_client.get(
        f"/api/v1/documents/{document['id']}", headers=headers
    )
    assert detail.status_code == 200

    updated = auth_client.patch(
        f"/api/v1/documents/{document['id']}",
        headers=headers,
        json={"name": "Security handbook v2.pdf", "file_size": 3072},
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["name"] == "Security handbook v2.pdf"
    assert len(updated_body["versions"]) == 2
    assert updated_body["versions"][-1]["version_number"] == 2
    assert updated_body["versions"][-1]["file_size"] == 3072

    empty_patch = auth_client.patch(
        f"/api/v1/documents/{document['id']}", headers=headers, json={}
    )
    assert empty_patch.status_code == 422

    deleted = auth_client.delete(
        f"/api/v1/documents/{document['id']}", headers=headers
    )
    assert deleted.status_code == 204
    assert auth_client.get(
        f"/api/v1/documents/{document['id']}", headers=headers
    ).status_code == 404
    assert auth_client.get("/api/v1/documents", headers=headers).json() == []

    with auth_client.app.state.test_session() as db:
        assert db.query(Document).filter_by(id=UUID(document["id"])).first() is None


def test_document_routes_require_authentication(auth_client):
    assert auth_client.get("/api/v1/documents").status_code == 401
    assert auth_client.post(
        "/api/v1/documents", json={"name": "Private"}
    ).status_code == 401


def test_document_metadata_is_isolated_between_organizations(auth_client):
    first = _register(
        auth_client, email="first@example.com", organization="First Org"
    )
    second = _register(
        auth_client, email="second@example.com", organization="Second Org"
    )
    first_headers = _headers(first["access_token"])
    second_headers = _headers(second["access_token"])

    created = auth_client.post(
        "/api/v1/documents",
        headers=first_headers,
        json={"name": "First organization document"},
    )
    assert created.status_code == 201
    document_id = created.json()["id"]

    assert auth_client.get("/api/v1/documents", headers=second_headers).json() == []
    assert auth_client.get(
        f"/api/v1/documents/{document_id}", headers=second_headers
    ).status_code == 404
    assert auth_client.patch(
        f"/api/v1/documents/{document_id}",
        headers=second_headers,
        json={"name": "Attempted cross-organization edit"},
    ).status_code == 404
    assert auth_client.delete(
        f"/api/v1/documents/{document_id}", headers=second_headers
    ).status_code == 404


def test_inactive_users_cannot_access_document_routes(auth_client):
    account = _register(
        auth_client, email="inactive@example.com", organization="Inactive Org"
    )
    with auth_client.app.state.test_session() as db:
        user = db.get(User, UUID(account["user"]["id"]))
        assert user is not None
        user.is_active = False
        db.commit()

    assert auth_client.get(
        "/api/v1/documents", headers=_headers(account["access_token"])
    ).status_code == 401


def test_viewer_can_read_but_cannot_create_or_edit_documents(auth_client):
    owner_account = _register(
        auth_client, email="owner@example.com", organization="Shared Org"
    )
    owner_headers = _headers(owner_account["access_token"])
    created = auth_client.post(
        "/api/v1/documents", headers=owner_headers, json={"name": "Read only"}
    )
    document_id = created.json()["id"]

    with auth_client.app.state.test_session() as db:
        owner_membership = (
            db.query(OrganizationMember)
            .filter_by(user_id=UUID(owner_account["user"]["id"]))
            .one()
        )
        viewer = User(
            email="viewer@example.com",
            password_hash=hash_password("correct horse battery staple"),
            full_name="Viewer",
        )
        db.add(viewer)
        db.flush()
        db.add(
            OrganizationMember(
                organization_id=owner_membership.organization_id,
                user_id=viewer.id,
                role="viewer",
            )
        )
        db.commit()
        viewer_token = create_access_token(viewer.id)

    viewer_headers = _headers(viewer_token)
    assert len(auth_client.get("/api/v1/documents", headers=viewer_headers).json()) == 1
    assert auth_client.post(
        "/api/v1/documents", headers=viewer_headers, json={"name": "Not allowed"}
    ).status_code == 403
    assert auth_client.patch(
        f"/api/v1/documents/{document_id}",
        headers=viewer_headers,
        json={"name": "Not allowed"},
    ).status_code == 403


def test_document_edit_permission_grant_allows_member_to_edit(auth_client):
    owner_account = _register(
        auth_client, email="grantor@example.com", organization="Permission Org"
    )
    created = auth_client.post(
        "/api/v1/documents",
        headers=_headers(owner_account["access_token"]),
        json={"name": "Shared for editing"},
    )
    document_id = created.json()["id"]

    with auth_client.app.state.test_session() as db:
        organization_id = UUID(created.json()["organization_id"])
        member = User(
            email="editor@example.com",
            password_hash=hash_password("correct horse battery staple"),
            full_name="Editor",
        )
        db.add(member)
        db.flush()
        db.add(
            OrganizationMember(
                organization_id=organization_id,
                user_id=member.id,
                role="member",
            )
        )
        db.add(
            DocumentPermission(
                document_id=UUID(document_id), user_id=member.id, permission="edit"
            )
        )
        db.commit()
        member_token = create_access_token(member.id)

    updated = auth_client.patch(
        f"/api/v1/documents/{document_id}",
        headers=_headers(member_token),
        json={"description": "Edited by a permitted teammate"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Edited by a permitted teammate"


def test_private_text_upload_and_download(auth_client):
    account = _register(
        auth_client, email="upload@example.com", organization="Upload Org"
    )
    content = b"Private team notes.\n"
    response = auth_client.post(
        "/api/v1/documents/upload",
        headers=_headers(account["access_token"]),
        data={"description": "Quarterly notes"},
        files={"file": ("notes.txt", content, "text/plain")},
    )

    assert response.status_code == 201
    document = response.json()
    assert document["name"] == "notes.txt"
    assert document["mime_type"] == "text/plain"
    assert document["file_size"] == len(content)
    assert document["description"] == "Quarterly notes"
    assert document["has_file"] is True
    assert "storage_key" not in document

    with auth_client.app.state.test_session() as db:
        stored_document = db.get(Document, UUID(document["id"]))
        assert stored_document is not None
        storage_key = stored_document.storage_key
    stored_path = auth_client.app.state.test_storage.root / storage_key
    assert stored_path.is_file()

    downloaded = auth_client.get(
        f"/api/v1/documents/{document['id']}/download",
        headers=_headers(account["access_token"]),
    )
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["content-type"] == "text/plain; charset=utf-8"
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert str(auth_client.app.state.test_storage.root) not in downloaded.headers.get(
        "content-disposition", ""
    )


def test_docx_upload_checks_zip_package_structure(auth_client):
    account = _register(
        auth_client, email="docx@example.com", organization="DOCX Org"
    )
    buffer = BytesIO()
    docx = WordDocument()
    docx.add_paragraph("A valid DOCX document.")
    docx.save(buffer)

    response = auth_client.post(
        "/api/v1/documents/upload",
        headers=_headers(account["access_token"]),
        files={
            "file": (
                "brief.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    assert response.json()["has_file"] is True


def test_upload_rejects_bad_signature_unsupported_type_and_oversize(auth_client, monkeypatch):
    account = _register(
        auth_client, email="validation@example.com", organization="Validation Org"
    )
    headers = _headers(account["access_token"])

    bad_pdf = auth_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("bad.pdf", b"plain text", "application/pdf")},
    )
    unsupported = auth_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("archive.bin", b"data", "application/octet-stream")},
    )
    assert bad_pdf.status_code == 415
    assert unsupported.status_code == 415

    monkeypatch.setattr(settings, "upload_max_bytes", 4)
    oversized = auth_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("large.txt", b"12345", "text/plain")},
    )
    assert oversized.status_code == 413
    assert auth_client.get(
        "/api/v1/documents", headers=headers
    ).json() == []
    assert list(auth_client.app.state.test_storage.root.iterdir()) == []


def test_upload_requires_authentication(auth_client):
    response = auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("private.txt", b"private", "text/plain")},
    )
    assert response.status_code == 401
    assert list(auth_client.app.state.test_storage.root.iterdir()) == []


def test_other_organization_cannot_download_uploaded_file(auth_client):
    first = _register(
        auth_client, email="file-owner@example.com", organization="File Org A"
    )
    second = _register(
        auth_client, email="file-outsider@example.com", organization="File Org B"
    )
    uploaded = auth_client.post(
        "/api/v1/documents/upload",
        headers=_headers(first["access_token"]),
        files={"file": ("secret.txt", b"secret", "text/plain")},
    )
    assert uploaded.status_code == 201

    cross_org = auth_client.get(
        f"/api/v1/documents/{uploaded.json()['id']}/download",
        headers=_headers(second["access_token"]),
    )
    assert cross_org.status_code == 404


def test_upload_storage_failure_removes_partial_file_and_creates_no_document(
    auth_client, monkeypatch
):
    account = _register(
        auth_client, email="storage-fail@example.com", organization="Failure Org"
    )
    storage = auth_client.app.state.test_storage
    original_store = storage.store

    def store_then_fail(key: str, content: bytes, content_type: str) -> None:
        original_store(key, content, content_type)
        raise StorageError("simulated storage failure")

    monkeypatch.setattr(storage, "store", store_then_fail)
    response = auth_client.post(
        "/api/v1/documents/upload",
        headers=_headers(account["access_token"]),
        files={"file": ("failure.txt", b"contents", "text/plain")},
    )
    assert response.status_code == 503
    assert auth_client.get(
        "/api/v1/documents", headers=_headers(account["access_token"])
    ).json() == []
    assert list(storage.root.iterdir()) == []


def test_database_failure_after_storage_removes_orphaned_file(auth_client, monkeypatch):
    account = _register(
        auth_client, email="db-fail@example.com", organization="DB Failure Org"
    )

    def fail_create(*args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(document_service, "create_document", fail_create)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        auth_client.post(
            "/api/v1/documents/upload",
            headers=_headers(account["access_token"]),
            files={"file": ("orphan.txt", b"contents", "text/plain")},
        )

    assert list(auth_client.app.state.test_storage.root.iterdir()) == []


def test_png_is_accepted_as_an_ocr_image():
    valid = validate_file("scan.png", "image/png", b"\x89PNG\r\n\x1a\ncontent")
    assert valid.mime_type == "image/png"
    assert valid.extension == ".png"
