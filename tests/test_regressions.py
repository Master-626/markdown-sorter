"""Demonstrable sorting bugs: wrong folders, swallowed errors, and unsafe paths."""

from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from markdown_sorter.cli import cli
from markdown_sorter.config import DEFAULT_CONFIG, load_config
from markdown_sorter.core import MarkdownSorter, SortError
from markdown_sorter.utils import _sort_timestamp, get_file_date_folder


def _sorter(root, mode="tag", rules=None, **general):
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = mode
    config["general"].update(general)
    if rules is not None:
        config["rules"] = rules
    return MarkdownSorter(root, config)


def _paths(root):
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


@pytest.mark.parametrize(
    ("literal", "folder"),
    [
        ("yes", "yes"),
        ("no", "no"),
        ("on", "on"),
        ("off", "off"),
        ("true", "true"),
        ("01", "01"),
        ("1.10", "1.10"),
    ],
)
def test_yaml_scalars_keep_their_written_form(tmp_path, literal, folder):
    source = tmp_path / "note.md"
    source.write_text(f"---\ntags: [{literal}]\n---\nbody\n", encoding="utf-8")
    original = source.read_bytes()
    assert _sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / folder / "note.md").read_bytes() == original
    # Skip case-insensitive aliases of the expected folder (true/True on Windows).
    if folder.casefold() not in {"true", "false"}:
        assert not (tmp_path / "True").exists()
        assert not (tmp_path / "False").exists()
    if folder not in {"1", "1.1"}:
        assert not (tmp_path / "1").exists()
        assert not (tmp_path / "1.1").exists()


def test_scalar_yes_is_a_tag_not_unsorted(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: yes\n---\n", encoding="utf-8")
    assert _sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / "yes" / "note.md").is_file()
    assert not (tmp_path / "Unsorted").exists()
    assert not (tmp_path / "True").exists()


