from pathlib import Path
from typing import Any, Dict
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG: Dict[str, Any] = {
    "general": {
        "mode": "tag",
        "primary_tag_index": 0,
        "fallback_dir": "Unsorted",
    },
    "date": {
        "format": "%Y/%m",
    },
    "rules": {},
}


def load_config(config_path: Path = None) -> Dict[str, Any]:
    """加载配置文件，若不存在则返回默认配置。"""
    if config_path is None or not config_path.exists():
        return DEFAULT_CONFIG

    try:
        with open(config_path, "rb") as f:
            user_config = tomllib.load(f)
            
        merged = DEFAULT_CONFIG.copy()
        for key, val in user_config.items():
            if isinstance(val, dict) and key in merged:
                merged[key].update(val)
            else:
                merged[key] = val
        return merged
    except Exception as e:
        print(f"Warning: Failed to load config file ({e}). Using defaults.")
        return DEFAULT_CONFIG
