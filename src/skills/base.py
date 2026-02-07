"""Base skill class and interfaces.

All skills inherit from BaseSkill and implement the execute method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class SkillCategory(str, Enum):
    """Skill categories matching spec.md."""
    INTERNAL = "internal"     # App operations (always available)
    EXTERNAL = "external"     # Third-party integrations (on-demand)
    AUTONOMOUS = "autonomous" # Self-executing capabilities


class PermissionLevel(str, Enum):
    """Permission levels for skill execution."""
    INTERNAL = "internal"           # No approval, no external effects
    EXTERNAL_READ = "external_read" # Reads from external services
    EXTERNAL_WRITE = "external_write" # Writes to external services
    AUTONOMOUS = "autonomous"       # Executes independently


class LoadStrategy(str, Enum):
    """Skill loading strategies."""
    EAGER = "eager"   # Load at startup
    LAZY = "lazy"     # Load on first use
    JIT = "jit"       # Just-in-time compilation


@dataclass
class SkillManifest:
    """Skill manifest following spec.md format."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: SkillCategory = SkillCategory.INTERNAL

    # Triggers for skill selection
    triggers: list[str] = field(default_factory=list)

    # Parameter schema
    parameters: dict = field(default_factory=dict)

    # Permissions
    permission_level: PermissionLevel = PermissionLevel.INTERNAL
    approval_required: bool = False
    data_access: list[str] = field(default_factory=list)
    external_calls: bool = False

    # Execution
    timeout_ms: int = 5000
    load_strategy: LoadStrategy = LoadStrategy.LAZY

    def to_dict(self) -> dict:
        """Convert manifest to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category.value,
            "triggers": self.triggers,
            "parameters": self.parameters,
            "permissions": {
                "level": self.permission_level.value,
                "approval_required": self.approval_required,
                "data_access": self.data_access,
                "external_calls": self.external_calls,
            },
            "timeout_ms": self.timeout_ms,
            "load_strategy": self.load_strategy.value,
        }


@dataclass
class SkillResult:
    """Result from skill execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: dict = field(default_factory=dict)

    # For approval tracking
    requires_approval: bool = False
    approval_id: Optional[str] = None


@dataclass
class SkillContext:
    """Context passed to skill execution."""
    user_id: str
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    parameters: dict = field(default_factory=dict)
    conversation_history: list = field(default_factory=list)
    user_preferences: dict = field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    def __init__(self):
        self._manifest: Optional[SkillManifest] = None

    @property
    @abstractmethod
    def manifest(self) -> SkillManifest:
        """Return the skill manifest."""
        pass

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute the skill with given context.

        Args:
            context: Execution context with user, session, and parameters

        Returns:
            SkillResult with success status and data/error
        """
        pass

    async def validate_parameters(self, parameters: dict) -> tuple[bool, Optional[str]]:
        """Validate parameters against manifest schema.

        Args:
            parameters: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default implementation - subclasses can override
        required = self.manifest.parameters.get("required", [])
        for param in required:
            if param not in parameters:
                return False, f"Missing required parameter: {param}"
        return True, None

    def requires_approval(self, context: SkillContext) -> bool:
        """Check if this skill requires user approval.

        Args:
            context: Execution context

        Returns:
            True if approval is required
        """
        return self.manifest.approval_required

    def can_execute(self, context: SkillContext) -> tuple[bool, Optional[str]]:
        """Check if skill can execute with given context.

        Args:
            context: Execution context

        Returns:
            Tuple of (can_execute, reason_if_not)
        """
        return True, None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.manifest.name})>"
