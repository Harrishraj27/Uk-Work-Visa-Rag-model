"""Script to create and verify a clean sharing zip archive of uk-work-visa-rag.
Ensures zero secrets, zero virtual environments, and zero cache artifacts are included.
"""
from __future__ import annotations
import hashlib, os, pathlib, re, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARCHIVE_PATH = DIST / "uk-work-visa-rag.zip"

EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".cursor", "dist", "staged"
}
EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db"
}
SECRET_ENV_KEYS = ("LLM_API_KEY", "EMBEDDING_API_KEY", "SUPABASE_ANON_KEY", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY")


def env_has_filled_secret(text: str) -> list:
    """The shipped .env must have every secret field blank. Returns names only, never values."""
    bad = []
    for line in text.splitlines():
        k, _, v = line.partition("=")
        if k.strip() in SECRET_ENV_KEYS and v.split("#")[0].strip():
            bad.append(k.strip())
    return bad
EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd"
}

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"AIzaSy[a-zA-Z0-9_\-]{33}"),
    re.compile(r"SECRET_[a-zA-Z0-9_]+"),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{25,}"),
]


def should_include(rel_path: pathlib.Path) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return False
    if rel_path.name in EXCLUDE_FILES:
        return False
    if rel_path.suffix in EXCLUDE_EXTENSIONS:
        return False
    if rel_path.name.startswith(".env") and rel_path.name not in (".env.example", ".env"):
        return False
    return True


def create_and_inspect_zip():
    DIST.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()

    included_files = []
    for root, dirs, files in os.walk(ROOT):
        # Prune excluded directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            full_path = pathlib.Path(root) / f
            rel_path = full_path.relative_to(ROOT)
            if should_include(rel_path):
                included_files.append((full_path, rel_path))

    with zipfile.ZipFile(ARCHIVE_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full_p, rel_p in sorted(included_files, key=lambda x: str(x[1])):
            zf.write(full_p, arcname=str(rel_p.as_posix()))

    # Audit the generated archive
    print(f"Archive created at: {ARCHIVE_PATH}")
    print(f"Total files included: {len(included_files)}")

    secret_violations = []
    dependency_violations = []
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(ARCHIVE_PATH, "r") as zf:
        namelist = zf.namelist()
        for name in namelist:
            info = zf.getinfo(name)
            total_uncompressed_bytes += info.file_size

            # Check paths
            if name.split("/")[-1].startswith(".env") and name.split("/")[-1] not in (".env", ".env.example"):
                dependency_violations.append(f"Unexpected env file found: {name}")
            if name.endswith("/.env") or name == ".env":
                filled = env_has_filled_secret(zf.read(name).decode("utf-8", errors="ignore"))
                if filled:
                    dependency_violations.append(f".env has filled secret fields (names only): {filled}")
            if ".venv" in name or "site-packages" in name:
                dependency_violations.append(f"Virtualenv dependency found: {name}")
            if "__pycache__" in name or name.endswith(".pyc"):
                dependency_violations.append(f"Cache file found: {name}")

            # Check content of text files for leaked synthetic or live secrets
            if name.endswith((".py", ".json", ".md", ".txt", ".html", ".css", ".sql", ".example", ".env")):
                try:
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    for pat in SECRET_PATTERNS:
                        # Allow test/script definition of pattern in test_safety, run_answer_eval, or packaging script
                        if any(k in name for k in ("test_safety.py", "run_answer_eval.py", "package_clean_zip.py")):
                            continue
                        matches = pat.findall(content)
                        if matches:
                            secret_violations.append(f"Potential secret in {name}: {matches}")
                except Exception as e:
                    pass

    # SHA256 of zip
    sha256 = hashlib.sha256(ARCHIVE_PATH.read_bytes()).hexdigest()
    zip_size_kb = ARCHIVE_PATH.stat().st_size / 1024

    print("\n--- SHARING ZIP AUDIT REPORT ---")
    print(f"Archive Size: {zip_size_kb:.1f} KB (Uncompressed: {total_uncompressed_bytes/1024:.1f} KB)")
    print(f"SHA-256 Checksum: {sha256}")
    print(f"Dependency/Cache Violations: {len(dependency_violations)}")
    print(f"Secret Violations: {len(secret_violations)}")

    if dependency_violations or secret_violations:
        print("\nAUDIT FAILED:")
        for v in dependency_violations + secret_violations:
            print(f" - {v}")
        raise SystemExit(1)
    else:
        print("\nAUDIT RESULT: CLEAN & READY FOR SHARING")


if __name__ == "__main__":
    create_and_inspect_zip()
