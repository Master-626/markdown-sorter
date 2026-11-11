"""Exclude globs keep selected notes in place without changing the default."""

from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner

from markdown_sorter.cli import cli
from markdown_sorter.config import DEFAULT_CONFIG, load_config
from markdown_sorter.core import MarkdownSorter, SortError
from markdown_sorter.utils import is_excluded, validate_exclude_pattern


def _tagged(path: Path, tag: str = "Work", body: str = "note") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntags: [{tag}]\n---\n{body}\n", encoding="utf-8")


def test_default_config_still_sorts_readme(tmp_path):
    source = tmp_path / "README.md"
    _tagged(source)
    assert MarkdownSorter(tmp_path, deepcopy(DEFAULT_CONFIG)).run() == (1, 0)
    assert (tmp_path / "Work" / "README.md").is_file()
    assert load_config()["general"]["exclude"] == []


@pytest.mark.parametrize(
    ("relative", "pattern", "expected"),
    [
        ("docs/README.md", "README.md", True),
        ("docs/readme.MD", "README.md", True),
        ("docs/README.md", "*.txt", False),
        ("docs/a.md", "docs/*.md", True),
        ("docs/sub/a.md", "docs/*.md", False),
        ("docs/sub/a.md", "docs/**", True),
        ("drafts/a.md", "drafts/**", True),
        ("drafts.md", "drafts/**", False),
        ("a/b/c.md", "**/*.md", True),
        ("c.md", "**/*.md", True),
        ("a.md", "?.md", True),
        ("ab.md", "?.md", False),
    ],
)
def test_exclude_glob_matching(relative, pattern, expected):
    assert is_excluded(relative, [pattern]) is expected


@pytest.mark.parametrize("pattern", ["../x", "/abs", r"a\b", "", "a//b", "C:/x", "bad:name", " "])
def test_unsafe_exclude_patterns_are_rejected(pattern):
    with pytest.raises(ValueError, match="Unsafe exclude pattern"):
        validate_exclude_pattern(pattern)


def test_exclude_leaves_matches_and_sorts_the_rest(tmp_path, capsys):
    readme = tmp_path / "README.md"
    note = tmp_path / "note.md"
    nested = tmp_path / "templates" / "a.md"
    named_like_dir = tmp_path / "templates.md"
    _tagged(readme, body="readme")
    _tagged(note, body="note")
    _tagged(nested, body="template")
    _tagged(named_like_dir, body="not a directory")
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["exclude"] = ["README.md", "templates/**"]

    assert MarkdownSorter(tmp_path, config).run() == (2, 2)
    output = capsys.readouterr().out
    assert f"[SKIP] {Path('README.md')} (excluded)" in output
    assert f"[SKIP] {Path('templates/a.md')} (excluded)" in output
    assert readme.read_text(encoding="utf-8").endswith("readme\n")
    assert nested.read_text(encoding="utf-8").endswith("template\n")
    assert (tmp_path / "Work" / "note.md").read_text(encoding="utf-8").endswith("note\n")
    assert (
        (tmp_path / "Work" / "templates.md")
        .read_text(encoding="utf-8")
        .endswith("not a directory\n")
    )
    assert not (tmp_path / "Work" / "README.md").exists()
    assert not (tmp_path / "Work" / "a.md").exists()


def test_dry_run_exclude_creates_nothing(tmp_path, capsys):
    source = tmp_path / "README.md"
    _tagged(source)
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["exclude"] = ["README.md"]
    assert MarkdownSorter(tmp_path, config, dry_run=True).run() == (0, 1)
    assert source.is_file()
    assert not (tmp_path / "Work").exists()
    output = capsys.readouterr().out
    assert f"[SKIP] {Path('README.md')} (excluded)" in output
    assert "DRY-RUN" not in output
    assert "MOVE" not in output


def test_excluded_invalid_front_matter_does_not_block_other_notes(tmp_path):
    readme = tmp_path / "README.md"
    note = tmp_path / "note.md"
    readme.write_text("---\ntags: [python\n---\n", encoding="utf-8")
    _tagged(note)
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["exclude"] = ["README.md"]
    assert MarkdownSorter(tmp_path, config).run() == (1, 1)
    assert readme.is_file()
    assert (tmp_path / "Work" / "note.md").is_file()


def test_excluded_file_still_blocks_a_colliding_destination(tmp_path):
    kept = tmp_path / "Work" / "note.md"
    source = tmp_path / "note.md"
    _tagged(kept, tag="Other", body="kept")
    _tagged(source, body="new")
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["exclude"] = ["Work/**"]
    with pytest.raises(SortError, match="Destination already exists"):
        MarkdownSorter(tmp_path, config).run()
    assert "kept" in kept.read_text(encoding="utf-8")
    assert "new" in source.read_text(encoding="utf-8")
    assert not (tmp_path / "Other").exists()


def test_unsafe_exclude_aborts_before_moving(tmp_path):
    source = tmp_path / "note.md"
    _tagged(source)
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["exclude"] = ["../escape"]
    with pytest.raises(SortError, match="Unsafe exclude pattern"):
        MarkdownSorter(tmp_path, config).run()
    assert source.is_file()
    assert not (tmp_path / "Work").exists()


def test_cli_exclude_appends_to_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[general]\nexclude = ["README.md"]\n', encoding="utf-8")
    readme = tmp_path / "README.md"
    draft = tmp_path / "drafts" / "a.md"
    note = tmp_path / "note.md"
    _tagged(readme)
    _tagged(draft)
    _tagged(note)
    result = CliRunner().invoke(
        cli,
        ["sort", str(tmp_path), "--config", str(config_path), "--exclude", "drafts/**"],
    )
    assert result.exit_code == 0, result.output
    assert readme.is_file()
    assert draft.is_file()
    assert (tmp_path / "Work" / "note.md").is_file()
    assert "完成" in result.output
    assert "跳过了 2" in result.output
