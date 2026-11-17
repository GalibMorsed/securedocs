from uuid import UUID

from app.core.security import create_access_token, hash_password
from app.models import Document, DocumentPermission, OrganizationMember, User


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
    assert document.get("storage_key") is None

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
