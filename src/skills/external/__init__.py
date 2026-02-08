"""External skills for third-party integrations."""

from src.skills.external.calendar import CalendarSkill
from src.skills.external.email import EmailSkill

__all__ = [
    "CalendarSkill",
    "EmailSkill",
]
