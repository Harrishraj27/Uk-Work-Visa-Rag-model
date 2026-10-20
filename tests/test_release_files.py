"""Static checks on the files that ship: env template, Docker, SQL, ignore rules."""
import pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
read = lambda p: (ROOT / p).read_text(encoding="utf-8")
KEY_FIELDS = ("LLM_API_KEY", "EMBEDDING_API_KEY", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")


def _vals(text):
    return {m.group(1): m.group(2).split("#")[0].strip() for m in re.finditer(r"^([A-Z_]+)=(.*)$", text, re.M)}


def test_env_files_have_blank_secret_fields_and_offline_defaults():
    for name in (".env.example", ".env"):
        v = _vals(read(name))
        for k in KEY_FIELDS:
            assert k in v and v[k] == "", f"{name}:{k} must exist and be blank"
        assert v["LLM_PROVIDER"] == "fake" and v["STORE"] == "local" and v["RETRIEVAL_MODE"] == "keyword"


def test_sql_has_rls_dimension_and_ordered_candidate_limits():
    sql = read("supabase/schema.sql")
    assert "enable row level security" in sql and sql.count("vector(1536)") == 2
    assert sql.count("order by r limit 20") == 2
    assert "grant execute on function hybrid_search" in sql
    assert "service_role" not in sql.split("Access control")[1].split("create policy")[0].lower().replace("service_role key", "")


def test_docker_copies_everything_the_app_needs_and_gitignore_keeps_it():
    d, gi, di = read("Dockerfile"), read(".gitignore"), read(".dockerignore")
    for need in ("COPY core", "COPY app", "COPY data/fixtures", "COPY data/chunks.jsonl"):
        assert need in d
    assert not re.search(r"^data/chunks\.jsonl\s*$", gi, re.M), "chunks.jsonl is needed by a fresh Docker build"
    assert ".env" in di and ".venv" in di


def test_requirements_are_exact_pins():
    for line in read("requirements.txt").splitlines():
        if line.strip() and not line.startswith("#"):
            assert "==" in line, line


def test_service_role_key_is_not_read_by_the_web_app():
    s = read("core/config.py")
    assert 'supabase_key=_s(e, "SUPABASE_ANON_KEY")' in s
    assert "SERVICE_ROLE" not in read("app/main.py") + read("app/retrieval.py")
