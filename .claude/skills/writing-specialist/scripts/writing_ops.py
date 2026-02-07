#!/usr/bin/env python3
"""Writing operations script - draft, edit, format, proofread content."""

import argparse
import json
import re
from pathlib import Path


def draft_document(
    output_path: str,
    title: str,
    content_type: str,
    sections: list = None,
) -> dict:
    """Draft a new document with structure."""
    path = Path(output_path)

    # Document templates by type
    templates = {
        "readme": f"# {title}\n\n## Overview\n\n## Installation\n\n## Usage\n\n## License\n",
        "api_doc": f"# {title}\n\n## Endpoints\n\n## Authentication\n\n## Examples\n\n## Errors\n",
        "report": f"# {title}\n\n## Executive Summary\n\n## Findings\n\n## Recommendations\n\n## Appendix\n",
        "proposal": f"# {title}\n\n## Problem Statement\n\n## Proposed Solution\n\n## Timeline\n\n## Budget\n",
        "article": f"# {title}\n\n## Introduction\n\n## Main Content\n\n## Conclusion\n",
    }

    content = templates.get(content_type, f"# {title}\n\n")

    if sections:
        content = f"# {title}\n\n"
        for section in sections:
            content += f"## {section}\n\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

    return {
        "status": "created",
        "path": str(path),
        "content_type": content_type,
        "sections": sections or [],
    }


def edit_content(
    file_path: str,
    edit_type: str,
    find: str = None,
    replace: str = None,
) -> dict:
    """Edit content in a file."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()
    original_length = len(content)

    if edit_type == "replace" and find and replace:
        new_content = content.replace(find, replace)
        count = content.count(find)
        path.write_text(new_content)
        return {
            "status": "success",
            "edit_type": "replace",
            "replacements": count,
        }

    elif edit_type == "append":
        if replace:  # Use replace as the content to append
            new_content = content + "\n" + replace
            path.write_text(new_content)
            return {"status": "success", "edit_type": "append"}

    elif edit_type == "prepend":
        if replace:
            new_content = replace + "\n" + content
            path.write_text(new_content)
            return {"status": "success", "edit_type": "prepend"}

    return {
        "status": "no_change",
        "edit_type": edit_type,
        "message": "No edits applied",
    }


def format_document(file_path: str, output_format: str) -> dict:
    """Format/convert a document."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()

    if output_format == "plain":
        # Strip markdown formatting
        plain = re.sub(r"#+ ", "", content)  # Remove headers
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", plain)  # Remove bold
        plain = re.sub(r"\*(.+?)\*", r"\1", plain)  # Remove italic
        plain = re.sub(r"`(.+?)`", r"\1", plain)  # Remove inline code

        output_path = path.with_suffix(".txt")
        output_path.write_text(plain)
        return {"status": "success", "output": str(output_path)}

    elif output_format == "html":
        # Basic markdown to HTML
        html = content
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)

        output_path = path.with_suffix(".html")
        output_path.write_text(f"<!DOCTYPE html>\n<html><body>\n{html}\n</body></html>")
        return {"status": "success", "output": str(output_path)}

    return {"status": "error", "message": f"Unknown format: {output_format}"}


def proofread(file_path: str) -> dict:
    """Check document for common issues."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()
    issues = []

    # Check for common issues
    if "  " in content:
        issues.append("Double spaces detected")
    if content != content.strip():
        issues.append("Leading/trailing whitespace")
    if "\t" in content and "    " in content:
        issues.append("Mixed tabs and spaces")

    # Check markdown issues
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if line.startswith("#") and not line.startswith("# ") and len(line) > 1:
            if not line[1] == "#":
                issues.append(f"Line {i}: Missing space after # in header")

    return {
        "status": "success",
        "issues_found": len(issues),
        "issues": issues,
        "clean": len(issues) == 0,
    }


def generate_outline(topic: str, depth: int = 2) -> dict:
    """Generate a document outline."""
    # Basic outline structure
    outline = {
        "topic": topic,
        "sections": [
            {"title": "Introduction", "subsections": ["Background", "Purpose"]},
            {"title": "Main Content", "subsections": ["Key Points", "Details", "Examples"]},
            {"title": "Conclusion", "subsections": ["Summary", "Next Steps"]},
        ],
    }

    if depth == 1:
        outline["sections"] = [{"title": s["title"]} for s in outline["sections"]]

    return {"status": "success", "outline": outline}


def word_count(file_path: str) -> dict:
    """Count words in a document."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()
    words = len(content.split())
    chars = len(content)
    lines = len(content.splitlines())

    return {
        "status": "success",
        "words": words,
        "characters": chars,
        "lines": lines,
        "reading_time_minutes": max(1, words // 200),
    }


def main():
    parser = argparse.ArgumentParser(description="Writing operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # draft command
    draft_parser = subparsers.add_parser("draft", help="Draft document")
    draft_parser.add_argument("output_path", help="Output file path")
    draft_parser.add_argument("--title", "-t", required=True)
    draft_parser.add_argument("--type", default="article",
                               choices=["readme", "api_doc", "report", "proposal", "article"])
    draft_parser.add_argument("--sections", "-s", nargs="+", help="Custom sections")

    # edit command
    edit_parser = subparsers.add_parser("edit", help="Edit content")
    edit_parser.add_argument("file_path", help="File to edit")
    edit_parser.add_argument("--type", "-t", default="replace",
                              choices=["replace", "append", "prepend"])
    edit_parser.add_argument("--find", "-f", help="Text to find")
    edit_parser.add_argument("--replace", "-r", help="Replacement text")

    # format command
    format_parser = subparsers.add_parser("format", help="Format document")
    format_parser.add_argument("file_path", help="File to format")
    format_parser.add_argument("--output", "-o", default="plain",
                                choices=["plain", "html"])

    # proofread command
    proof_parser = subparsers.add_parser("proofread", help="Proofread document")
    proof_parser.add_argument("file_path", help="File to proofread")

    # outline command
    outline_parser = subparsers.add_parser("outline", help="Generate outline")
    outline_parser.add_argument("topic", help="Topic for outline")
    outline_parser.add_argument("--depth", "-d", type=int, default=2)

    # wordcount command
    wc_parser = subparsers.add_parser("wordcount", help="Count words")
    wc_parser.add_argument("file_path", help="File to count")

    args = parser.parse_args()

    if args.command == "draft":
        result = draft_document(args.output_path, args.title, args.type, args.sections)
    elif args.command == "edit":
        result = edit_content(args.file_path, args.type, args.find, args.replace)
    elif args.command == "format":
        result = format_document(args.file_path, args.output)
    elif args.command == "proofread":
        result = proofread(args.file_path)
    elif args.command == "outline":
        result = generate_outline(args.topic, args.depth)
    elif args.command == "wordcount":
        result = word_count(args.file_path)
    else:
        result = {"error": "Unknown command"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
