"""
Azure OpenAI client setup for the OpenAI Agents SDK.

Key concept: We configure the SDK to use Azure OpenAI instead of the default
OpenAI endpoint by creating an AsyncAzureOpenAI client and registering it as
the global default via set_default_openai_client().

The SDK will then use Chat Completions API (not Responses API) with Azure,
which is the correct mode for Azure deployments.
"""
import os
from openai import AsyncAzureOpenAI
from agents import set_default_openai_client, set_tracing_disabled

from config import settings


_configured = False


def configure_azure_client() -> AsyncAzureOpenAI:
    """
    Create and register the Azure OpenAI client with the Agents SDK.

    This must be called once at application startup before any agents run.
    Returns the configured client for reference.
    """
    global _configured

    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
        # No Azure credentials — disable tracing to avoid noise and continue
        # (useful for dev/testing without a real LLM)
        set_tracing_disabled(True)
        return None

    client = AsyncAzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )

    # Register this client as the global default for all agents.
    # This means every Agent(...) created anywhere in the app will use
    # Azure OpenAI automatically without needing explicit client references.
    set_default_openai_client(client)

    _configured = True
    return client


def get_deployment_name() -> str:
    """Return the Azure deployment name to use as the model param for agents."""
    return settings.AZURE_OPENAI_DEPLOYMENT or "gpt-4o"
