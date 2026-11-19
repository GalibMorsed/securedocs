from dataclasses import dataclass
from io import BytesIO
import unicodedata
import zipfile

from docx import Document as WordDocument
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfReader
from PIL import Image, UnidentifiedImageError
import fitz
import pytesseract

from app.core.config import settings


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
    if mime in {"image/png", "image/jpeg", "image/tiff"}:
        return _extract_image(content)
    raise DocumentExtractionError("This document type is not supported for text extraction.")


def _extract_pdf(content: bytes) -> list[ExtractedPage]:
    try:
        pdf = PdfReader(BytesIO(content), strict=False)
        if pdf.is_encrypted:
            raise DocumentExtractionError("Password-protected PDFs cannot be processed.")
        extracted = [
            ExtractedPage(normalize_text(page.extract_text() or ""), index + 1)
            for index, page in enumerate(pdf.pages)
        ]
        ocr_indices = [index for index, page in enumerate(extracted) if len(page.text.strip()) < 40]
        if not ocr_indices:
            return extracted
        if len(extracted) > settings.ocr_max_pages:
            raise DocumentExtractionError(
                f"This PDF has more than the OCR limit of {settings.ocr_max_pages} pages. Split it into smaller files and retry."
            )
        try:
            with fitz.open(stream=content, filetype="pdf") as rendered_pdf:
                if rendered_pdf.needs_pass:
                    raise DocumentExtractionError("Password-protected PDFs cannot be processed.")
                ocr_indices = [
                    index for index in ocr_indices
                    if rendered_pdf.load_page(index).get_images(full=True)
                ]
                if not ocr_indices:
                    return extracted
                for index in ocr_indices:
                    page = rendered_pdf.load_page(index)
                    text_page = page.get_textpage_ocr(
                        language=settings.ocr_languages,
                        dpi=settings.ocr_dpi,
                        full=True,
                    )
                    ocr_text = normalize_text(page.get_text("text", textpage=text_page))
                    if ocr_text:
                        extracted[index] = ExtractedPage(ocr_text, index + 1)
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                "OCR could not read this scanned PDF. Check that the configured Tesseract language data is installed, then retry."
            ) from exc
        return extracted
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError("This PDF could not be read. Please upload a valid PDF.") from exc


def _extract_docx(content: bytes) -> list[ExtractedPage]:
    try:
        document = WordDocument(BytesIO(content))
        blocks = list(_docx_blocks(document))
        text = normalize_text("\n".join(blocks))
        if len(text) < 40:
            image_text = _ocr_docx_images(content)
            if image_text:
                text = normalize_text("\n".join([text, *image_text]))
        return [ExtractedPage(text)]
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


def _extract_image(content: bytes) -> list[ExtractedPage]:
    try:
        with Image.open(BytesIO(content)) as image:
            pages: list[ExtractedPage] = []
            total_frames = getattr(image, "n_frames", 1)
            if total_frames > settings.ocr_max_pages:
                raise DocumentExtractionError(f"This image has more than the OCR limit of {settings.ocr_max_pages} frames.")
            for page_number in range(total_frames):
                image.seek(page_number)
                image.load()
                text = pytesseract.image_to_string(image, lang=settings.ocr_languages)
                pages.append(ExtractedPage(normalize_text(text), page_number + 1))
    except pytesseract.TesseractNotFoundError as exc:
        raise DocumentExtractionError("OCR engine is unavailable. Install Tesseract OCR and retry.") from exc
    except (UnidentifiedImageError, OSError, pytesseract.TesseractError) as exc:
        raise DocumentExtractionError("OCR could not read this image file.") from exc
    return pages


def _ocr_docx_images(content: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            image_names = [name for name in archive.namelist() if name.startswith("word/media/")]
            image_text: list[str] = []
            for name in image_names:
                try:
                    with Image.open(BytesIO(archive.read(name))) as image:
                        image.load()
                        text = normalize_text(pytesseract.image_to_string(image, lang=settings.ocr_languages))
                        if text:
                            image_text.append(text)
                except (UnidentifiedImageError, OSError, pytesseract.TesseractError):
                    continue
            return image_text
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocumentExtractionError("This DOCX image content could not be read.") from exc
