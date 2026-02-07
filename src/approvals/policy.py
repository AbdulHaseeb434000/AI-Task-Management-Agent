"""Approval Policy - Defines permission tiers and action classification.

Manages:
- Auto-execute vs approval-required actions
- User-configurable overrides
- Permission tier classification
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import UserPreference
from src.database.connection import get_async_session


class ActionTier(Enum):
    """Permission tier for actions."""
    AUTO_EXECUTE = "auto_execute"      # No approval needed
    APPROVAL_REQUIRED = "approval_required"  # Always requires approval
    USER_CONFIGURABLE = "user_configurable"  # User can override


class ActionCategory(Enum):
    """Categories of actions."""
    TASK_MANAGEMENT = "task_management"
    COMMUNICATION = "communication"
    EXTERNAL_INTEGRATION = "external_integration"
    DATA_MODIFICATION = "data_modification"
    SYSTEM = "system"


@dataclass
class ActionDefinition:
    """Definition of an action and its default tier."""
    name: str
    description: str
    category: ActionCategory
    default_tier: ActionTier
    reversible: bool = True  # Can be undone?
    external: bool = False   # Has external side effects?


# Default action definitions
DEFAULT_ACTIONS: Dict[str, ActionDefinition] = {
    # Task Management - Auto Execute
    "task.create": ActionDefinition(
        name="task.create",
        description="Create a new task",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "task.update": ActionDefinition(
        name="task.update",
        description="Update task details",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "task.complete": ActionDefinition(
        name="task.complete",
        description="Mark task as complete",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "task.breakdown": ActionDefinition(
        name="task.breakdown",
        description="Break task into subtasks",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "task.prioritize": ActionDefinition(
        name="task.prioritize",
        description="Prioritize tasks",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "task.schedule": ActionDefinition(
        name="task.schedule",
        description="Schedule task",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "reminder.create": ActionDefinition(
        name="reminder.create",
        description="Set a reminder",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
        reversible=True,
    ),
    "task.search": ActionDefinition(
        name="task.search",
        description="Search tasks",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.AUTO_EXECUTE,
    ),

    # Task Management - Approval Required
    "task.delete": ActionDefinition(
        name="task.delete",
        description="Delete task permanently",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        reversible=False,
    ),
    "task.bulk_delete": ActionDefinition(
        name="task.bulk_delete",
        description="Delete multiple tasks",
        category=ActionCategory.TASK_MANAGEMENT,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        reversible=False,
    ),

    # Communication - Approval Required
    "email.send": ActionDefinition(
        name="email.send",
        description="Send an email",
        category=ActionCategory.COMMUNICATION,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        reversible=False,
        external=True,
    ),
    "message.send": ActionDefinition(
        name="message.send",
        description="Send a message (Slack, Discord, etc.)",
        category=ActionCategory.COMMUNICATION,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        reversible=False,
        external=True,
    ),

    # External Integrations - Approval Required
    "calendar.create_event": ActionDefinition(
        name="calendar.create_event",
        description="Create calendar event",
        category=ActionCategory.EXTERNAL_INTEGRATION,
        default_tier=ActionTier.USER_CONFIGURABLE,
        external=True,
    ),
    "calendar.update_event": ActionDefinition(
        name="calendar.update_event",
        description="Update calendar event",
        category=ActionCategory.EXTERNAL_INTEGRATION,
        default_tier=ActionTier.USER_CONFIGURABLE,
        external=True,
    ),
    "github.create_issue": ActionDefinition(
        name="github.create_issue",
        description="Create GitHub issue",
        category=ActionCategory.EXTERNAL_INTEGRATION,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        external=True,
    ),
    "github.create_pr": ActionDefinition(
        name="github.create_pr",
        description="Create pull request",
        category=ActionCategory.EXTERNAL_INTEGRATION,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        external=True,
    ),

    # Payments - Always Approval Required
    "payment.submit": ActionDefinition(
        name="payment.submit",
        description="Submit a payment",
        category=ActionCategory.EXTERNAL_INTEGRATION,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        reversible=False,
        external=True,
    ),
    "order.place": ActionDefinition(
        name="order.place",
        description="Place an order",
        category=ActionCategory.EXTERNAL_INTEGRATION,
        default_tier=ActionTier.APPROVAL_REQUIRED,
        reversible=False,
        external=True,
    ),
}


class ApprovalPolicy:
    """Manages approval policies for actions.

    Determines what actions need approval based on:
    - Default action definitions
    - User-specific overrides
    - Category-level settings
    """

    def __init__(self):
        """Initialize with default actions."""
        self._actions = DEFAULT_ACTIONS.copy()
        self._user_overrides: Dict[uuid.UUID, Dict[str, ActionTier]] = {}

    def register_action(self, definition: ActionDefinition) -> None:
        """Register a new action definition.

        Args:
            definition: The action definition.
        """
        self._actions[definition.name] = definition

    async def load_user_overrides(self, user_id: uuid.UUID) -> None:
        """Load user's approval preferences.

        Args:
            user_id: The user's ID.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "approvals",
                )
            )
            prefs = result.scalars().all()

            overrides = {}
            for pref in prefs:
                if pref.key.startswith("action."):
                    action_name = pref.key[7:]  # Remove "action." prefix
                    try:
                        overrides[action_name] = ActionTier(pref.value)
                    except ValueError:
                        pass

            self._user_overrides[user_id] = overrides

    async def set_user_override(
        self,
        user_id: uuid.UUID,
        action_name: str,
        tier: ActionTier,
    ) -> bool:
        """Set a user's preference for an action.

        Args:
            user_id: The user's ID.
            action_name: The action name.
            tier: The desired tier.

        Returns:
            True if override was set.
        """
        # Only allow override for user-configurable actions
        action = self._actions.get(action_name)
        if not action:
            return False

        # Don't allow promoting approval-required to auto-execute
        # for dangerous actions
        if action.default_tier == ActionTier.APPROVAL_REQUIRED and not action.reversible:
            if tier == ActionTier.AUTO_EXECUTE:
                return False

        async with get_async_session() as session:
            # Check if preference exists
            result = await session.execute(
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.category == "approvals",
                    UserPreference.key == f"action.{action_name}",
                )
            )
            pref = result.scalar_one_or_none()

            if pref:
                pref.value = tier.value
            else:
                pref = UserPreference(
                    user_id=user_id,
                    category="approvals",
                    key=f"action.{action_name}",
                    value=tier.value,
                )
                session.add(pref)

            await session.commit()

        # Update cache
        if user_id not in self._user_overrides:
            self._user_overrides[user_id] = {}
        self._user_overrides[user_id][action_name] = tier

        return True

    def requires_approval(
        self,
        user_id: uuid.UUID,
        action_name: str,
    ) -> bool:
        """Check if an action requires approval.

        Args:
            user_id: The user's ID.
            action_name: The action name.

        Returns:
            True if approval is required.
        """
        # Check user override first
        overrides = self._user_overrides.get(user_id, {})
        if action_name in overrides:
            return overrides[action_name] == ActionTier.APPROVAL_REQUIRED

        # Check default
        action = self._actions.get(action_name)
        if not action:
            # Unknown action - require approval for safety
            return True

        return action.default_tier == ActionTier.APPROVAL_REQUIRED

    def get_action_info(self, action_name: str) -> Optional[ActionDefinition]:
        """Get action definition.

        Args:
            action_name: The action name.

        Returns:
            ActionDefinition or None.
        """
        return self._actions.get(action_name)

    def get_all_actions(self) -> List[Dict[str, Any]]:
        """Get all registered actions.

        Returns:
            List of action info dicts.
        """
        return [
            {
                "name": action.name,
                "description": action.description,
                "category": action.category.value,
                "default_tier": action.default_tier.value,
                "reversible": action.reversible,
                "external": action.external,
            }
            for action in self._actions.values()
        ]

    def get_user_settings(
        self,
        user_id: uuid.UUID,
    ) -> Dict[str, Dict[str, Any]]:
        """Get user's approval settings.

        Args:
            user_id: The user's ID.

        Returns:
            Dict of action name to settings.
        """
        overrides = self._user_overrides.get(user_id, {})
        settings = {}

        for name, action in self._actions.items():
            current_tier = overrides.get(name, action.default_tier)
            settings[name] = {
                "description": action.description,
                "default_tier": action.default_tier.value,
                "current_tier": current_tier.value,
                "is_overridden": name in overrides,
                "can_override": (
                    action.default_tier == ActionTier.USER_CONFIGURABLE
                    or (action.default_tier == ActionTier.AUTO_EXECUTE)
                    or (action.default_tier == ActionTier.APPROVAL_REQUIRED and action.reversible)
                ),
            }

        return settings


# Global policy manager
_policy: Optional[ApprovalPolicy] = None


def get_policy_manager() -> ApprovalPolicy:
    """Get the global policy manager."""
    global _policy
    if _policy is None:
        _policy = ApprovalPolicy()
    return _policy
