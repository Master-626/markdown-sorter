from pathlib import Path
import shutil
from typing import Dict, Any, Tuple, Optional
from markdown_sorter.utils import extract_frontmatter_tags, get_file_date_folder


class MarkdownSorter:
    def __init__(self, target_dir: Path, config: Dict[str, Any], dry_run: bool = False):
        self.target_dir = target_dir.resolve()
        self.config = config
        self.dry_run = dry_run

    def resolve_destination(self, file_path: Path) -> Path:
        """根据配置规则计算目标路径。"""
        mode = self.config["general"]["mode"]
        fallback = self.config["general"]["fallback_dir"]

        rel_subfolder: Optional[str] = None

        if mode == "tag":
            tags = extract_frontmatter_tags(file_path)
            idx = self.config["general"].get("primary_tag_index", 0)
            if tags and len(tags) > idx:
                rel_subfolder = tags[idx]

        elif mode == "date":
            fmt = self.config["date"].get("format", "%Y/%m")
            rel_subfolder = get_file_date_folder(file_path, fmt)

        elif mode == "rule":
            rules: Dict[str, list] = self.config.get("rules", {})
            content_lower = file_path.stem.lower()
            
            # 同时读取标签做规则匹配
            tags = [t.lower() for t in extract_frontmatter_tags(file_path)]
            
            for folder, keywords in rules.items():
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in content_lower or kw_lower in tags:
                        rel_subfolder = folder
                        break
                if rel_subfolder:
                    break

        if not rel_subfolder:
            rel_subfolder = fallback

        return self.target_dir / rel_subfolder / file_path.name

    def run(self) -> Tuple[int, int]:
        """执行整理流程，返回 (成功数量, 跳过数量)。"""
        md_files = list(self.target_dir.rglob("*.md"))
        moved_count = 0
        skipped_count = 0

        for file_path in md_files:
            dest_path = self.resolve_destination(file_path)

            # 避开已在目标位置的文件
            if file_path == dest_path:
                skipped_count += 1
                continue

            print(f"[{'DRY-RUN' if self.dry_run else 'MOVE'}] {file_path.relative_to(self.target_dir)} -> {dest_path.relative_to(self.target_dir)}")

            if not self.dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(dest_path))

            moved_count += 1

        return moved_count, skipped_count
