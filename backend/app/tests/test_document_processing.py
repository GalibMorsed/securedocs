from io import BytesIO
from uuid import UUID

import pytest
from docx import Document as WordDocument

from app.models import Document, DocumentChunk
from app.services.document_chunking import chunk_pages
from app.services.document_extraction import (
    DocumentExtractionError,
    ExtractedPage,
    extract_document_text,
)
from app.services.document_processing import process_document
import app.services.document_processing as processing


class FakeProvider:
    def embed_text(self, text):
        return [0.1] * 4096

    def embed_batch(self, texts):
        return [[0.1] * 4096 for _ in texts]


class FakeBudget:
    pass


@pytest.fixture(autouse=True)
def no_embedding_budget(monkeypatch):
    monkeypatch.setattr(processing, "reserve_embedding_tokens", lambda *_args: None)


def _process(db, client, document_id):
    return process_document(db, document_id, client.app.state.test_storage, FakeProvider(), FakeBudget())

TEXT_MIME = "text/plain"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _register(client, email: str, organization: str) -> str:
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
    return response.json()["access_token"]


def _upload_text(client, token: str, content: bytes = b"The searchable contents."):
    return client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", content, TEXT_MIME)},
    )


def _pdf_with_text(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def _docx_with_text() -> bytes:
    document = WordDocument()
    document.add_paragraph("Text from a DOCX paragraph.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Table cell one"
    table.cell(0, 1).text = "Table cell two"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def test_extracts_and_normalizes_txt():
    pages = extract_document_text(b"\xef\xbb\xbf  Hello\r\n\r\nworld  \r", TEXT_MIME)
    assert pages == [ExtractedPage("Hello\n\nworld")]


def test_extracts_pdf_text_with_page_number():
    pages = extract_document_text(_pdf_with_text("Searchable PDF text."), PDF_MIME)
    assert len(pages) == 1
    assert pages[0].text == "Searchable PDF text."
    assert pages[0].page_number == 1


def test_extracts_docx_paragraphs_and_tables():
    pages = extract_document_text(_docx_with_text(), DOCX_MIME)
    assert "Text from a DOCX paragraph." in pages[0].text
    assert "Table cell one\tTable cell two" in pages[0].text


def test_empty_and_unsupported_extraction_are_clear():
    assert extract_document_text(b"  \n\t", TEXT_MIME)[0].text == ""
    with pytest.raises(DocumentExtractionError, match="not supported"):
        extract_document_text(b"content", "application/octet-stream")
    with pytest.raises(DocumentExtractionError, match="UTF-8"):
        extract_document_text(b"\xff", TEXT_MIME)


def test_chunking_respects_boundaries_overlap_and_offsets():
    text = "alpha beta gamma delta " * 160
    chunks = chunk_pages([ExtractedPage(text)], chunk_size=300, overlap=60)
    assert len(chunks) > 3
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.char_end > chunk.char_start for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)
    assert all(text[chunk.char_start : chunk.char_end] == chunk.content for chunk in chunks)
    assert all(
        chunks[index].char_start < chunks[index - 1].char_end
        for index in range(1, len(chunks))
    )
    assert chunks[0].char_start == 0
    with pytest.raises(ValueError, match="overlap"):
        chunk_pages([ExtractedPage("text")], chunk_size=10, overlap=10)


def test_worker_marks_ready_and_is_idempotent(auth_client):
    token = _register(auth_client, "processing@example.com", "Processing Org")
    uploaded = _upload_text(auth_client, token, b"Reliable searchable content. " * 100)
    assert uploaded.status_code == 201
    document_id = UUID(uploaded.json()["id"])
    assert uploaded.json()["status"] == "uploaded"
    assert auth_client.app.state.test_queued_document_ids == [document_id]

    with auth_client.app.state.test_session() as db:
        result = _process(db, auth_client, document_id)
        document = db.get(Document, document_id)
        assert result == "ready"
        assert document.status == "ready"
        assert document.processing_started_at is not None
        assert document.processed_at is not None
        assert document.processing_error is None
        chunks_before = db.query(DocumentChunk).filter_by(document_id=document_id).count()
        assert chunks_before > 1
        assert process_document(db, document_id, auth_client.app.state.test_storage, FakeProvider(), FakeBudget()) == "ready"
        assert all(chunk.embedding is not None for chunk in db.query(DocumentChunk).filter_by(document_id=document_id))
        assert db.query(DocumentChunk).filter_by(document_id=document_id).count() == chunks_before

    listed = auth_client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})
    assert listed.json()[0]["status"] == "ready"


def test_empty_document_fails_safely_and_can_be_retried(auth_client):
    token = _register(auth_client, "empty@example.com", "Empty Org")
    uploaded = _upload_text(auth_client, token, b" \n\t ")
    document_id = UUID(uploaded.json()["id"])
    with auth_client.app.state.test_session() as db:
        assert _process(db, auth_client, document_id) == "failed"

    failed = auth_client.get(
        f"/api/v1/documents/{document_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert failed["status"] == "failed"
    assert failed["processed_at"] is not None
    assert failed["processing_error"] == "No searchable text was found in this document."

    retried = auth_client.post(
        f"/api/v1/documents/{document_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retried.status_code == 202
    assert retried.json()["status"] == "uploaded"
    assert retried.json()["processing_error"] is None
    assert auth_client.app.state.test_queued_document_ids.count(document_id) == 2


def test_retry_is_organization_scoped_and_rejects_ready_document(auth_client):
    token = _register(auth_client, "retry-owner@example.com", "Retry Org A")
    outsider = _register(auth_client, "retry-outsider@example.com", "Retry Org B")
    uploaded = _upload_text(auth_client, token)
    document_id = UUID(uploaded.json()["id"])

    cross_org = auth_client.post(
        f"/api/v1/documents/{document_id}/retry",
        headers={"Authorization": f"Bearer {outsider}"},
    )
    assert cross_org.status_code == 404
    with auth_client.app.state.test_session() as db:
        assert _process(db, auth_client, document_id) == "ready"
    already_ready = auth_client.post(
        f"/api/v1/documents/{document_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert already_ready.status_code == 409


def test_worker_retries_unexpected_failures_and_resets_status(auth_client, monkeypatch):
    token = _register(auth_client, "transient@example.com", "Transient Org")
    uploaded = _upload_text(auth_client, token)
    document_id = UUID(uploaded.json()["id"])
    with auth_client.app.state.test_session() as db:
        document = db.get(Document, document_id)
        document.status = "processing"
        db.commit()

    import app.workers.tasks as tasks

    class RetryScheduled(Exception):
        pass

    retry_options = {}

    def transient_failure(*args, **kwargs):
        raise RuntimeError("temporary worker failure")

    def schedule_retry(*, exc, countdown):
        retry_options.update(exc=exc, countdown=countdown)
        raise RetryScheduled()

    monkeypatch.setattr(tasks, "SessionLocal", auth_client.app.state.test_session)
    monkeypatch.setattr(tasks, "get_embedding_provider", FakeProvider)
    monkeypatch.setattr(tasks, "process_document", transient_failure)
    monkeypatch.setattr(tasks.process_document_task, "retry", schedule_retry)
    with pytest.raises(RetryScheduled):
        tasks.process_document_task.run(str(document_id))

    with auth_client.app.state.test_session() as db:
        document = db.get(Document, document_id)
        assert document.status == "uploaded"
        assert document.processing_started_at is None
    assert isinstance(retry_options["exc"], RuntimeError)
    assert retry_options["countdown"] == 2
