"""Skill Registry - Dynamic loading and management of skills.

Responsibilities from spec.md:
- Maintains catalog of all available skills
- Handles dynamic loading/unloading
- Validates skill permissions before execution
- Tracks skill versions and compatibility
"""

import asyncio
import importlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import (
    BaseSkill,
    SkillCategory,
    SkillContext,
    SkillManifest,
    SkillResult,
    LoadStrategy,
    PermissionLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class RegisteredSkill:
    """A skill registered in the registry."""
    manifest: SkillManifest
    module_path: str
    skill_class: Optional[Type[BaseSkill]] = None
    instance: Optional[BaseSkill] = None
    enabled: bool = True
    load_count: int = 0
    last_used: Optional[float] = None
    error_count: int = 0


class SkillRegistry:
    """Central registry for all skills.

    Loading Strategy (from spec.md):
    - Eager load: Internal CRUD skills (always needed)
    - Lazy load: External integrations (only when user requests)
    - JIT compile: Autonomous skills (loaded for specific tasks)
    """

    def __init__(self):
        self._skills: Dict[str, RegisteredSkill] = {}
        self._trigger_index: Dict[str, List[str]] = {}  # trigger -> skill names
        self._category_index: Dict[SkillCategory, List[str]] = {
            cat: [] for cat in SkillCategory
        }
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the registry and load eager skills."""
        if self._initialized:
            return

        # Discover and register all skills
        await self._discover_skills()

        # Load eager skills immediately
        for name, registered in self._skills.items():
            if registered.manifest.load_strategy == LoadStrategy.EAGER:
                await self._load_skill(name)

        self._initialized = True
        logger.info(f"Skill registry initialized with {len(self._skills)} skills")

    async def _discover_skills(self) -> None:
        """Discover skills from the skills directory."""
        skills_dir = Path(__file__).parent

        # Discover internal skills
        internal_dir = skills_dir / "internal"
        if internal_dir.exists():
            await self._discover_from_directory(internal_dir, SkillCategory.INTERNAL)

        # Discover external skills
        external_dir = skills_dir / "external"
        if external_dir.exists():
            await self._discover_from_directory(external_dir, SkillCategory.EXTERNAL)

        # Discover autonomous skills
        autonomous_dir = skills_dir / "autonomous"
        if autonomous_dir.exists():
            await self._discover_from_directory(autonomous_dir, SkillCategory.AUTONOMOUS)

    async def _discover_from_directory(
        self, directory: Path, category: SkillCategory
    ) -> None:
        """Discover skills from a directory."""
        for path in directory.glob("*.py"):
            if path.name.startswith("_"):
                continue

            module_name = path.stem
            module_path = f"src.skills.{category.value}.{module_name}"

            try:
                # Import module to get manifest
                module = importlib.import_module(module_path)

                # Find skill class (subclass of BaseSkill)
                skill_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill
                    ):
                        skill_class = attr
                        break

                if skill_class:
                    # Create temporary instance to get manifest
                    temp_instance = skill_class()
                    manifest = temp_instance.manifest

                    self.register_skill(
                        manifest=manifest,
                        module_path=module_path,
                        skill_class=skill_class,
                    )
                    logger.debug(f"Discovered skill: {manifest.name}")

            except Exception as e:
                logger.warning(f"Failed to discover skill from {path}: {e}")

    def register_skill(
        self,
        manifest: SkillManifest,
        module_path: str,
        skill_class: Optional[Type[BaseSkill]] = None,
    ) -> None:
        """Register a skill with the registry.

        Args:
            manifest: Skill manifest
            module_path: Python module path for the skill
            skill_class: Optional skill class (loaded lazily if not provided)
        """
        registered = RegisteredSkill(
            manifest=manifest,
            module_path=module_path,
            skill_class=skill_class,
        )

        self._skills[manifest.name] = registered
        self._category_index[manifest.category].append(manifest.name)

        # Index triggers for quick lookup
        for trigger in manifest.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower not in self._trigger_index:
                self._trigger_index[trigger_lower] = []
            self._trigger_index[trigger_lower].append(manifest.name)

        logger.info(f"Registered skill: {manifest.name} ({manifest.category.value})")

    async def _load_skill(self, name: str) -> Optional[BaseSkill]:
        """Load a skill instance.

        Args:
            name: Skill name

        Returns:
            Loaded skill instance or None
        """
        registered = self._skills.get(name)
        if not registered:
            logger.error(f"Skill not found: {name}")
            return None

        if registered.instance:
            return registered.instance

        try:
            # Load class if not already loaded
            if not registered.skill_class:
                module = importlib.import_module(registered.module_path)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill
                    ):
                        registered.skill_class = attr
                        break

            if not registered.skill_class:
                logger.error(f"No skill class found in {registered.module_path}")
                return None

            # Create instance
            registered.instance = registered.skill_class()
            registered.load_count += 1

            logger.debug(f"Loaded skill: {name}")
            return registered.instance

        except Exception as e:
            logger.error(f"Failed to load skill {name}: {e}")
            registered.error_count += 1
            return None

    async def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name, loading if necessary.

        Args:
            name: Skill name

        Returns:
            Skill instance or None
        """
        registered = self._skills.get(name)
        if not registered or not registered.enabled:
            return None

        if not registered.instance:
            await self._load_skill(name)

        if registered.instance:
            registered.last_used = time.time()

        return registered.instance

    def find_skills_by_trigger(self, query: str) -> List[str]:
        """Find skills that match a trigger query.

        Args:
            query: User query to match against triggers

        Returns:
            List of matching skill names
        """
        query_lower = query.lower()
        matched = set()

        for trigger, skills in self._trigger_index.items():
            if trigger in query_lower or query_lower in trigger:
                matched.update(skills)

        return list(matched)

    def find_skills_by_category(self, category: SkillCategory) -> List[str]:
        """Find skills by category.

        Args:
            category: Skill category

        Returns:
            List of skill names in category
        """
        return self._category_index.get(category, [])

    async def execute_skill(
        self,
        name: str,
        context: SkillContext,
    ) -> SkillResult:
        """Execute a skill with error handling and timeout.

        Args:
            name: Skill name
            context: Execution context

        Returns:
            SkillResult with success/error
        """
        skill = await self.get_skill(name)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill not found or disabled: {name}",
            )

        registered = self._skills[name]

        # Validate parameters
        is_valid, error = await skill.validate_parameters(context.parameters)
        if not is_valid:
            return SkillResult(success=False, error=error)

        # Check if approval is required
        if skill.requires_approval(context):
            return SkillResult(
                success=False,
                requires_approval=True,
                error="This action requires user approval",
                metadata={"skill": name, "parameters": context.parameters},
            )

        # Execute with timeout
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                skill.execute(context),
                timeout=registered.manifest.timeout_ms / 1000,
            )
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        except asyncio.TimeoutError:
            registered.error_count += 1
            return SkillResult(
                success=False,
                error=f"Skill execution timed out after {registered.manifest.timeout_ms}ms",
                duration_ms=registered.manifest.timeout_ms,
            )

        except Exception as e:
            registered.error_count += 1
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Skill {name} execution failed: {e}")
            return SkillResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    def get_manifest(self, name: str) -> Optional[SkillManifest]:
        """Get a skill's manifest.

        Args:
            name: Skill name

        Returns:
            SkillManifest or None
        """
        registered = self._skills.get(name)
        return registered.manifest if registered else None

    def list_skills(
        self,
        category: Optional[SkillCategory] = None,
        enabled_only: bool = True,
    ) -> List[SkillManifest]:
        """List all registered skills.

        Args:
            category: Optional category filter
            enabled_only: Only include enabled skills

        Returns:
            List of skill manifests
        """
        manifests = []
        for name, registered in self._skills.items():
            if enabled_only and not registered.enabled:
                continue
            if category and registered.manifest.category != category:
                continue
            manifests.append(registered.manifest)
        return manifests

    def enable_skill(self, name: str) -> bool:
        """Enable a skill."""
        if name in self._skills:
            self._skills[name].enabled = True
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        """Disable a skill."""
        if name in self._skills:
            self._skills[name].enabled = False
            return True
        return False

    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "total_skills": len(self._skills),
            "loaded_skills": sum(
                1 for s in self._skills.values() if s.instance is not None
            ),
            "by_category": {
                cat.value: len(names) for cat, names in self._category_index.items()
            },
            "total_errors": sum(s.error_count for s in self._skills.values()),
        }


# Global registry instance
_registry: Optional[SkillRegistry] = None


async def get_registry() -> SkillRegistry:
    """Get the global skill registry, initializing if needed."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        await _registry.initialize()
    return _registry
