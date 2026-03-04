---
name: 🔌 Plugin Submission
about: Share a rename plugin for the community plugins/ directory
title: "[PLUGIN] "
labels: ["plugin", "community"]
assignees: ''
---

## Plugin Name
<!-- e.g. audiobook_rename, manga_chapter_sort -->

## What It Does
<!-- Describe the rename logic — what file types, what naming scheme. -->

## Supported Extensions
<!-- e.g. .mp3, .m4b, .epub -->

## Plugin Code
```python
# Paste your plugin code here
EXTENSIONS = [".ext"]

def rename(fp, meta):
    ...
```

## Example
| Original filename | Renamed to |
|---|---|
| book.epub | AuthorName - Title.epub |
