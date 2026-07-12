import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"


class Settings(BaseModel):
    openrouter_api_key: str = Field(..., min_length=1)
    model: str = DEFAULT_MODEL
    base_url: str = OPENROUTER_BASE_URL


def load_settings() -> Settings:
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set.\n"
            "Fix: copy .env.example to .env and add your key:\n"
            "    cp .env.example .env\n"
            "Get a key at https://openrouter.ai/keys"
        )

    return Settings(openrouter_api_key=api_key)
