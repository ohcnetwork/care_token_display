from care.emr.models import Token
from care.emr.models.scheduling.schedule import SchedulableResource
from care.emr.resources.scheduling.schedule.spec import SchedulableResourceTypeOptions
from care.users.models import User


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


def build_display_path(sub_queues, service_account: User | None) -> str | None:
    """Build the SSR display path for a configured token display device."""
    from django.urls import reverse
    from rest_framework.authtoken.models import Token as AuthToken

    if not sub_queues or service_account is None:
        return None

    key = AuthToken.objects.filter(user=service_account).values_list("key", flat=True).first()
    if not key:
        return None

    path = reverse(
        "sub-queues-token-display",
        kwargs={"sub_queue_external_ids": ",".join(str(sub_queue.external_id) for sub_queue in sub_queues)},
    )
    return f"{path}?token={key}"
