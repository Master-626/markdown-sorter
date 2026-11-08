from datetime import datetime
from pathlib import Path
from typing import List

import frontmatter


def extract_frontmatter_tags(file_path: Path) -> List[str]:
    """解析 Markdown 文件的 Front Matter 并提取 tags。"""
    try:
        post = frontmatter.load(file_path)
        tags = post.get("tags", [])
        if isinstance(tags, str):
            return [tags]
        elif isinstance(tags, list):
            return [str(t) for t in tags]
    except Exception:
        pass
    return []


def get_file_date_folder(file_path: Path, date_format: str = "%Y/%m") -> str:
    """获取文件的创建/修改日期格式化路径。"""
    stat = file_path.stat()
    # 优先选择创建时间 (st_birthtime，Linux 下退化为 st_mtime)
    timestamp = getattr(stat, "st_birthtime", stat.st_mtime)
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime(date_format)
