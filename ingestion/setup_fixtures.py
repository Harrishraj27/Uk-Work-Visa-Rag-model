"""Setup reviewed public fixtures for offline tests and evaluation.

Verifies checksums and restores data/chunks.jsonl, data/manifest.json,
from reviewed fixtures on a clean clone.
"""
from __future__ import annotations
import hashlib, json, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "data" / "fixtures"
DATA = ROOT / "data"


def verify_fixture_checksums() -> bool:
    checksum_file = FIXTURES / "checksums.json"
    if not checksum_file.exists():
        print("ERROR: data/fixtures/checksums.json is missing.")
        return False

    expected = json.loads(checksum_file.read_text(encoding="utf-8"))
    all_ok = True
    for filename, exp_hash in expected.items():
        fp = FIXTURES / filename
        if not fp.exists():
            print(f"ERROR: Fixture {filename} is missing.")
            all_ok = False
            continue
        actual_hash = hashlib.sha256(fp.read_bytes()).hexdigest()
        if actual_hash != exp_hash:
            print(f"ERROR: Checksum mismatch for {filename} (expected {exp_hash[:12]}, got {actual_hash[:12]}).")
            all_ok = False
        else:
            print(f"VERIFIED: {filename} (sha256: {actual_hash[:12]}...)")
    return all_ok


def setup(force: bool = False) -> None:
    print("=== Verifying reviewed public fixtures ===")
    if not verify_fixture_checksums():
        sys.exit(1)

    DATA.mkdir(parents=True, exist_ok=True)
    for filename in ["chunks.jsonl", "manifest.json"]:
        src = FIXTURES / filename
        dst = DATA / filename
        if not dst.exists() or force:
            shutil.copy2(src, dst)
            print(f"Installed {dst.relative_to(ROOT)} from fixture.")
        else:
            print(f"Preserved existing {dst.relative_to(ROOT)}.")
    print("Done. Clean offline setup complete.")


if __name__ == "__main__":
    force_opt = "--force" in sys.argv
    setup(force=force_opt)
