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
