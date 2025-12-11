from typing import List, Optional
from pydantic import BaseModel, HttpUrl, field_validator

class GenerateRequest(BaseModel):
    urls: List[HttpUrl]
    model: str
    instructions: Optional[str] = None
    max_words: int = 2000
    source_labels: Optional[List[str]] = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Model is required.")
        return value.strip()

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, urls: List[HttpUrl]) -> List[HttpUrl]:
        if not urls:
            raise ValueError("At least one URL is required.")
        return urls

    @field_validator("max_words")
    @classmethod
    def validate_max_words(cls, value: int) -> int:
        return max(200, min(4000, value))


class ImageResult(BaseModel):
    title: str
    thumbnail: str
    link: str


class GenerateResponse(BaseModel):
    markdown: str
    images: List[ImageResult]
    source_titles: List[str]
    source_urls: List[str]
    source_images: List[List[str]]
    model: str
    prompt_preview: str
    source_summaries: List[str]
