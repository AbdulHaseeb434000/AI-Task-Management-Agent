---
name: writing-specialist
description: Create and edit documents including READMEs, reports, proposals, and articles. Use when the task involves drafting content, editing text, formatting documents, or proofreading.
---

# Writing Specialist

Execute writing operations using `scripts/writing_ops.py`.

## Commands

### Draft Document
```bash
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py draft <output_path> -t "<title>" --type <type>
```
Types: `readme`, `api_doc`, `report`, `proposal`, `article`

### Edit Content
```bash
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py edit <file_path> -t replace -f "<find>" -r "<replace>"
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py edit <file_path> -t append -r "<content>"
```

### Format Document
```bash
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py format <file_path> -o plain
```

### Proofread
```bash
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py proofread <file_path>
```

### Generate Outline
```bash
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py outline "<topic>" -d 2
```

### Word Count
```bash
uv run python .claude/skills/writing-specialist/scripts/writing_ops.py wordcount <file_path>
```

## Workflow

1. Generate outline for structure
2. Draft initial document
3. Edit for clarity
4. Proofread and format
