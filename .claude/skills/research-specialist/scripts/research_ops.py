#!/usr/bin/env python3
"""Research operations script - search, fetch, summarize, analyze."""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path


def web_search(query: str, num_results: int = 5) -> dict:
    """Search the web for information.

    Note: This is a placeholder. In production, integrate with a search API.
    """
    return {
        "status": "success",
        "query": query,
        "num_results": num_results,
        "message": "Use WebSearch tool or integrate with search API",
        "suggestion": f"Search for: {query}",
    }


def fetch_url(url: str) -> dict:
    """Fetch content from a URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AI-Task-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode("utf-8", errors="replace")
            return {
                "status": "success",
                "url": url,
                "content_length": len(content),
                "content_preview": content[:500],
            }
    except Exception as e:
        return {"status": "error", "url": url, "message": str(e)}


def fetch_library_docs(library: str, topic: str = None) -> dict:
    """Fetch documentation for a library.

    Uses Context7 skill if available, otherwise provides guidance.
    """
    # Check if context7 script exists
    context7_path = Path(__file__).parent.parent.parent / ".claude/skills/context7/scripts/context7.py"

    if context7_path.exists():
        return {
            "status": "use_skill",
            "skill": "context7",
            "commands": [
                f"python3 {context7_path} search \"{library}\"",
                f"python3 {context7_path} context \"<library-id>\" \"{topic or 'getting started'}\"",
            ],
        }

    # Fallback: suggest documentation URLs
    doc_urls = {
        "fastapi": "https://fastapi.tiangolo.com/",
        "openai-agents": "https://openai.github.io/openai-agents-python/",
        "pydantic": "https://docs.pydantic.dev/",
        "sqlite": "https://docs.python.org/3/library/sqlite3.html",
    }

    return {
        "status": "success",
        "library": library,
        "topic": topic,
        "doc_url": doc_urls.get(library.lower(), f"https://pypi.org/project/{library}/"),
        "suggestion": "Use WebFetch to retrieve documentation",
    }


def summarize_content(content: str, max_length: int = 200) -> dict:
    """Summarize content to key points."""
    lines = content.strip().splitlines()

    # Extract key lines (non-empty, not just whitespace)
    key_lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 10][:5]

    return {
        "status": "success",
        "original_length": len(content),
        "summary_points": key_lines,
        "note": "For better summaries, use an LLM",
    }


def analyze_data(file_path: str, analysis_type: str = "basic") -> dict:
    """Analyze data from a file."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text()

    if path.suffix == ".json":
        try:
            data = json.loads(content)
            return {
                "status": "success",
                "file_type": "json",
                "is_array": isinstance(data, list),
                "is_object": isinstance(data, dict),
                "top_keys": list(data.keys())[:10] if isinstance(data, dict) else None,
                "array_length": len(data) if isinstance(data, list) else None,
            }
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"Invalid JSON: {e}"}

    elif path.suffix == ".csv":
        lines = content.splitlines()
        return {
            "status": "success",
            "file_type": "csv",
            "rows": len(lines),
            "columns": len(lines[0].split(",")) if lines else 0,
            "headers": lines[0].split(",") if lines else [],
        }

    else:
        lines = content.splitlines()
        return {
            "status": "success",
            "file_type": path.suffix or "text",
            "lines": len(lines),
            "characters": len(content),
        }


def compare_sources(source1: str, source2: str) -> dict:
    """Compare information from two sources."""
    return {
        "status": "success",
        "source1": source1[:100],
        "source2": source2[:100],
        "note": "Manual comparison needed - review both sources for accuracy",
    }


def main():
    parser = argparse.ArgumentParser(description="Research operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search command
    search_parser = subparsers.add_parser("search", help="Web search")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--num", "-n", type=int, default=5)

    # fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch URL")
    fetch_parser.add_argument("url", help="URL to fetch")

    # docs command
    docs_parser = subparsers.add_parser("docs", help="Fetch library docs")
    docs_parser.add_argument("library", help="Library name")
    docs_parser.add_argument("--topic", "-t", help="Specific topic")

    # summarize command
    summarize_parser = subparsers.add_parser("summarize", help="Summarize content")
    summarize_parser.add_argument("content", help="Content to summarize")
    summarize_parser.add_argument("--max", "-m", type=int, default=200)

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze data file")
    analyze_parser.add_argument("file_path", help="File to analyze")
    analyze_parser.add_argument("--type", "-t", default="basic")

    args = parser.parse_args()

    if args.command == "search":
        result = web_search(args.query, args.num)
    elif args.command == "fetch":
        result = fetch_url(args.url)
    elif args.command == "docs":
        result = fetch_library_docs(args.library, args.topic)
    elif args.command == "summarize":
        result = summarize_content(args.content, args.max)
    elif args.command == "analyze":
        result = analyze_data(args.file_path, args.type)
    else:
        result = {"error": "Unknown command"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
