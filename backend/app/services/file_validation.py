from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import re
import zipfile


class InvalidUploadedFile(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedFile:
    name: str
    mime_type: str
    extension: str


_FILE_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def validate_file(filename: str | None, declared_type: str | None, content: bytes) -> ValidatedFile:
    if not filename:
        raise InvalidUploadedFile("A filename is required")
    safe_name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    if not safe_name or _CONTROL_CHARACTERS.search(safe_name):
        raise InvalidUploadedFile("The filename is invalid")
    if len(safe_name) > 255:
        raise InvalidUploadedFile("The filename must be 255 characters or fewer")
    if not content:
        raise InvalidUploadedFile("Empty files cannot be uploaded")

    mime_type = (declared_type or "").split(";", maxsplit=1)[0].strip().lower()
    extension = _FILE_TYPES.get(mime_type)
    if extension is None:
        raise InvalidUploadedFile("Unsupported file type. Upload a PDF, TXT, or DOCX file")
    if PurePosixPath(safe_name).suffix.lower() != extension:
        raise InvalidUploadedFile("The filename extension does not match the declared file type")

    if mime_type == "application/pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
            raise InvalidUploadedFile("The file does not contain a valid PDF signature")
    elif mime_type == "text/plain":
        if b"\x00" in content:
            raise InvalidUploadedFile("The text file contains binary data")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidUploadedFile("Text files must use UTF-8 encoding") from exc
    else:
        _validate_docx(content)

    return ValidatedFile(name=safe_name, mime_type=mime_type, extension=extension)


def _validate_docx(content: bytes) -> None:
    if not content.startswith(b"PK\x03\x04"):
        raise InvalidUploadedFile("The file does not contain a valid DOCX signature")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise InvalidUploadedFile("The ZIP file is not a valid DOCX document")
            if any(info.flag_bits & 0x1 for info in archive.infolist()):
                raise InvalidUploadedFile("Encrypted DOCX files are not supported")
    except zipfile.BadZipFile as exc:
        raise InvalidUploadedFile("The file does not contain a valid DOCX archive") from exc
