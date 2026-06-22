from typing import Literal

from pydantic import BaseModel, Field


class LLMConnectionTestRequest(BaseModel):
    provider_type: Literal["openai_compatible"] = "openai_compatible"
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)


class LLMConnectionTestResponse(BaseModel):
    success: bool
    provider_type: Literal["openai_compatible"]
    base_url: str
    model: str
    message: str
