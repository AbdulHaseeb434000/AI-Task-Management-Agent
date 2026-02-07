"""Research Agent - Specialist for information gathering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents import Agent, function_tool


@function_tool
def web_search(
    query: str,
    num_results: int = 5,
) -> dict:
    """Search the web for information.

    Args:
        query: Search query
        num_results: Number of results to return

    Returns:
        Search results with titles, URLs, and snippets
    """
    # In production, integrate with a search API
    return {
        "status": "success",
        "query": query,
        "results": [],
        "total_results": 0,
    }


@function_tool
def fetch_url(
    url: str,
    extract_type: str = "text",
) -> dict:
    """Fetch and extract content from a URL.

    Args:
        url: The URL to fetch
        extract_type: What to extract (text, links, images, all)

    Returns:
        Extracted content from the page
    """
    # In production, fetch and parse the URL
    return {
        "status": "success",
        "url": url,
        "title": "",
        "content": "",
        "links": [],
    }


@function_tool
def fetch_library_docs(
    library_name: str,
    query: str,
    tokens: int = 5000,
) -> dict:
    """Fetch documentation for a library using Context7.

    Args:
        library_name: Name of the library (e.g., "react", "fastapi")
        query: Specific documentation query
        tokens: Maximum tokens to return

    Returns:
        Library documentation content
    """
    # This would integrate with Context7 API
    return {
        "status": "success",
        "library": library_name,
        "query": query,
        "documentation": "",
        "examples": [],
    }


@function_tool
def summarize_content(
    content: str,
    max_length: int = 500,
    style: str = "bullet_points",
) -> dict:
    """Summarize content into key points.

    Args:
        content: The content to summarize
        max_length: Maximum summary length in words
        style: Summary style (bullet_points, paragraph, executive)

    Returns:
        Summarized content
    """
    return {
        "status": "success",
        "original_length": len(content.split()),
        "summary": "",
        "key_points": [],
    }


@function_tool
def analyze_data(
    data: str,
    analysis_type: str = "general",
) -> dict:
    """Analyze data and extract insights.

    Args:
        data: The data to analyze (JSON, CSV, or text)
        analysis_type: Type of analysis (general, statistical, comparative)

    Returns:
        Analysis results with insights
    """
    return {
        "status": "success",
        "analysis_type": analysis_type,
        "insights": [],
        "recommendations": [],
    }


RESEARCH_AGENT_INSTRUCTIONS = """You are a Research Agent specialized in information gathering and analysis.

## Capabilities

- **Web Search**: Find current information on any topic
- **Fetch URLs**: Extract content from web pages
- **Library Docs**: Get up-to-date library documentation
- **Summarize**: Condense information into key points
- **Analyze**: Extract insights from data

## Guidelines

1. Always verify information from multiple sources when possible
2. Cite sources for factual claims
3. Distinguish between facts and opinions
4. Provide balanced perspectives on controversial topics
5. Note when information might be outdated

## Research Process

1. Understand the research question
2. Search for relevant sources
3. Extract and analyze key information
4. Synthesize findings
5. Present with citations

## When Done

After completing research:
1. Summarize key findings
2. List sources used
3. Note confidence level in findings
4. Highlight any gaps or uncertainties

Be thorough and accurate. Quality research saves time downstream.
"""


def create_research_agent() -> Agent:
    """Create the research specialist agent."""
    return Agent(
        name="Research Agent",
        instructions=RESEARCH_AGENT_INSTRUCTIONS,
        model="gpt-4o",
        tools=[
            web_search,
            fetch_url,
            fetch_library_docs,
            summarize_content,
            analyze_data,
        ],
    )


# Alias for consistency
ResearchAgent = create_research_agent
