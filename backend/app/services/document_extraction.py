from dataclasses import dataclass
from io import BytesIO
import unicodedata
import zipfile

from docx import Document as WordDocument
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfReader


class DocumentExtractionError(ValueError):
    """An uploaded file cannot be converted into searchable text."""


@dataclass(frozen=True)
class ExtractedPage:
    text: str
    page_number: int | None = None


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "".join(
        character
        for character in text
        if character in "\n\t" or not unicodedata.category(character).startswith("C")
    )
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines).strip()
    while "\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n", "\n\n")
    return normalized


def extract_document_text(content: bytes, mime_type: str | None) -> list[ExtractedPage]:
    mime = (mime_type or "").split(";", maxsplit=1)[0].strip().lower()
    if mime == "text/plain":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError("Text files must use UTF-8 encoding.") from exc
        return [ExtractedPage(normalize_text(text))]
    if mime == "application/pdf":
        return _extract_pdf(content)
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx(content)
    raise DocumentExtractionError("This document type is not supported for text extraction.")


def _extract_pdf(content: bytes) -> list[ExtractedPage]:
    try:
        pdf = PdfReader(BytesIO(content), strict=False)
        if pdf.is_encrypted:
            raise DocumentExtractionError("Password-protected PDFs cannot be processed.")
        return [
            ExtractedPage(normalize_text(page.extract_text() or ""), index + 1)
            for index, page in enumerate(pdf.pages)
        ]
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError("This PDF could not be read. Please upload a valid PDF.") from exc


def _extract_docx(content: bytes) -> list[ExtractedPage]:
    try:
        document = WordDocument(BytesIO(content))
        blocks = list(_docx_blocks(document))
        return [ExtractedPage(normalize_text("\n".join(blocks)))]
    except DocumentExtractionError:
        raise
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise DocumentExtractionError("This DOCX file could not be read. Please upload a valid DOCX file.") from exc
    except Exception as exc:
        raise DocumentExtractionError("This DOCX file could not be read. Please upload a valid DOCX file.") from exc


def _docx_blocks(container):
    for item in container.iter_inner_content():
        if hasattr(item, "text"):
            yield item.text
        else:
            for row in item.rows:
                yield "\t".join(
                    " ".join(block for block in _docx_blocks(cell) if block)
                    for cell in row.cells
                )
