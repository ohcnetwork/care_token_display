from uuid import UUID

from care.emr.models import Token
from care.emr.models.scheduling.schedule import SchedulableResource
from care.emr.resources.scheduling.schedule.spec import SchedulableResourceTypeOptions
from care.users.models import User


def get_token_display_cache_key(sub_queue_external_id: UUID) -> str:
    """
    Generate a cache key for token display partial view.
    """
    return f"token_display:partial:{sub_queue_external_id}"


def fmt_user_name(obj: User) -> str:
    parts = [obj.prefix, obj.first_name, obj.last_name, obj.suffix]
    return " ".join(filter(None, parts))


def fmt_schedule_resource_name(obj: SchedulableResource) -> str:
    if obj.resource_type == SchedulableResourceTypeOptions.practitioner.value:
        return fmt_user_name(obj.user)
    if obj.resource_type == SchedulableResourceTypeOptions.healthcare_service.value:
        return obj.healthcare_service.name
    if obj.resource_type == SchedulableResourceTypeOptions.location.value:
        return obj.location.name
    raise ValueError("Invalid resource type")


def fmt_token_number(token: Token) -> str:
    return f"{token.category.shorthand}-{token.number:03d}"
