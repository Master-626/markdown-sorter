"""Plan first, then move notes without replacing an existing directory entry."""

import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

from markdown_sorter.utils import extract_frontmatter_tags, get_file_date_folder


class SortError(ValueError):
    """A plan or move could not be completed safely."""


def _path_key(path: Path) -> str:
    # Be conservative across case-insensitive and Unicode-normalizing filesystems.
    return unicodedata.normalize("NFC", path.as_posix()).casefold()


def _signature(path: Path) -> Tuple[int, int, int, int]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise SortError(f"Not a regular file (symlinks are not moved): {path}")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _is_link(path: Path) -> bool:
    """Include Windows junctions/reparse points, even on Python before 3.12."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


@dataclass(frozen=True)
class Move:
    source: Path
    destination: Path
    signature: Tuple[int, int, int, int]


class MarkdownSorter:
    def __init__(self, target_dir: Path, config: Dict[str, Any], dry_run: bool = False):
        if _is_link(target_dir):
            raise SortError(f"Target directory must not be a symlink or junction: {target_dir}")
        self.target_dir = target_dir.resolve(strict=True)
        if not self.target_dir.is_dir():
            raise SortError(f"Not a directory: {self.target_dir}")
        self.config = config
        self.dry_run = dry_run

    def _check_parents(self, path: Path) -> None:
        """Reject links/junctions and non-directory components, including the root."""
        relative = path.relative_to(self.target_dir)
        parent = self.target_dir
        for part in (None, *relative.parts[:-1]):
            if part is not None:
                parent /= part
            if os.path.lexists(parent):
                if _is_link(parent) or not parent.is_dir():
                    raise SortError(f"Unsafe destination/source directory: {parent}")
                if parent.resolve().as_posix() != parent.as_posix():
                    raise SortError(f"Aliased destination/source directory: {parent}")

    def resolve_destination(self, file_path: Path) -> Path:
        """根据配置规则计算目标路径，只允许根目录内的普通相对路径。"""
        mode = self.config["general"]["mode"]
        fallback = self.config["general"]["fallback_dir"]
        rel_subfolder: Optional[str] = None

        if mode == "tag":
            tags = extract_frontmatter_tags(file_path)
            idx = self.config["general"].get("primary_tag_index", 0)
            if not isinstance(idx, int) or idx < 0:
                raise SortError("primary_tag_index must be a non-negative integer")
            if tags and len(tags) > idx:
                rel_subfolder = tags[idx]
        elif mode == "date":
            fmt = self.config["date"].get("format", "%Y/%m")
            rel_subfolder = get_file_date_folder(file_path, fmt)
        elif mode == "rule":
            rules: Dict[str, list] = self.config.get("rules", {})
            content_lower = file_path.stem.lower()
            tags = [t.lower() for t in extract_frontmatter_tags(file_path)]
            for folder, keywords in rules.items():
                if any(kw.lower() in content_lower or kw.lower() in tags for kw in keywords):
                    rel_subfolder = folder
                    break
        else:
            raise SortError(f"Unknown sort mode: {mode}")

        if not rel_subfolder:
            rel_subfolder = fallback
        if (
            not isinstance(rel_subfolder, str)
            or not rel_subfolder
            or Path(rel_subfolder).is_absolute()
            or PureWindowsPath(rel_subfolder).drive
            or "\\" in rel_subfolder
            or any(part in ("", ".", "..") for part in rel_subfolder.split("/"))
            or any(char in rel_subfolder for char in '<>:"|?*\0')
            or any(part.endswith((" ", ".")) for part in rel_subfolder.split("/"))
        ):
            raise SortError(f"Unsafe category path: {rel_subfolder!r}")

        destination = self.target_dir / rel_subfolder / file_path.name
        self._check_parents(destination)
        return destination

    def plan(self) -> Tuple[List[Move], int]:
        """Check the entire batch before creating directories or moving any files."""
        files: List[Path] = []
        occupied: Dict[str, Path] = {}

        def walk_error(error: OSError) -> None:
            raise error

        for root, directories, filenames in os.walk(
            self.target_dir, followlinks=False, onerror=walk_error
        ):
            for name in directories + filenames:
                path = Path(root) / name
                key = _path_key(path)
                if key in occupied and occupied[key].as_posix() != path.as_posix():
                    raise SortError(f"Case/Unicode path alias: {occupied[key]} and {path}")
                occupied[key] = path
            # os.walk does not follow symlinks; also exclude Windows junctions.
            directories[:] = sorted(name for name in directories if not _is_link(Path(root) / name))
            files.extend(
                Path(root) / name for name in sorted(filenames) if name.lower().endswith(".md")
            )

        moves: List[Move] = []
        planned: Dict[str, Path] = {}
        source_ids: Dict[Tuple[int, int], Path] = {}
        skipped = 0
        for source in sorted(files):
            self._check_parents(source)
            signature = _signature(source)
            if signature[:2] in source_ids:
                raise SortError(
                    f"Hard-linked source aliases: {source_ids[signature[:2]]} and {source}"
                )
            source_ids[signature[:2]] = source
            destination = self.resolve_destination(source)
            if _signature(source) != signature:
                raise SortError(f"Source changed while planning: {source}")
            if source.as_posix() == destination.as_posix():
                skipped += 1
                continue
            key = _path_key(destination)
            if key in occupied or os.path.lexists(destination):
                raise SortError(f"Destination already exists: {destination}")
            if key in planned:
                raise SortError(
                    f"Destination collision: {planned[key]} and {source} -> {destination}"
                )
            # Check directory aliases and file-versus-directory conflicts too.
            for parent in destination.parents:
                if parent == self.target_dir:
                    break
                existing = occupied.get(_path_key(parent))
                if existing is not None and (
                    existing.as_posix() != parent.as_posix() or not existing.is_dir()
                ):
                    raise SortError(f"Destination directory conflicts with {existing}")
            planned[key] = source
            moves.append(Move(source, destination, signature))

        planned_directories: Dict[str, Path] = {}
        for move in moves:
            for parent in move.destination.parents:
                if parent == self.target_dir:
                    break
                key = _path_key(parent)
                if key in planned:
                    raise SortError(f"Destination is also a planned directory: {parent}")
                if key in planned_directories and (
                    planned_directories[key].as_posix() != parent.as_posix()
                ):
                    raise SortError(f"Planned directory alias: {parent}")
                planned_directories[key] = parent
        return moves, skipped

    def _move(self, move: Move) -> None:
        """Link exclusively, verify, then unlink: interruptions can leave duplicates."""
        self._check_parents(move.source)
        self._check_parents(move.destination)
        if _signature(move.source) != move.signature:
            raise SortError(f"Source changed since planning: {move.source}")
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        self._check_parents(move.destination)
        # Unlike rename/shutil.move, link never overwrites an occupied name.
        # No copy/delete fallback: cross-device and unsupported links fail safely.
        os.link(move.source, move.destination, follow_symlinks=False)
        # Do not roll back on failure: either path may have changed externally.
        self._check_parents(move.source)
        self._check_parents(move.destination)
        if (
            _signature(move.source) != move.signature
            or _signature(move.destination) != move.signature
        ):
            raise SortError(f"File changed during move; both paths retained: {move.source}")
        move.source.unlink()

    def run(self) -> Tuple[int, int]:
        """执行整理流程，返回 (成功数量, 跳过数量)。失败时停止，不覆盖文件。"""
        moves, skipped = self.plan()
        moved = 0
        for move in moves:
            source = move.source.relative_to(self.target_dir)
            destination = move.destination.relative_to(self.target_dir)
            if not self.dry_run:
                try:
                    self._move(move)
                except (OSError, SortError, NotImplementedError) as error:
                    raise SortError(
                        f"Stopped after {moved} completed moves at {source} -> {destination}: "
                        f"{error}. Inspect both paths before retrying; no rollback was attempted."
                    ) from error
            print(f"[{'DRY-RUN' if self.dry_run else 'MOVE'}] {source} -> {destination}")
            moved += 1
        return moved, skipped
