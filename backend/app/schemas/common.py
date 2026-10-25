from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = "User"


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class BrandProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[uuid.UUID] = None
    brand_name: str = "IncuBrix"
    target_audience: str
    tone_of_voice: str = "Educational, High-Signal, Action-Oriented"
    vocabulary_rules: Optional[str] = None
    words_to_avoid: List[str] = Field(default_factory=list)
    default_cta: str = "Learn more → incubrix.com/start"
    primary_color: str = "#4F46E5"
    secondary_color: str = "#0F172A"
    verified_product_facts: List[str] = Field(default_factory=list)


class CampaignCreate(BaseModel):
    name: str
    source_document_id: Optional[uuid.UUID] = None
    brand_profile_id: Optional[uuid.UUID] = None
    duration_days: int = Field(default=30, ge=1, le=90)
    platforms: List[str] = Field(default_factory=lambda: ["instagram", "facebook", "youtube"])
    formats: List[str] = Field(default_factory=lambda: ["text", "image", "carousel", "short_video"])
    timezone_name: str = "UTC"
    destination_url: Optional[str] = "https://incubrix.com/start"


class AssetUpdate(BaseModel):
    hook: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    cta: Optional[str] = None
    tracking_url: Optional[str] = None
    approval_status: Optional[str] = None


class ReschedulePostRequest(BaseModel):
    scheduled_utc: datetime
    timezone_name: Optional[str] = "UTC"
    connected_account_id: Optional[uuid.UUID] = None
