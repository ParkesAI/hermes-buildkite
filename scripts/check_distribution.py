"""Check release metadata and installed wheel discovery, without provider credentials."""

import pathlib
import tarfile
import tomllib
import zipfile

import yaml

root = pathlib.Path(__file__).resolve().parents[1]
project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
manifest = yaml.safe_load((root / "plugin.yaml").read_text())
assert project["version"] == manifest["version"], "Package and plugin versions disagree"
assert project["license"] == manifest["license"] == "MIT"
assert project["entry-points"]["hermes_agent.plugins"]["hermes-buildkite"] == "hermes_buildkite"
wheel = root / "dist" / f"hermes_buildkite-{project['version']}-py3-none-any.whl"
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    assert "hermes_buildkite/plugin.yaml" in names
    assert "hermes_buildkite/receiver.py" in names
    assert yaml.safe_load(archive.read("hermes_buildkite/plugin.yaml")) == manifest
    assert not any(name.endswith((".env", ".key", ".pem", ".log")) for name in names)
    assert not any(name.startswith(("tests/", ".git/", ".venv/")) for name in names)
source = root / "dist" / f"hermes_buildkite-{project['version']}.tar.gz"
with tarfile.open(source) as archive:
    names = {"/".join(member.name.split("/")[1:]) for member in archive.getmembers()}
    assert {
        "pyproject.toml",
        "uv.lock",
        "scripts/check_distribution.py",
        "docs/VERIFICATION.md",
    } <= names
print(f"Release metadata and wheel contents verified for {project['version']}")
