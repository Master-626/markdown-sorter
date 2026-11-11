import re
import unicodedata
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, List, Sequence

import yaml
from frontmatter.default_handlers import YAMLHandler

try:
    from yaml import CSafeLoader as _YamlSafeLoader
except ImportError:  # pragma: no cover - pure-Python fallback
    from yaml import SafeLoader as _YamlSafeLoader


class _LiteralScalarLoader(_YamlSafeLoader):
    """Load YAML scalars as written instead of YAML 1.1's implicit types."""


def _construct_literal_scalar(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            f"expected a scalar node, but found {node.id}",
            node.start_mark,
        )
    return loader.construct_scalar(node)


for _yaml_tag in (
    "tag:yaml.org,2002:bool",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:float",
    "tag:yaml.org,2002:timestamp",
):
    _LiteralScalarLoader.add_constructor(_yaml_tag, _construct_literal_scalar)


def _sort_timestamp(stat_result: Any) -> float:
    """Use birth time when it is a real timestamp, otherwise mtime.

    Some platforms report ``st_birthtime`` as 0 when creation time is unknown.
    Filing those notes under 1970 would be wrong; modification time is the
    documented fallback.
    """
    birth = getattr(stat_result, "st_birthtime", None)
    if isinstance(birth, (int, float)) and not isinstance(birth, bool) and birth > 0:
        return float(birth)
    return float(stat_result.st_mtime)


def extract_frontmatter_tags(file_path: Path) -> List[str]:
    """解析 Markdown Front Matter 里的 tags。

    Scalars stay as written, so ``yes`` does not become ``True`` and ``01``
    does not become ``1``. A missing or null ``tags`` value means there are no
    tags. Invalid YAML, text that is not UTF-8, and tag entries that are not
    strings raise ``ValueError`` instead of looking like an untagged note.
    """
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"Cannot read {file_path} as UTF-8: {error}") from error

    handler = YAMLHandler()
    stripped = text.strip()
    if not handler.detect(stripped):
        return []
    try:
        front_matter, _content = handler.split(stripped)
    except ValueError:
        # A leading thematic break is not front matter.
        return []
    try:
        data = yaml.load(front_matter, Loader=_LiteralScalarLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid front matter in {file_path}: {error}") from error
    if data is None:
        return []
    if not isinstance(data, dict):
        raise ValueError(f"Front matter in {file_path} must be a mapping")
    if "tags" not in data:
        return []
    return _tag_strings(data["tags"], file_path)


def _tag_strings(tags: Any, file_path: Path) -> List[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        return [tags]
    if isinstance(tags, list):
        values: List[str] = []
        for item in tags:
            if item is None:
                raise ValueError(f"Front matter tags in {file_path} must be strings, not null")
            if not isinstance(item, str):
                raise ValueError(
                    f"Front matter tags in {file_path} must be strings, not {type(item).__name__}"
                )
            values.append(item)
        return values
    raise ValueError(
        f"Front matter tags in {file_path} must be a string or list, not {type(tags).__name__}"
    )


def tag_has_keyword(keyword: str, tag: str) -> bool:
    """Return True if ``keyword`` is the whole tag or one letter/number segment.

    Segments are split on hyphens, underscores, and other non-word characters,
    so ``python`` matches ``python-dev`` and ``work`` does not match ``network``.
    """
    keyword = keyword.lower()
    tag = tag.lower()
    if keyword == tag:
        return True
    segments = [segment for segment in re.split(r"[\W_]+", tag) if segment]
    return keyword in segments


def get_file_date_folder(file_path: Path, date_format: str = "%Y/%m") -> str:
    """获取文件的创建/修改日期格式化路径。"""
    timestamp = _sort_timestamp(file_path.stat())
    return datetime.fromtimestamp(timestamp).strftime(date_format)


def validate_exclude_pattern(pattern: str) -> None:
    """Reject exclude globs that escape the notes root or are not relative."""
    if (
        not isinstance(pattern, str)
        or not pattern
        or pattern != pattern.strip()
        or "\\" in pattern
        or pattern.startswith("/")
        or PureWindowsPath(pattern).drive
        or any(part in ("", ".", "..") for part in pattern.split("/"))
        or any(char in pattern for char in '<>:"|\0')
        or any(unicodedata.category(char) in {"Cc", "Zl", "Zp"} for char in pattern)
    ):
        raise ValueError(f"Unsafe exclude pattern: {pattern!r}")


def is_excluded(relative_posix: str, patterns: Sequence[str]) -> bool:
    """Return whether a note's path relative to the root matches an exclude glob.

    ``*`` and ``?`` stay inside one path segment. ``**`` spans segments. A
    pattern with no ``/`` matches the file name in any directory. Matching is
    case-insensitive, consistent with the sorter's alias checks.
    """
    return any(_glob_match(relative_posix, pattern) for pattern in patterns)


def _glob_match(relative_posix: str, pattern: str) -> bool:
    relative = relative_posix.casefold()
    folded = pattern.casefold()
    if "/" not in folded:
        relative = relative.rsplit("/", 1)[-1]
    return _parts_match(relative.split("/"), folded.split("/"))


def _parts_match(path: List[str], pattern: List[str]) -> bool:
    if not pattern:
        return not path
    if pattern[0] == "**":
        if _parts_match(path, pattern[1:]):
            return True
        return bool(path) and _parts_match(path[1:], pattern)
    if not path or not _segment_match(path[0], pattern[0]):
        return False
    return _parts_match(path[1:], pattern[1:])


def _segment_match(text: str, pattern: str) -> bool:
    pieces = []
    for char in pattern:
        if char == "*":
            pieces.append("[^/]*")
        elif char == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(char))
    return re.fullmatch("".join(pieces), text) is not None