def test_sexagesimal_tag_is_not_rewritten_to_an_integer(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [1:30]\n---\n", encoding="utf-8")
    before = _paths(tmp_path)
    with pytest.raises(SortError, match="Unsafe category"):
        _sorter(tmp_path).run()
    assert _paths(tmp_path) == before
    assert not (tmp_path / "90").exists()


def test_null_tags_value_means_untagged(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: null\n---\n", encoding="utf-8")
    assert _sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / "Unsorted" / "note.md").is_file()
    assert not (tmp_path / "None").exists()
    assert not (tmp_path / "null").exists()


def test_null_tag_entry_aborts_instead_of_creating_none(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [python, null]\n---\n", encoding="utf-8")
    before = source.read_bytes()
    with pytest.raises(SortError, match="not null"):
        _sorter(tmp_path).run()
    assert source.read_bytes() == before
    assert _paths(tmp_path) == {"note.md"}


def test_invalid_front_matter_aborts_the_whole_batch(tmp_path):
    good = tmp_path / "a-good.md"
    bad = tmp_path / "z-bad.md"
    good.write_text("---\ntags: [Work]\n---\nkeep\n", encoding="utf-8")
    bad.write_text("---\ntags: [python\n---\n", encoding="utf-8")
    before = _paths(tmp_path)
    with pytest.raises(SortError, match="Invalid front matter"):
        _sorter(tmp_path).run()
    assert _paths(tmp_path) == before
    assert good.read_text(encoding="utf-8").endswith("keep\n")


def test_leading_thematic_break_is_not_front_matter(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\n# Title\n\nHello\n", encoding="utf-8")
    assert _sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / "Unsorted" / "note.md").is_file()


def test_utf8_bom_does_not_hide_tags(tmp_path):
    source = tmp_path / "note.md"
    original = b"\xef\xbb\xbf---\ntags: [Work]\n---\nkept\n"
    source.write_bytes(original)
    assert _sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / "Work" / "note.md").read_bytes() == original
    assert not (tmp_path / "Unsorted").exists()


def test_undecodable_note_aborts_without_moving_siblings(tmp_path):
    bad = tmp_path / "bad.md"
    good = tmp_path / "good.md"
    bad.write_bytes(b"\xff\xfe")
    good.write_text("---\ntags: [Work]\n---\n", encoding="utf-8")
    before = _paths(tmp_path)
    with pytest.raises(SortError, match="UTF-8"):
        _sorter(tmp_path).run()
    assert _paths(tmp_path) == before


def test_rule_keyword_matches_tag_substring(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [python-dev]\n---\n", encoding="utf-8")
    sorter = _sorter(tmp_path, mode="rule", rules={"Lang/Python": ["Python"]})
    assert sorter.run() == (1, 0)
    assert (tmp_path / "Lang" / "Python" / "note.md").is_file()
    assert not (tmp_path / "Unsorted").exists()


def test_rule_keyword_does_not_match_unrelated_tag(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [network]\n---\n", encoding="utf-8")
    assert _sorter(tmp_path, mode="rule", rules={"Work": ["work"]}).run() == (1, 0)
    assert (tmp_path / "Unsorted" / "note.md").is_file()


def test_rule_keyword_matches_a_tag_segment(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [work-notes]\n---\n", encoding="utf-8")
    assert _sorter(tmp_path, mode="rule", rules={"Work": ["work"]}).run() == (1, 0)
    assert (tmp_path / "Work" / "note.md").is_file()


def test_rule_filename_still_uses_substring_match(tmp_path):
    source = tmp_path / "network.md"
    source.write_text("# notes\n", encoding="utf-8")
    assert _sorter(tmp_path, mode="rule", rules={"Work": ["work"]}).run() == (1, 0)
    assert (tmp_path / "Work" / "network.md").is_file()


def test_rule_keyword_does_not_match_inside_a_word(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [homework]\n---\n", encoding="utf-8")
    assert _sorter(tmp_path, mode="rule", rules={"Work": ["work"]}).run() == (1, 0)
    assert (tmp_path / "Unsorted" / "note.md").is_file()


@pytest.mark.parametrize("keywords", ["python", [""], ["  "], [1]])
def test_malformed_rule_keywords_do_not_match_everything(tmp_path, keywords):
    source = tmp_path / "n.md"
    source.write_text("python notes", encoding="utf-8")
    before = source.read_bytes()
    with pytest.raises(SortError, match="non-empty strings"):
        _sorter(tmp_path, mode="rule", rules={"X": keywords}).run()
    assert source.read_bytes() == before
    assert not (tmp_path / "X").exists()


def test_boolean_primary_tag_index_is_rejected(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [Python, Dev]\n---\n", encoding="utf-8")
    before = _paths(tmp_path)
    with pytest.raises(SortError, match="non-negative integer"):
        _sorter(tmp_path, primary_tag_index=True).run()
    assert _paths(tmp_path) == before
    assert not (tmp_path / "Dev").exists()


def test_invalid_toml_does_not_fall_back_to_defaults(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[general\nmode = "date"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to load config"):
        load_config(config_path)
    assert "Warning" not in capsys.readouterr().out

    source = tmp_path / "note.md"
    source.write_text("---\ntags: [Work]\n---\n", encoding="utf-8")
    result = CliRunner().invoke(cli, ["sort", str(tmp_path), "--config", str(config_path)])
    assert result.exit_code == 1
    assert "Failed to load config" in result.output
    assert "Traceback" not in result.output
    assert "完成" not in result.output
    assert source.is_file()
    assert not (tmp_path / "Work").exists()


def test_non_table_general_section_is_a_clean_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text('general = "tag"\n', encoding="utf-8")
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [Work]\n---\n", encoding="utf-8")
    result = CliRunner().invoke(
        cli, ["sort", str(tmp_path), "--config", str(config_path), "--dry-run"]
    )
    assert result.exit_code == 1
    assert "must be a table" in result.output
    assert "Traceback" not in result.output
    assert source.is_file()
    assert not (tmp_path / "Work").exists()


def test_bool_index_in_toml_is_rejected(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[general]\nprimary_tag_index = true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-negative integer"):
        load_config(config_path)


@pytest.mark.parametrize("folder", [" CON", "a\nb", "CON", "nul.txt", "COM1", "aux"])
def test_unsafe_tag_segments_abort_without_creating_them(tmp_path, folder):
    source = tmp_path / "note.md"
    if folder == "a\nb":
        source.write_text('---\ntags: ["a\\nb"]\n---\n', encoding="utf-8")
    else:
        source.write_text(f"---\ntags: ['{folder}']\n---\n", encoding="utf-8")
    before = _paths(tmp_path)
    with pytest.raises(SortError, match="Unsafe category"):
        _sorter(tmp_path).run()
    assert _paths(tmp_path) == before


@pytest.mark.parametrize("folder", ["console", "null", "COM10"])
def test_ordinary_tags_are_not_treated_as_device_names(tmp_path, folder):
    source = tmp_path / "note.md"
    source.write_text(f"---\ntags: ['{folder}']\n---\n", encoding="utf-8")
    assert _sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / folder / "note.md").is_file()


def test_rule_mode_rejects_invalid_front_matter_even_if_name_matches(tmp_path):
    source = tmp_path / "python-notes.md"
    source.write_text("---\ntags: [python\n---\n", encoding="utf-8")
    with pytest.raises(SortError, match="Invalid front matter"):
        _sorter(tmp_path, mode="rule", rules={"Lang/Python": ["python"]}).run()
    assert source.is_file()
    assert not (tmp_path / "Lang").exists()


def test_date_mode_sorts_without_reading_tags(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("---\ntags: [python\n---\n", encoding="utf-8")
    assert _sorter(tmp_path, mode="date").run() == (1, 0)
    assert not source.exists()
    assert list(tmp_path.rglob("*.md"))


def test_zero_birthtime_falls_back_to_mtime(tmp_path, monkeypatch):
    moment = 1_700_000_000
    assert _sort_timestamp(SimpleNamespace(st_birthtime=0, st_mtime=moment)) == moment
    assert (
        _sort_timestamp(SimpleNamespace(st_birthtime=moment - 10, st_mtime=moment)) == moment - 10
    )
    assert _sort_timestamp(SimpleNamespace(st_mtime=moment)) == moment

    source = tmp_path / "note.md"
    source.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        "pathlib.Path.stat",
        lambda *_args, **_kwargs: SimpleNamespace(st_birthtime=0, st_mtime=moment),
    )
    expected = datetime.fromtimestamp(moment).strftime("%Y/%m")
    assert get_file_date_folder(source, "%Y/%m") == expected
    assert not expected.startswith("1970")


def test_non_string_date_format_fails_before_moving(tmp_path):
    source = tmp_path / "note.md"
    source.write_text("x", encoding="utf-8")
    config = deepcopy(DEFAULT_CONFIG)
    config["date"]["format"] = 2024
    config["general"]["mode"] = "date"
    with pytest.raises(SortError, match="date.format"):
        MarkdownSorter(tmp_path, config).run()
    assert source.is_file()
    assert _paths(tmp_path) == {"note.md"}
