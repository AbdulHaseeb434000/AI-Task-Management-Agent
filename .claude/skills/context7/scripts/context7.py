#!/usr/bin/env python3
"""
Context7 Documentation Fetcher

Fetches up-to-date library documentation via the Context7 API.

Usage:
    python context7.py search "<library-name>"
    python context7.py context "<library-id>" "<query>" [--type txt|md] [--tokens N]

Examples:
    python context7.py search "next.js"
    python context7.py context "/vercel/next.js" "app router middleware"
    python context7.py context "/facebook/react" "useEffect" --tokens 3000
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "https://context7.com/api"


def search_libraries(query: str) -> dict:
    """Search for libraries matching the query."""
    url = f"{BASE_URL}/v1/search?query={urllib.parse.quote(query)}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP Error: {e.code}", "message": e.reason}
    except urllib.error.URLError as e:
        return {"error": "URL Error", "message": str(e.reason)}
    except Exception as e:
        return {"error": "Error", "message": str(e)}


def get_context(library_id: str, query: str, output_type: str = "txt", tokens: int = 5000) -> str:
    """Fetch documentation context for a library."""
    # Ensure library_id starts with /
    if not library_id.startswith("/"):
        library_id = f"/{library_id}"

    params = {
        "query": query,
        "type": output_type,
        "tokens": str(tokens)
    }

    url = f"{BASE_URL}/v1{library_id}/context?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read().decode()
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} - {e.reason}"
    except urllib.error.URLError as e:
        return f"Error: {e.reason}"
    except Exception as e:
        return f"Error: {e}"


def format_search_results(data: dict) -> str:
    """Format search results for display."""
    if "error" in data:
        return f"Error: {data['error']} - {data.get('message', '')}"

    libraries = data.get("libraries", data.get("results", []))

    if not libraries:
        return "No libraries found."

    output = ["Found libraries:\n"]

    for lib in libraries[:10]:  # Show top 10
        lib_id = lib.get("id", lib.get("libraryId", "N/A"))
        name = lib.get("name", lib.get("title", "Unknown"))
        description = lib.get("description", "")[:100]

        output.append(f"  ID: {lib_id}")
        output.append(f"  Name: {name}")
        if description:
            output.append(f"  Description: {description}...")
        output.append("")

    output.append("\nUse the ID with the 'context' command:")
    output.append(f'  python context7.py context "{libraries[0].get("id", "/org/repo")}" "your query"')

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch library documentation via Context7 API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "react"
  %(prog)s context "/facebook/react" "hooks useEffect"
  %(prog)s context "/vercel/next.js" "middleware" --tokens 3000
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for a library")
    search_parser.add_argument("query", help="Library name to search for")

    # Context command
    context_parser = subparsers.add_parser("context", help="Get documentation context")
    context_parser.add_argument("library_id", help="Context7 library ID (e.g., /vercel/next.js)")
    context_parser.add_argument("query", help="Documentation query")
    context_parser.add_argument("--type", choices=["txt", "md"], default="txt",
                                help="Output format (default: txt)")
    context_parser.add_argument("--tokens", type=int, default=5000,
                                help="Maximum tokens to return (default: 5000)")

    args = parser.parse_args()

    if args.command == "search":
        result = search_libraries(args.query)
        print(format_search_results(result))

    elif args.command == "context":
        result = get_context(
            args.library_id,
            args.query,
            output_type=args.type,
            tokens=args.tokens
        )
        print(result)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
