"""Product API, AI-output, and database models.

The project uses MongoDB for persistence, but all inbound/outbound structures
are described with Pydantic models. These models provide explicit contracts
between the API, services, AI generation, and publisher layers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ── Category models ────────────────────────────────────────────────────────────

class CategoryNode(BaseModel):
    """A single Zoho Commerce category node, potentially with nested children."""

    category_id: str
    name: str
    parent_category_id: str = "0"
    depth: int = 0
    visibility: bool = True
    children: List["CategoryNode"] = Field(default_factory=list)


CategoryNode.model_rebuild()  # resolve forward reference


class CategoryTreeResponse(BaseModel):
    """Response for GET /categories: both tree and flat list for different UI uses."""

    tree: List[CategoryNode] = Field(default_factory=list)
    flat: List[CategoryNode] = Field(default_factory=list)
    total: int = 0
    cached: bool = False


class CategorySuggestRequest(BaseModel):
    """Request body for POST /categories/suggest."""

    product_title: str
    tags: List[str] = Field(default_factory=list)
    seo_keywords: List[str] = Field(default_factory=list)
    short_description_html: str = ""
    categories: List[Dict[str, str]] = Field(default_factory=list)  # [{category_id, name}]


class CategorySuggestResponse(BaseModel):
    """AI-powered category suggestion result."""

    category_id: Optional[str] = None
    category_name: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""


class PublishRequest(BaseModel):
    """Optional request body for POST /publish/{product_id}."""

    category_id: Optional[str] = None


class ProductStatus(str, Enum):
    """Lifecycle states for a scraped product."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ExtractRequest(BaseModel):
    """Request body for scraping a supplier page."""

    url: HttpUrl


class GenerateRequest(BaseModel):
    """Request body for approving text and queueing AI generation."""

    raw_text: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    source_url: str = Field(min_length=1)


class ExtractResponse(BaseModel):
    """Response returned after supplier HTML has been extracted to text."""

    raw_text: str
    vendor: str
    source_url: str
    text_length: int


class GenerateResponse(BaseModel):
    """Response returned after a generation job is queued or reused."""

    success: bool
    message: str
    product_id: str
    vendor: str
    text_length: int


class StatusResponse(BaseModel):
    """Polling response for product generation status."""

    status: ProductStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SellingPrice(BaseModel):
    """Normalized pricing structure produced by the AI model."""

    quartz_base_price: float = 0
    vendor_base_price: Optional[float] = None
    after_gst: float = 0
    after_margin: float = 0
    final_selling_price: float = 0
    currency: str = "INR"


class Dimensions(BaseModel):
    """Structured package dimensions in centimetres."""

    L: str = ""
    W: str = ""
    H: str = ""


class AIProduct(BaseModel):
    """Validated AI-generated product listing contract."""

    product_title: str = ""
    seo_title: str = ""
    meta_description: str = ""
    seo_description: str = ""
    hsn_code: str = ""
    sku: str = ""
    brand: str = ""
    weight_g: Union[float, str] = 0.0
    dimensions_cm: Union[str, Dimensions] = ""
    selling_price: SellingPrice = Field(default_factory=SellingPrice)
    tags: List[str] = Field(default_factory=list)
    seo_keywords: List[str] = Field(default_factory=list)
    short_description_html: str = ""
    long_description_html: str = ""

    @field_validator("seo_keywords", mode="before")
    @classmethod
    def flatten_keywords(cls, value: Any) -> List[str]:
        """Accept legacy grouped keyword objects and normalize to a flat list."""

        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, dict):
            keywords: List[str] = []
            for group in value.values():
                if isinstance(group, list):
                    keywords.extend(str(item) for item in group)
                elif group:
                    keywords.append(str(group))
            return keywords
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> List[str]:
        """Normalize tags from list or comma-separated string input."""

        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    def as_mongo(self) -> Dict[str, Any]:
        """Return a plain dictionary safe for MongoDB insertion."""

        return self.model_dump(mode="json")


class RawProductData(BaseModel):
    """Raw product document stored before AI generation."""

    vendor: str
    source: str = "url_scrape"
    source_url: str
    raw_page_text: str
    title: str = ""
    vendor_sku: str = ""
    description_raw: str = ""
    specifications: Dict[str, Any] = Field(default_factory=dict)
    pricing: Dict[str, Any] = Field(default_factory=lambda: {
        "base_price": None,
        "selling_price": None,
        "retail_price": None,
        "currency": "INR",
        "includes_gst": False,
    })
    images: List[str] = Field(default_factory=list)

    def as_mongo(self) -> Dict[str, Any]:
        """Return a plain dictionary safe for MongoDB insertion."""

        return self.model_dump(mode="json")
