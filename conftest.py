"""Tests run offline: real provider settings from a local .env are cleared so no test can call a live API.
Dimensions are NOT forced to a toy size: tests use the real 1536-dim default so dimension bugs are visible."""
import os

for k in ("LLM_API_KEY", "EMBEDDING_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ[k] = ""
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_PROVIDER"] = ""
os.environ["EMBEDDING_DIM"] = "1536"
os.environ["STORE"] = "local"
os.environ["RETRIEVAL_MODE"] = "keyword"
