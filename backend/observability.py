"""
Observability — Langfuse v4 SDK + OpenInference instrumentation for the Agents SDK.

How it works (v4):
  - Langfuse() initialises itself as the global OTel TracerProvider automatically.
  - OpenAIAgentsInstrumentor registers an OpenInference trace processor with the
    Agents SDK, converting every agent run / handoff / tool call into OTel spans.
  - Those spans are picked up by the Langfuse provider and exported in real time.
  - should_export_span=lambda span: True ensures the openinference spans are not
    filtered out by v4's default smart-filter (which only keeps gen_ai.* spans).

Configuration (.env):
  LANGFUSE_PUBLIC_KEY    pk-lf-...
  LANGFUSE_SECRET_KEY    sk-lf-...
  LANGFUSE_BASE_URL      https://us.cloud.langfuse.com   (or EU: https://cloud.langfuse.com)

All three are optional — the app runs normally without them.
"""
import os
import logging
import traceback as _traceback

logger = logging.getLogger(__name__)

_langfuse = None
_setup_error: str = ""


def setup_observability() -> None:
    """
    Initialise Langfuse v4 tracing. Safe to call unconditionally —
    silently skips if keys are not configured or packages are missing.
    """
    global _langfuse, _setup_error

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key  = os.getenv("LANGFUSE_SECRET_KEY", "").strip()

    print(f"   [Langfuse] PK present: {bool(public_key)}, SK present: {bool(secret_key)}")

    if not public_key or not secret_key:
        _setup_error = "Keys not configured"
        logger.info(
            "Langfuse not configured — observability inactive "
            "(set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY to enable)"
        )
        return

    try:
        from langfuse import Langfuse
        from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

        # Langfuse() reads PUBLIC_KEY / SECRET_KEY / BASE_URL from env automatically.
        # should_export_span=True exports all spans, including the openinference ones
        # that the v4 smart-filter would otherwise drop.
        _langfuse = Langfuse(should_export_span=lambda span: True)

        if not _langfuse.auth_check():
            _setup_error = "Auth check failed — verify keys and BASE_URL"
            logger.warning("⚠️  Langfuse auth check failed — verify your keys and BASE_URL")
            print(f"   [Langfuse] ❌ Auth check failed")
            _langfuse = None
            return

        # Instrument the Agents SDK — hooks into the Langfuse OTel provider set above.
        OpenAIAgentsInstrumentor().instrument()

        base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
        logger.info(f"✅ Langfuse v4 observability active → {base_url}")
        print(f"   [Langfuse] ✅ Active → {base_url}")

    except ImportError as e:
        _setup_error = f"Package missing: {e}"
        logger.warning(
            f"Langfuse package missing ({e}). "
            "Run: pip install langfuse openinference-instrumentation-openai-agents"
        )
        print(f"   [Langfuse] ❌ Import error: {e}")
    except Exception as e:
        _setup_error = str(e)
        logger.warning(f"Langfuse setup failed: {e}")
        print(f"   [Langfuse] ❌ Setup failed: {e}")
        print(_traceback.format_exc())


def flush_observability() -> None:
    """Flush buffered spans on shutdown so the last traces are not lost."""
    global _langfuse
    if _langfuse:
        try:
            _langfuse.flush()
            logger.info("Langfuse spans flushed")
        except Exception as e:
            logger.warning(f"Langfuse flush failed: {e}")


def is_observability_active() -> bool:
    return _langfuse is not None


def get_setup_error() -> str:
    return _setup_error
