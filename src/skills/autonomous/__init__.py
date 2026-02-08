"""Autonomous Skills - Self-executing capabilities.

These skills can operate with minimal user intervention,
executing multi-step tasks autonomously.
"""

from .research import ResearchSkill
from .summarize import SummarizeSkill

__all__ = ["ResearchSkill", "SummarizeSkill"]
