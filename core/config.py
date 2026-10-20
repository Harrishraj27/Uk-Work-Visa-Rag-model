"""All settings come from environment variables (see .env.example). Nothing is hard-coded about models or prices."""
from __future__ import annotations
import os, pathlib
from dataclasses import dataclass
from typing import Mapping, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv(path: Optional[pathlib.Path] = None) -> None:
    """Load KEY=VALUE pairs from .env into os.environ if the key is not already set. Never logs values."""
    p = path or (ROOT / ".env")
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        else:
            val = val.split("#")[0].strip()
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


class ConfigError(RuntimeError):
    pass


def _s(env: Mapping[str, str], name: str, default: str = "") -> str:
    v = env.get(name)
    return v.strip() if v and v.strip() else default


def _f(env, name) -> Optional[float]:
    v = _s(env, name)
    return float(v) if v else None


@dataclass(frozen=True)
class Settings:
    corpus_version: str = ""
    chunks_path: str = str(ROOT / "data" / "chunks.jsonl")
    embeddings_path: str = str(ROOT / "data" / "embeddings.jsonl")
    manifest_path: str = str(ROOT / "data" / "manifest.json")
    check_log_path: str = str(ROOT / "data" / "check_log.json")
    sponsors_path: str = str(ROOT / "data" / "sponsors.csv")
    store: str = "local"               # local | supabase
    retrieval_mode: str = "keyword"    # keyword | hybrid
    top_k: int = 5
    llm_provider: str = ""             # "" (retrieval-only) | openai | anthropic | fake
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_max_tokens_param: str = "max_tokens"   # some newer OpenAI models want max_completion_tokens
    llm_temperature: Optional[float] = None
    max_output_tokens: int = 400
    embedding_provider: str = ""       # "" | openai | fake
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_dim: int = 1536
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""
    supabase_fallback_local: bool = False
    stale_days: int = 45
    daily_token_budget: int = 200_000
    rate_limit_per_min: int = 10
    price_in_per_mtok: Optional[float] = None    # your provider's CURRENT rate, per million tokens
    price_out_per_mtok: Optional[float] = None


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    e = os.environ if env is None else env
    d = Settings()
    return Settings(
        corpus_version=_s(e, "CORPUS_VERSION"),
        chunks_path=_s(e, "CHUNKS_PATH", d.chunks_path),
        embeddings_path=_s(e, "EMBEDDINGS_PATH", d.embeddings_path),
        manifest_path=_s(e, "MANIFEST_PATH", d.manifest_path),
        check_log_path=_s(e, "CHECK_LOG_PATH", d.check_log_path),
        sponsors_path=_s(e, "SPONSORS_PATH", d.sponsors_path),
        store=_s(e, "STORE", "local"),
        retrieval_mode=_s(e, "RETRIEVAL_MODE", "keyword"),
        top_k=int(_s(e, "TOP_K", "5")),
        llm_provider=_s(e, "LLM_PROVIDER"),
        llm_model=_s(e, "LLM_MODEL"),
        llm_api_key=_s(e, "LLM_API_KEY"),
        llm_base_url=_s(e, "LLM_BASE_URL", d.llm_base_url),
        llm_max_tokens_param=_s(e, "LLM_MAX_TOKENS_PARAM", "max_tokens"),
        llm_temperature=_f(e, "LLM_TEMPERATURE"),
        max_output_tokens=int(_s(e, "MAX_OUTPUT_TOKENS", "400")),
        embedding_provider=_s(e, "EMBEDDING_PROVIDER"),
        embedding_model=_s(e, "EMBEDDING_MODEL"),
        embedding_api_key=_s(e, "EMBEDDING_API_KEY"),
        embedding_base_url=_s(e, "EMBEDDING_BASE_URL", d.embedding_base_url),
        embedding_dim=int(_s(e, "EMBEDDING_DIM", "1536")),
        supabase_url=_s(e, "SUPABASE_URL").rstrip("/"),
        supabase_key=_s(e, "SUPABASE_ANON_KEY") or _s(e, "SUPABASE_KEY"),   # app uses the public anon key only
        supabase_service_key=_s(e, "SUPABASE_SERVICE_ROLE_KEY"),     # ingestion only, never the web app
        supabase_fallback_local=_s(e, "SUPABASE_FALLBACK_LOCAL", "false").lower() in ("1", "true", "yes"),
        stale_days=int(_s(e, "STALE_DAYS", "45")),
        daily_token_budget=int(_s(e, "DAILY_TOKEN_BUDGET", "200000")),
        rate_limit_per_min=int(_s(e, "RATE_LIMIT_PER_MIN", "10")),
        price_in_per_mtok=_f(e, "PRICE_IN_PER_MTOK"),
        price_out_per_mtok=_f(e, "PRICE_OUT_PER_MTOK"),
    )


def estimate_cost(settings: Settings, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Estimated model cost in the currency of the configured per-million-token prices; None if prices unset."""
    if settings.price_in_per_mtok is None or settings.price_out_per_mtok is None:
        return None
    return (input_tokens * settings.price_in_per_mtok + output_tokens * settings.price_out_per_mtok) / 1_000_000
