"""All destructive-behavior regressions use disposable pytest directories."""

import errno
import os
from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner

from markdown_sorter.cli import cli
from markdown_sorter.config import DEFAULT_CONFIG, load_config
from markdown_sorter.core import MarkdownSorter, SortError


def note(root, name, body="note", tag="Work"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntags: ['{tag}']\n---\n{body}", encoding="utf-8")
    return path


def sorter(root, dry_run=False, mode="tag"):
    config = deepcopy(DEFAULT_CONFIG)
    config["general"]["mode"] = mode
    return MarkdownSorter(root, config, dry_run)


def snapshot(root):
    return {
        str(path.relative_to(root)): ("link", os.readlink(path))
        if path.is_symlink()
        else ("dir", None)
        if path.is_dir()
        else ("file", path.read_bytes())
        for path in root.rglob("*")
    }


def symlink(path, target, directory=False):
    try:
        path.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")


@pytest.mark.parametrize("dry_run", [False, True])
def test_duplicate_destinations_reject_entire_batch(tmp_path, dry_run):
    note(tmp_path, "a/first.md", tag="Other")
    note(tmp_path, "b/note.md", "first original")
    note(tmp_path, "c/note.md", "second original")
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="collision"):
        sorter(tmp_path, dry_run).run()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling-link", "hardlink"])
def test_existing_destination_is_never_replaced(tmp_path, kind):
    source = note(tmp_path, "note.md", "original")
    destination = tmp_path / "Work" / "note.md"
    destination.parent.mkdir()
    if kind == "file":
        destination.write_text("existing content")
    elif kind == "directory":
        destination.mkdir()
    elif kind == "symlink":
        symlink(destination, source)
    elif kind == "dangling-link":
        symlink(destination, tmp_path / "missing")
    else:
        os.link(source, destination)
    before = snapshot(tmp_path)
    with pytest.raises(SortError):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_success_preserves_bytes_mtime_and_permissions(tmp_path):
    source = note(tmp_path, "in/note.md", "Unicode 中文\n\nline\r\nend")
    os.chmod(source, 0o640)
    before, info = source.read_bytes(), source.stat()
    assert sorter(tmp_path).run() == (1, 0)
    destination = tmp_path / "Work/note.md"
    assert not source.exists()
    assert destination.read_bytes() == before
    assert destination.stat().st_mtime_ns == info.st_mtime_ns
    assert destination.stat().st_mode == info.st_mode
    assert sorter(tmp_path).run() == (0, 1)


def test_dry_run_uses_same_plan_but_creates_nothing(tmp_path, capsys):
    note(tmp_path, "nested/a.md")
    before = snapshot(tmp_path)
    assert sorter(tmp_path, True).run() == (1, 0)
    assert snapshot(tmp_path) == before
    expected = f"[DRY-RUN] {Path('nested/a.md')} -> {Path('Work/a.md')}"
    assert expected in capsys.readouterr().out


@pytest.mark.parametrize("mode", ["tag", "date", "rule"])
def test_modes_move_and_rerun_safely(tmp_path, mode):
    note(tmp_path, "a.md")
    instance = sorter(tmp_path, mode=mode)
    if mode == "rule":
        instance.config["rules"] = {"Projects/Work": ["work"]}
    assert instance.run() == (1, 0)
    assert instance.run() == (0, 1)
    assert len(list(tmp_path.rglob("*.md"))) == 1


@pytest.mark.parametrize(
    "folder",
    [
        "../escape",
        "a/../../escape",
        "/absolute",
        "./Work",
        "Work/../Work",
        "Work//Sub",
        "C:/escape",
        r"C:\escape",
        r"a\b",
        "Work.",
        "Work ",
        "bad:name",
        "a/",
        ".",
        "..",
    ],
)
def test_unsafe_category_aborts_without_mutation(tmp_path, folder):
    note(tmp_path, "note.md", tag=folder)
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="Unsafe category"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("mode", ["tag", "date", "rule"])
def test_unsafe_config_paths_rejected(tmp_path, mode):
    source = tmp_path / "note.md"
    source.write_text("untagged")
    instance = sorter(tmp_path, mode=mode)
    if mode == "tag":
        instance.config["general"]["fallback_dir"] = "../escape"
    elif mode == "date":
        instance.config["date"]["format"] = "../escape/%Y"
    else:
        instance.config["rules"] = {"../escape": ["note"]}
    with pytest.raises(SortError, match="Unsafe category"):
        instance.run()
    assert source.read_text() == "untagged"


