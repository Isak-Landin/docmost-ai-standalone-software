from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SpaceCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="Display name for the new space.")
    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-zA-Z0-9]+$",
        description="URL-friendly identifier. Alphanumeric only, no spaces or dashes.",
    )
    description: Optional[str] = Field(None, description="Optional plain-text description.")


class PageCreateIn(BaseModel):
    title: Optional[str] = Field(None, description="Page title. Defaults to empty if omitted.")
    content: Optional[str] = Field(None, description="Markdown content for the page body.")
    parent_page_id: Optional[UUID] = Field(
        None, description="UUID of the parent page. Omit for a root-level page."
    )


class PageUpdateIn(BaseModel):
    title: Optional[str] = Field(None, description="New title. Unchanged if omitted.")
    content: Optional[str] = Field(None, description="Markdown content. Unchanged if omitted.")
    operation: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description=(
            "How content is applied when content is provided. "
            "'replace' overwrites the full body (default). "
            "'append' adds after existing content. "
            "'prepend' adds before existing content."
        ),
    )
