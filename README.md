# Markdown Sorter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

**Markdown Sorter** 是一个智能且高效的 CLI 命令行工具，帮助你自动按 **标签 (YAML Front Matter)**、**文件日期** 或 **自定义规则** 整理乱糟糟的 Markdown 笔记文件夹。

---

## ✨ 功能特性

- 🏷️ **按标签分类**：解析笔记开头的 Front Matter（如 `tags: [python, cli]`），自动整理到对应文件夹。
- 📅 **按日期归档**：提取文件创建/修改时间，按 `YYYY/MM` 等层级整理。
- 🎯 **自定义规则分类**：根据文件标题或 Front Matter 关键词规则过滤分类。
- 🛡️ **安全预览 (Dry-Run)**：支持预览移动操作，防止误操作。
- ⚡ **保留原文**：移动文件，不修改 Markdown 原文内容。

---

## 📦 安装方法

你可以使用 `pip` 本地安装：

```bash
git clone https://github.com/Master-626/markdown-sorter.git
cd markdown-sorter
pip install .
```

支持 Python 3.9 及以上版本。Python 3.9 会安装 `python-frontmatter<1.2`，避免 1.2.0 导入 `typing.TypeGuard` 时出错；Python 3.10 及以上版本使用正常的依赖范围。安装后的快速检查：

```bash
python -m pip check
markdown-sorter --version
markdown-sorter sort --help
```

## 🚀 快速上手

### 1. 基础用法

直接整理指定的 Markdown 目录：

```bash
# 默认使用 YAML 标签分类
markdown-sorter sort /path/to/notes
```

### 2. 预览操作 (Dry Run)

在不真实移动文件的情况下预览整理结果：

```bash
markdown-sorter sort /path/to/notes --dry-run
```

### 3. 按不同模式整理

```bash
# 按日期归档 (如: 2026/03/note.md)
markdown-sorter sort /path/to/notes --mode date

# 使用配置文件整理
markdown-sorter sort /path/to/notes --config config.example.toml
```

---

## ⚙️ 配置文件说明

在本地创建 `config.toml` 文件：

```toml
[general]
mode = "tag"
fallback_dir = "Unsorted"

[date]
format = "%Y/%m"

[rules]
"Projects/Python" = ["python", "pip"]
"Work/Meeting" = ["meeting", "minutes"]
```

分类目录必须是整理根目录内的相对路径，如 `Projects/Python`。不允许绝对路径、`..`、`.`、反斜杠、空路径段或末尾空格/点。此限制同样适用于标签、备用目录、规则目录和日期格式的结果。

## 🛡️ 冲突与中断处理

- 先检查整个批次，再开始移动。两个笔记指向同一目标、目标已存在，或文件与目录路径冲突时，命令报错退出，本次预检不会移动任何文件。
- 不覆盖、不自动改名。请先调整冲突文件名或分类，再运行 `--dry-run`。即使现有目标也会在本批次移动，仍会报错，不进行交换或链式覆盖。
- 为避免跨平台差异，大小写或 Unicode 规范化后相同的文件/目录名按冲突处理。已位于目标路径的普通文件会跳过；`.md` 和 `.MD` 都会扫描。
- 不整理符号链接文件、不递归进入链接目录，不接受链接或 Windows junction 作为目标目录。源笔记之间有硬链接别名时也会停止。
- 单文件移动先用硬链接创建一个**不能覆盖现有名称**的目标，再检查源文件身份并删除原路径。预检后若有人创建了同名目标，移动仍会安全失败。
- 因此源与目标必须位于同一文件系统，且文件系统必须支持硬链接。跨盘、FAT/exFAT 或其他不支持的存储会报错并保留源文件，不回退到可能覆盖的复制/删除操作。预览不能证明写入权限或硬链接支持。

**中断后恢复：** Ctrl+C、权限错误等可能留下已经完成的移动，也可能让当前文件同时出现在源和目标两处。这两处可能是同一文件的硬链接，编辑任一处会影响另一处。工具不会自动回滚或删除这些路径，重新运行会因冲突停止。请先备份并检查两处内容，保留需要的位置、手动处理重复路径，然后重新预览。

这不是整批事务或备份工具，不承诺断电持久性。整理期间请暂停同步程序和其他会编辑、替换文件或目录的操作；路径检查不用于防御恶意并发目录替换。重要笔记请先备份。

## 🧪 开发与测试

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
```

回归测试只操作临时目录，覆盖同名覆盖、已有目标、路径别名、预览、重复运行和中断/失败后的文件保留。CI 在 Linux、macOS、Windows 上运行 Python 3.13，并在 Ubuntu 22.04 上单独检查最低支持版本 Python 3.9。每个 CI 环境都会先执行普通安装、依赖检查和 CLI 启动检查，再安装开发依赖运行测试。

---

## 📄 开源协议

本项目基于 MIT License 开源。
