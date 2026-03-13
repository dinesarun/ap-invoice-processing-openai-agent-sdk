"""
Configuration module — loads Azure OpenAI + LLMWhisperer settings from environment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    # LLMWhisperer
    LLMWHISPERER_API_KEY: str = os.getenv("LLMWHISPERER_API_KEY", "")
    LLMWHISPERER_BASE_URL: str = os.getenv(
        "LLMWHISPERER_BASE_URL", "https://llmwhisperer-api.unstract.com/api/v2"
    )

    # App
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./ap_invoices.db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")


settings = Settings()
