import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from markdown_sorter.utils import validate_exclude_pattern

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG: Dict[str, Any] = {
    "general": {
        "mode": "tag",
        "primary_tag_index": 0,
        "fallback_dir": "Unsorted",
        "exclude": [],
    },
    "date": {
        "format": "%Y/%m",
    },
    "rules": {},
}


def validate_config(config: Dict[str, Any]) -> None:
    """Raise ValueError when a config table cannot be applied safely."""
    if not isinstance(config, dict):
        raise ValueError("Config must be a table")

    general = config.get("general", {})
    if not isinstance(general, dict):
        raise ValueError("Config section 'general' must be a table")
    mode = general.get("mode", "tag")
    if mode not in {"tag", "date", "rule"}:
        raise ValueError("general.mode must be 'tag', 'date', or 'rule'")
    index = general.get("primary_tag_index", 0)
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError("primary_tag_index must be a non-negative integer")
    if not isinstance(general.get("fallback_dir", "Unsorted"), str):
        raise ValueError("general.fallback_dir must be a string")
    exclude = general.get("exclude", [])
    if not isinstance(exclude, list):
        raise ValueError("general.exclude must be a list of glob patterns")
    for pattern in exclude:
        validate_exclude_pattern(pattern)

    date_cfg = config.get("date", {})
    if not isinstance(date_cfg, dict):
        raise ValueError("Config section 'date' must be a table")
    date_format = date_cfg.get("format", "%Y/%m")
    if not isinstance(date_format, str) or not date_format:
        raise ValueError("date.format must be a non-empty string")

    rules = config.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("Config section 'rules' must be a table")
    for folder, keywords in rules.items():
        if (
            not isinstance(folder, str)
            or isinstance(keywords, str)
            or not isinstance(keywords, list)
            or any(not isinstance(keyword, str) or not keyword.strip() for keyword in keywords)
        ):
            raise ValueError(f"Rule {folder!r} must map to a list of non-empty strings")


def load_config(config_path: Path = None) -> Dict[str, Any]:
    """加载配置文件。路径不存在时返回默认配置；文件无法解析时抛出 ValueError。"""
    if config_path is None or not config_path.exists():
        config = deepcopy(DEFAULT_CONFIG)
        validate_config(config)
        return config

    with open(config_path, "rb") as handle:
        try:
            user_config = tomllib.load(handle)
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"Failed to load config file {config_path}: {error}") from error

    if not isinstance(user_config, dict):
        raise ValueError(f"Config root must be a table: {config_path}")

    merged = deepcopy(DEFAULT_CONFIG)
    for key, val in user_config.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key].update(val)
        else:
            merged[key] = val
    validate_config(merged)
    return merged
