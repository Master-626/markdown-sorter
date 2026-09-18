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
- ⚡ **无损保留**：仅进行文件复制或移动，不修改 Markdown 原文内容。

---

## 📦 安装方法

你可以使用 `pip` 本地安装：

```bash
git clone https://github.com/Master-626/markdown-sorter.git
cd markdown-sorter
pip install .
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

---

## 📄 开源协议

本项目基于 MIT License 开源。
