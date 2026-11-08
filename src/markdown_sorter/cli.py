import sys
from pathlib import Path

import click

from markdown_sorter import __version__
from markdown_sorter.config import load_config
from markdown_sorter.core import MarkdownSorter


@click.group()
@click.version_option(version=__version__)
def cli():
    """Markdown Sorter - 智能 Markdown 文件整理工具"""
    pass


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="配置文件路径 (TOML)",
)
@click.option(
    "--mode", "-m", type=click.Choice(["tag", "date", "rule"]), help="分类模式 (会覆盖配置文件设置)"
)
@click.option("--dry-run", is_flag=True, help="仅预览整理结果，不实际移动文件")
def sort(directory: Path, config: Path, mode: str, dry_run: bool):
    """整理指定目录下的所有 Markdown 文件"""
    cfg = load_config(config)

    if mode:
        cfg["general"]["mode"] = mode

    click.echo(f"📁 目标目录: {directory.resolve()}")
    click.echo(f"⚙️ 模式: {cfg['general']['mode']}")
    if dry_run:
        click.echo("🔍 模式: [Dry-run] 仅预览，不修改文件\n")

    try:
        sorter = MarkdownSorter(target_dir=directory, config=cfg, dry_run=dry_run)
        moved, skipped = sorter.run()
    except (OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"\n✨ 完成！整理了 {moved} 个文件，跳过了 {skipped} 个文件。")


def main():
    """Use UTF-8 for CLI output, including redirected Windows streams."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")
    cli()


if __name__ == "__main__":
    main()
