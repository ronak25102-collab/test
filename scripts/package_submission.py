"""Create a local, credential-checked source archive from the current checkout."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

SECRET_PATTERN = re.compile(
    rb"(?:cc_[A-Za-z0-9_-]{32,}|nvapi-[A-Za-z0-9_-]{20,}|"
    rb"tvly-(?:dev|prod)-[A-Za-z0-9_-]{20,})"
)
ENV_EXAMPLES = {".env.example", ".env.submission.example"}
RUNTIME_PARTS = {
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
    "dist", "test-results", "playwright-report",
}


def source_entries(root: Path, archive: Path) -> dict[str, bytes]:
    """Git's ignore rules are the first filter; explicit guards fail closed too."""
    files = subprocess.check_output(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root
    ).decode("utf-8").split("\0")
    entries = {}
    for name in sorted(set(files) - {""}):
        relative = Path(name)
        path = root / relative
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Refusing an external source path")
        # Check every component: a symlinked directory can hide ordinary-looking files.
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
            raise RuntimeError("Refusing an external or symlinked source path")
        if not path.resolve().is_relative_to(root):
            raise RuntimeError("Refusing an external source path")
        if path.resolve() == archive or not path.is_file():
            continue
        if (
            (relative.name.startswith(".env") and name not in ENV_EXAMPLES)
            or name == "config/model-rates.json"
            or RUNTIME_PARTS.intersection(relative.parts)
            or relative.suffix in {".db", ".sqlite", ".sqlite3", ".pyc"}
            or relative.name.startswith(".env.") and name not in ENV_EXAMPLES
        ):
            raise RuntimeError("Credential/runtime file appeared in source list")
        # Raw documents, extracted passages, local reports and generated bundles are private.
        if relative.parts[0] in {"data", "output"} and name not in {
            "data/.gitkeep", "output/.gitkeep"
        }:
            continue
        if name == "SOURCE-MANIFEST.json":
            raise RuntimeError("Reserved source manifest appeared in source list")
        data = path.read_bytes()
        if SECRET_PATTERN.search(data):
            raise RuntimeError("Credential-shaped data found; archive was not created")
        entries[name] = data
    return entries


def create_archive(root: Path, archive: Path) -> dict:
    root = root.resolve()
    archive = archive.resolve()
    entries = source_entries(root, archive)
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit,
        "includes_current_uncommitted_source": True,
        "submitted_or_published": False,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()},
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=archive.parent, suffix=".zip", delete=False) as temp:
            temporary = Path(temp.name)
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
            for name, data in entries.items():
                bundle.writestr(name, data)
            bundle.writestr("SOURCE-MANIFEST.json", json.dumps(manifest, indent=2))
        temporary.replace(archive)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "local_archive": str(archive),
        "source_files": len(entries),
        "git_commit": git_commit,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "submitted_or_published": False,
    }


def main(argv=None, *, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("output/Beyond-Final-Submission.zip"),
        help="Archive filename; relative paths are resolved from the repository root.",
    )
    args = parser.parse_args(argv)
    root = Path(root or Path(__file__).resolve().parents[1])
    archive = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(create_archive(root, archive), indent=2))


if __name__ == '__main__':
    main()
