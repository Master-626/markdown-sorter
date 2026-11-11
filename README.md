## 中文摘要

Markdown Sorter 把一个目录里的 Markdown 笔记移动到子文件夹，分类依据是 YAML Front Matter 的 `tags`、文件时间，或文件名/标签中的关键词。它只移动文件，不改写正文。整批移动会先做安全检查：目标冲突、不安全路径、损坏的配置，或标签/规则模式下无法解析的 Front Matter，都会让命令报错停止，并且不会覆盖已有文件。

Python 3.9+ 下执行 `pip install .` 安装。`markdown-sorter sort <目录> --dry-run` 只预览。`python -m pytest -q` 跑测试，`ruff` 做检查。配置项 `exclude` 或可重复的 `--exclude` 可以把 README、模板等笔记留在原地。命令行提示是中文。

---

# Markdown Sorter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

Markdown Sorter is a command-line tool that files Markdown notes into subfolders. It can group them by a YAML front matter tag, by the file's creation or modification time, or by keyword rules. The note body is never rewritten.

The tool plans the whole batch before it moves anything. If two notes would land on the same path, a destination already exists, a category is not a safe relative path, the config file is invalid, or tag/rule mode cannot read a note's front matter, the command stops with an error and does not overwrite existing files.

Command output is in Chinese. Read it as UTF-8, including when you redirect it on Windows.

## Features

- **Tags.** The primary tag becomes a directory. `tags: [python, cli]` with the default index files the note under `python/`.
- **Date.** Notes are filed under a `strftime` pattern such as `%Y/%m`. A real creation time is used when the platform provides one; otherwise the modification time is used.
- **Rules.** The first matching rule wins. A keyword is a case-insensitive substring of the file name (without `.md`), or it equals a tag or one of that tag's segments (`python` matches the tag `python-dev` and not `network`).
- **Exclude globs.** Matching notes stay where they are. This is off unless you set it.
- **Dry run.** Print the same plan without creating directories or moving files.

## Install

Python 3.9 or newer is required.

```bash
git clone https://github.com/Master-626/markdown-sorter.git
cd markdown-sorter
pip install .
```

On Python 3.9 the package depends on `python-frontmatter` older than 1.2, because 1.2 imports `typing.TypeGuard`. Python 3.10 and newer use the current release. Check the install with:

```bash
python -m pip check
markdown-sorter --version
markdown-sorter sort --help
```

## Usage

```bash
# File notes by their first YAML tag.
markdown-sorter sort /path/to/notes

# Show the plan and change nothing.
markdown-sorter sort /path/to/notes --dry-run

# File notes under YYYY/MM instead.
markdown-sorter sort /path/to/notes --mode date

# Use a TOML config, and leave README plus everything under templates/.
markdown-sorter sort /path/to/notes --config config.example.toml \
  --exclude README.md --exclude 'templates/**'
```

Quote globs. An unquoted `templates/**` is expanded by the shell before Markdown Sorter sees it.

A note that is already at its destination is skipped. Running the command again after a successful sort reports those files as skipped and does not move them a second time.

### Options

| Option | Meaning |
| --- | --- |
| `directory` | Notes root. Must be an existing directory, not a symlink or junction. |
| `-c`, `--config PATH` | TOML config file. Missing files are not an error when you omit this option. A file that exists but cannot be parsed is an error. |
| `-m`, `--mode` | `tag`, `date`, or `rule`. Overrides `general.mode` for this run only. |
| `--dry-run` | Print the plan. Creates nothing and moves nothing. |
| `--exclude GLOB` | Leave matching notes in place. Repeat the flag to add patterns. Appended to `general.exclude`. |
| `--version` | Print the version. |
| `--help` | Print help. |

## Configuration

`config.example.toml` is a commented starting point. Category directories are relative to the notes root.

```toml
[general]
mode = "tag"              # tag, date, or rule
primary_tag_index = 0     # which tag to use; 0 is the first
fallback_dir = "Unsorted" # used when a note has no matching category
exclude = ["README.md", "templates/**"]

[date]
format = "%Y/%m"

[rules]
"Projects/Python" = ["python", "pip"]
"Work/Meeting" = ["meeting", "minutes"]
```

`general.exclude` and every `--exclude` value are globs:

- `*`, `?`, and `**` are special. Other characters are literal, including brackets.
- `*` and `?` do not cross `/`. `docs/*.md` matches `docs/a.md` and not `docs/sub/a.md`.
- `**` crosses directories. `templates/**` matches notes inside `templates` and not a file named `templates.md`.
- A pattern with no `/` matches the file name anywhere, so `README.md` also matches `guide/README.md`.
- Matching is case-insensitive.

