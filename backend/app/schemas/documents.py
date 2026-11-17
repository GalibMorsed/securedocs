from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]


class DocumentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    mime_type: str | None = Field(default=None, max_length=255)
    file_size: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Document name cannot be blank")
        return name

    @field_validator("description", "mime_type")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class DocumentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    mime_type: str | None = Field(default=None, max_length=255)
    file_size: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_patch(self) -> "DocumentUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one document field must be provided")
        if "name" in self.model_fields_set and (
            self.name is None or not self.name.strip()
        ):
            raise ValueError("Document name cannot be blank")
        return self

    @field_validator("name", "description", "mime_type")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    name: str
    description: str | None
    mime_type: str | None
    file_size: int | None
    created_by: UUID | None
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    owner_id: UUID
    name: str
    description: str | None
    mime_type: str | None
    file_size: int | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    versions: list[DocumentVersionResponse]
