import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def packager():
    path = Path(__file__).parents[2] / "scripts" / "package_submission.py"
    spec = importlib.util.spec_from_file_location("submission_packager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checkout(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-qm", "Initial test commit"], cwd=tmp_path, check=True,
    )
    return tmp_path


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_cli_manifest_includes_current_source_and_excludes_private_runtime(
    packager, checkout, capsys
):
    write(checkout, ".gitignore", b".env\nconfig/model-rates.json\ndata/*\noutput/*\n")
    write(checkout, "app.py", b"print('source')\n")
    write(checkout, ".env.submission.example", b"CODECRAFT_API_KEY=\n")
    write(checkout, ".env", b"private local configuration")
    write(checkout, "config/model-rates.json", b"private rate configuration")
    write(checkout, "data/exports/report.html", b"private source passages")
    write(checkout, "output/old.zip", b"old local archive")
    packager.main(["--output", "output/custom-submission.zip"], root=checkout)
    result = json.loads(capsys.readouterr().out)
    assert result["submitted_or_published"] is False
    archive = checkout / "output/custom-submission.zip"
    assert result["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {
            ".gitignore", "app.py", ".env.submission.example", "SOURCE-MANIFEST.json",
        }
        manifest = json.loads(bundle.read("SOURCE-MANIFEST.json"))
        assert manifest["git_commit"] == result["git_commit"]
        assert manifest["submitted_or_published"] is False
        assert manifest["includes_current_uncommitted_source"] is True
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(bundle.read(name)).hexdigest() == digest


@pytest.mark.parametrize("prefix", [b"cc_", b"nvapi-", b"tvly-dev-", b"tvly-prod-"])
def test_credential_shapes_cannot_enter_archive(packager, checkout, prefix):
    write(checkout, "accidental-secret.txt", prefix + b"x" * 48)
    archive = checkout / "output/rejected.zip"
    with pytest.raises(RuntimeError, match="Credential-shaped data"):
        packager.create_archive(checkout, archive)
    assert not archive.exists()


@pytest.mark.parametrize("name", [
    ".env", ".env.backup", "config/model-rates.json", "cache.sqlite", "node_modules/a.js",
])
def test_private_files_fail_closed_even_if_not_gitignored(packager, checkout, name):
    write(checkout, name, b"must stay private")
    with pytest.raises(RuntimeError, match="Credential/runtime file"):
        packager.create_archive(checkout, checkout / "output/rejected.zip")


def test_tracked_local_reports_are_excluded_even_if_gitignore_is_missing(packager, checkout):
    write(checkout, "app.py", b"source")
    write(checkout, "data/.gitkeep", b"")
    write(checkout, "data/raw/disclosure.pdf", b"private downloaded document")
    write(checkout, "data/exports/report.html", b"private saved report")
    subprocess.run(["git", "add", "data"], cwd=checkout, check=True)
    archive = checkout / "output/source.zip"
    packager.create_archive(checkout, archive)
    with zipfile.ZipFile(archive) as bundle:
        assert "data/.gitkeep" in bundle.namelist()
        assert not any(name.startswith("data/") and name != "data/.gitkeep"
                       for name in bundle.namelist())


def test_symlinked_file_is_rejected(packager, checkout):
    target = write(checkout, "real.txt", b"source")
    try:
        (checkout / "linked.txt").symlink_to(target)
    except OSError:
        pytest.skip("OS does not permit creating symlinks")
    with pytest.raises(RuntimeError, match="symlinked"):
        packager.create_archive(checkout, checkout / "output/rejected.zip")


def test_secret_rejection_does_not_replace_existing_archive(packager, checkout):
    archive = write(checkout, "output/source.zip", b"previous artifact")
    write(checkout, ".gitignore", b"output/*\n")
    write(checkout, "oops.txt", b"cc_" + b"z" * 48)
    with pytest.raises(RuntimeError, match="Credential-shaped data"):
        packager.create_archive(checkout, archive)
    assert archive.read_bytes() == b"previous artifact"