Patterns have to be relative. Absolute paths, backslashes, `..`, empty segments, and control characters are rejected.

### Tags

Front matter is YAML between `---` lines at the start of the file. Tag scalars are kept as written: `yes` stays `yes` (it is not turned into `True`), `01` stays `01`, and `1.10` stays `1.10`. A missing `tags` key, `tags: null`, or a note with no front matter has no tags and uses `fallback_dir`. A leading thematic break (`---` followed by a heading, without a closing `---`) is not front matter.

`tags` must be a string or a list of strings. `null` inside the list, a mapping, or YAML that does not parse is an error in `tag` and `rule` mode, and nothing in that batch is moved. `date` mode does not read front matter; it only uses the file timestamp. A UTF-8 BOM is accepted. Text that is not UTF-8 is an error in `tag` and `rule` mode.

`primary_tag_index` has to be a non-negative integer. A boolean is rejected (`true` is not `1`). If the index is past the end of the list, the note uses `fallback_dir`.

### Rules

Each rule maps a destination directory to a list of non-empty keyword strings. The first matching rule wins. A keyword matches the filename stem when it is a case-insensitive substring, so `python` matches `my-python-notes.md` and `work` also matches `network.md`. Choose distinctive keywords. A keyword matches a tag when it equals the whole tag or a segment split on hyphens, underscores, and other non-letter characters: `python` matches `python-dev`, and `work` matches `work-notes` but not `network` or `homework`. An empty keyword is rejected because it would match every note. A bare string instead of a list is rejected because it would otherwise be read character by character.

### Dates

`date.format` is a non-empty `strftime` pattern. The result is checked with the same path rules as a tag, so a format that produces `..`, a drive letter, or a colon still fails the run. When `st_birthtime` is missing or not a positive timestamp, the modification time is used. That includes platforms that report creation time as `0`.

## Safety

Category paths, including tags, the fallback directory, rule directories, and formatted dates, must be relative segments inside the notes root. The command rejects absolute paths, drive prefixes, backslashes, `.` and `..`, empty segments, leading or trailing whitespace, trailing dots, control characters, `<>:"|?*`, and Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`, including names like `NUL.txt`). Those checks run on every operating system so a tree sorted on Linux does not become illegal on Windows.

- The batch is checked before any directory is created for a move. Two notes with the same target, an existing target, or a file/directory clash abort the run. Nothing from that plan is moved.
- The tool does not overwrite and does not rename automatically. Fix the clash, then run `--dry-run`. A destination that would be freed by another move in the same batch is still a clash; files are not swapped.
- Names that match after case-folding or Unicode normalization are clashes. A regular file that is already at its exact destination is skipped. `.md` and `.MD` are both included.
- Symlink files are not moved. Symlink directories are not walked. A symlink or Windows junction cannot be the notes root or a parent of a source or destination. Two Markdown names that are hard links of each other abort the run.
- Each move creates a hard link that cannot replace an existing name, checks that the source is still the planned file, then deletes the old path. If something else creates the destination after the plan, the move fails. The source and destination must be on the same filesystem, and that filesystem must support hard links. Cross-device moves and FAT/exFAT fail and leave the source in place. There is no copy/delete fallback. A dry run does not prove that the process can write or create hard links.

**After an interrupt:** Ctrl+C or a permission error can leave earlier moves finished, and the current file can exist at both the old and new paths. Those two paths may be hard links of one file, so editing either one changes the other. The tool does not roll back or delete them. A later run stops on the clash. Back up, compare both copies, keep the one you want, remove the duplicate path, then preview again.

This is not a transaction and not a backup. It does not promise durability across a power loss. Pause sync tools and other writers while a sort is running. The path checks are not a defense against a hostile process racing directory replacement. Copy important notes first.

## Tests

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

The tests use temporary directories. They cover tag, date, and rule classification, exclude globs, previews, collisions, unsafe paths, invalid config and front matter, and files left in place when a move fails.

GitHub Actions runs ruff and pytest on Python 3.9, 3.10, 3.11, 3.12, and 3.13. Python 3.9 runs on Ubuntu 22.04 because newer GitHub-hosted images do not include that runtime. macOS and Windows run 3.13. Each job installs the package, runs `pip check` and the CLI, then installs the dev extra and runs pytest, ruff, and a build.

## License

MIT. See [LICENSE](LICENSE).
