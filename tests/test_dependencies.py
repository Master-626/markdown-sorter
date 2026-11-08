"""Protect the advertised Python floor and normal CLI installation."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@pytest.mark.parametrize("python_version", ["3.9", "3.10", "3.11", "3.12", "3.13"])
def test_frontmatter_requirement_respects_python_version(python_version):
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    config = tomllib.loads(project.read_text(encoding="utf-8"))
    requirements = [Requirement(item) for item in config["project"]["dependencies"]]
    active = [
        requirement
        for requirement in requirements
        if requirement.name == "python-frontmatter"
        and (
            requirement.marker is None
            or requirement.marker.evaluate({"python_version": python_version})
        )
    ]
    assert len(active) == 1
    assert "1.0.0" in active[0].specifier
    assert "1.1.0" in active[0].specifier
    if python_version == "3.9":
        assert "1.2.0" not in active[0].specifier
        assert "1.3.0" not in active[0].specifier
    else:
        assert "1.2.0" in active[0].specifier
        assert "1.3.0" in active[0].specifier


@pytest.mark.parametrize("arguments", [["--version"], ["--help"], ["sort", "--help"]])
def test_installed_cli_starts_outside_checkout(tmp_path, arguments):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-m", "markdown_sorter.cli", *arguments],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