def test_source_symlink_is_refused(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("original")
    symlink(tmp_path / "note.md", target)
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="regular file"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_destination_directory_symlink_is_refused(tmp_path):
    note(tmp_path, "note.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink(tmp_path / "Work", outside, directory=True)
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="directory"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_directory_symlinks_are_not_traversed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    note(outside, "note.md")
    root = tmp_path / "notes"
    root.mkdir()
    symlink(root / "linked", outside, directory=True)
    assert sorter(root).run() == (0, 0)
    assert (outside / "note.md").is_file()


def test_hardlinked_sources_are_refused(tmp_path):
    source = note(tmp_path, "a.md")
    os.link(source, tmp_path / "b.md")
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="Hard-linked"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("first,second", [("Work", "work"), ("Café", "Cafe\u0301")])
def test_planned_directory_aliases_are_refused(tmp_path, first, second):
    note(tmp_path, "a.md", tag=first)
    note(tmp_path, "b.md", tag=second)
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="alias"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_existing_case_alias_is_refused(tmp_path):
    note(tmp_path, "note.md")
    (tmp_path / "work").mkdir()
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="conflicts|Aliased"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_file_and_planned_directory_conflict(tmp_path):
    note(tmp_path, "note.md", tag="A")
    note(tmp_path, "other.md", tag="A/note.md")
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="planned directory"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_existing_file_as_directory_is_refused(tmp_path):
    note(tmp_path, "note.md", tag="Work/sub")
    (tmp_path / "Work").write_text("not a directory")
    before = snapshot(tmp_path)
    with pytest.raises(SortError, match="directory"):
        sorter(tmp_path).run()
    assert snapshot(tmp_path) == before


def test_destination_created_after_preflight_is_not_overwritten(tmp_path, monkeypatch):
    source = note(tmp_path, "note.md")
    original = source.read_bytes()
    real_link = os.link

    def competing_link(src, dst, **kwargs):
        Path(dst).write_text("newly created")
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(os, "link", competing_link)
    with pytest.raises(SortError, match="Stopped after 0"):
        sorter(tmp_path).run()
    assert source.read_bytes() == original
    assert (tmp_path / "Work/note.md").read_text() == "newly created"


@pytest.mark.parametrize(
    "error",
    [
        OSError(errno.EXDEV, "Cross-device link"),
        PermissionError("denied"),
        OSError(errno.ENOSPC, "Disk full"),
    ],
)
def test_link_failure_retains_original(tmp_path, monkeypatch, error):
    source = note(tmp_path, "note.md")
    before = source.read_bytes()

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(os, "link", fail)
    with pytest.raises(SortError, match="Stopped after 0"):
        sorter(tmp_path).run()
    assert source.read_bytes() == before
    assert not (tmp_path / "Work/note.md").exists()


def test_source_change_after_planning_is_refused(tmp_path, monkeypatch):
    source = note(tmp_path, "note.md")
    instance = sorter(tmp_path)
    real_plan = instance.plan

    def changed_plan():
        result = real_plan()
        source.write_text("edited during planning")
        return result

    monkeypatch.setattr(instance, "plan", changed_plan)
    with pytest.raises(SortError, match="Source changed"):
        instance.run()
    assert source.read_text() == "edited during planning"
    assert not (tmp_path / "Work").exists()


@pytest.mark.parametrize("error", [KeyboardInterrupt(), PermissionError("unlink denied")])
def test_interrupt_before_source_unlink_preserves_both(tmp_path, monkeypatch, error):
    source = note(tmp_path, "note.md")
    before = source.read_bytes()
    real_unlink = Path.unlink

    def fail_unlink(path, *args, **kwargs):
        if path == source:
            raise error
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else SortError):
        sorter(tmp_path).run()
    assert source.read_bytes() == before
    assert (tmp_path / "Work/note.md").read_bytes() == before
    with pytest.raises(SortError):
        sorter(tmp_path).run()
    assert source.read_bytes() == before


def test_interrupt_after_link_creation_preserves_both(tmp_path, monkeypatch):
    source = note(tmp_path, "note.md")
    before = source.read_bytes()
    real_link = os.link

    def interrupt_after_link(*args, **kwargs):
        real_link(*args, **kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "link", interrupt_after_link)
    with pytest.raises(KeyboardInterrupt):
        sorter(tmp_path).run()
    assert source.read_bytes() == before
    assert (tmp_path / "Work/note.md").read_bytes() == before


def test_mid_batch_failure_does_not_undo_completed_moves(tmp_path, monkeypatch):
    first = note(tmp_path, "a.md", "first")
    second = note(tmp_path, "b.md", "second")
    first_bytes, second_bytes = first.read_bytes(), second.read_bytes()
    real_link = os.link

    def fail_second(src, dst, **kwargs):
        if src == second:
            raise OSError("simulated failure")
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(os, "link", fail_second)
    with pytest.raises(SortError, match="Stopped after 1"):
        sorter(tmp_path).run()
    assert not first.exists()
    assert (tmp_path / "Work/a.md").read_bytes() == first_bytes
    assert second.read_bytes() == second_bytes
    assert not (tmp_path / "Work/b.md").exists()


def test_source_replaced_during_link_is_not_deleted(tmp_path, monkeypatch):
    source = note(tmp_path, "note.md")
    before = source.read_bytes()
    real_link = os.link

    def replace_source(src, dst, **kwargs):
        real_link(src, dst, **kwargs)
        src.unlink()
        src.write_text("new source")

    monkeypatch.setattr(os, "link", replace_source)
    with pytest.raises(SortError, match="both paths retained"):
        sorter(tmp_path).run()
    assert source.read_text() == "new source"
    assert (tmp_path / "Work/note.md").read_bytes() == before


def test_cli_collision_is_nonzero_with_no_success_message(tmp_path):
    note(tmp_path, "a/note.md")
    note(tmp_path, "b/note.md")
    before = snapshot(tmp_path)
    result = CliRunner().invoke(cli, ["sort", str(tmp_path)])
    assert result.exit_code == 1
    assert "collision" in result.output
    assert "完成" not in result.output
    assert snapshot(tmp_path) == before


def test_config_defaults_are_isolated(tmp_path):
    original = deepcopy(DEFAULT_CONFIG)
    config = load_config()
    config["general"]["mode"] = "date"
    assert DEFAULT_CONFIG == original
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[general]\nmode = "rule"\n')
    assert load_config(cfg_path)["general"]["mode"] == "rule"
    assert load_config()["general"]["mode"] == "tag"
    assert DEFAULT_CONFIG == original


def test_repeated_cli_invocations_do_not_leak_mode(tmp_path):
    runner = CliRunner()
    first = runner.invoke(cli, ["sort", str(tmp_path), "--mode", "date"])
    second = runner.invoke(cli, ["sort", str(tmp_path)])
    assert first.exit_code == second.exit_code == 0
    assert "模式: tag" in second.output


def test_root_symlink_is_refused(tmp_path):
    root = tmp_path / "real"
    root.mkdir()
    source = note(root, "note.md")
    alias = tmp_path / "alias"
    symlink(alias, root, directory=True)
    with pytest.raises(SortError, match="Target directory"):
        sorter(alias).run()
    assert source.is_file()
    assert not (root / "Work").exists()


def test_uppercase_markdown_extension_is_sorted(tmp_path):
    source = note(tmp_path, "note.MD")
    before = source.read_bytes()
    assert sorter(tmp_path).run() == (1, 0)
    assert (tmp_path / "Work/note.MD").read_bytes() == before


def test_empty_directory_is_noop(tmp_path):
    assert sorter(tmp_path).run() == (0, 0)
    assert list(tmp_path.iterdir()) == []


def test_unrelated_directory_named_md_is_not_moved(tmp_path):
    (tmp_path / "directory.md").mkdir()
    assert sorter(tmp_path).run() == (0, 0)
    assert (tmp_path / "directory.md").is_dir()


def test_windows_reparse_points_detected_on_older_python(tmp_path, monkeypatch):
    import stat
    from types import SimpleNamespace

    from markdown_sorter.core import _is_link

    monkeypatch.setattr(
        Path, "lstat", lambda path: SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
    )
    assert _is_link(tmp_path)


def test_unsupported_link_operation_retains_original(tmp_path, monkeypatch):
    source = note(tmp_path, "note.md")
    before = source.read_bytes()

    def unsupported(*args, **kwargs):
        raise NotImplementedError("no hard links")

    monkeypatch.setattr(os, "link", unsupported)
    with pytest.raises(SortError, match="no hard links"):
        sorter(tmp_path).run()
    assert source.read_bytes() == before


def test_abrupt_process_exit_after_link_keeps_both_paths(tmp_path):
    import subprocess
    import sys

    source = note(tmp_path, "note.md")
    before = source.read_bytes()
    child = r"""
import os
import sys
from pathlib import Path
from markdown_sorter.config import load_config
from markdown_sorter.core import MarkdownSorter
real_link = os.link

def exit_after_link(*args, **kwargs):
    real_link(*args, **kwargs)
    os._exit(23)

os.link = exit_after_link
MarkdownSorter(Path(sys.argv[1]), load_config()).run()
"""
    result = subprocess.run([sys.executable, "-c", child, str(tmp_path)], capture_output=True)
    assert result.returncode == 23, result.stderr
    assert source.read_bytes() == before
    assert (tmp_path / "Work/note.md").read_bytes() == before
    with pytest.raises(SortError):
        sorter(tmp_path).run()
