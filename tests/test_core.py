from copy import deepcopy
from pathlib import Path

from markdown_sorter.config import DEFAULT_CONFIG
from markdown_sorter.core import MarkdownSorter


def test_tag_sorting(tmp_path: Path):
    # 创建带 Front Matter 的 MD 测试文件
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ntags: [Python, Dev]\n---\n# Header\nHello Markdown")

    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = "tag"

    sorter = MarkdownSorter(target_dir=tmp_path, config=config, dry_run=True)
    dest = sorter.resolve_destination(test_file)

    assert dest == tmp_path / "Python" / "test.md"


def test_date_sorting(tmp_path: Path):
    test_file = tmp_path / "date_test.md"
    test_file.write_text("# Note")

    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = "date"
    config["date"]["format"] = "%Y-%m"

    sorter = MarkdownSorter(target_dir=tmp_path, config=config, dry_run=True)
    dest = sorter.resolve_destination(test_file)

    assert dest.parent.name.count("-") == 1  # 验证 YYYY-MM 格式


def test_missing_tags_use_fallback(tmp_path: Path):
    test_file = tmp_path / "plain.md"
    test_file.write_text("# Just a title\n", encoding="utf-8")
    sorter = MarkdownSorter(tmp_path, deepcopy(DEFAULT_CONFIG), dry_run=True)
    assert sorter.resolve_destination(test_file) == tmp_path / "Unsorted" / "plain.md"


def test_primary_tag_index_selects_later_tag(tmp_path: Path):
    test_file = tmp_path / "test.md"
    test_file.write_text("---\ntags: [Python, Dev]\n---\n", encoding="utf-8")
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["primary_tag_index"] = 1
    sorter = MarkdownSorter(tmp_path, config, dry_run=True)
    assert sorter.resolve_destination(test_file) == tmp_path / "Dev" / "test.md"


def test_rule_matches_filename_and_first_rule_wins(tmp_path: Path):
    test_file = tmp_path / "my-python-notes.md"
    test_file.write_text("# notes\n", encoding="utf-8")
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = "rule"
    config["rules"] = {
        "Projects/Python": ["python"],
        "Projects/Other": ["python", "notes"],
    }
    sorter = MarkdownSorter(tmp_path, config, dry_run=True)
    destination = sorter.resolve_destination(test_file)
    assert destination == tmp_path / "Projects" / "Python" / "my-python-notes.md"


def test_unmatched_rule_uses_fallback(tmp_path: Path):
    test_file = tmp_path / "grocery.md"
    test_file.write_text("# milk\n", encoding="utf-8")
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = "rule"
    config["rules"] = {"Projects/Python": ["python"]}
    sorter = MarkdownSorter(tmp_path, config, dry_run=True)
    assert sorter.resolve_destination(test_file) == tmp_path / "Unsorted" / "grocery.md"


def test_rule_matches_non_ascii_keyword(tmp_path: Path):
    test_file = tmp_path / "a.md"
    test_file.write_text("---\ntags: [周会]\n---\n", encoding="utf-8")
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = "rule"
    config["rules"] = {"Work/Meeting": ["周会"]}
    sorter = MarkdownSorter(tmp_path, config, dry_run=True)
    assert sorter.resolve_destination(test_file) == tmp_path / "Work" / "Meeting" / "a.md"
