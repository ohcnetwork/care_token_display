from pydantic import UUID4, BaseModel, ValidationInfo, field_validator

from care.emr.models import Device, TokenSubQueue
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueReadSpec,
)
from care.emr.resources.user.spec import UserSpec
from care.users.models import User


class TokenDisplayDeviceMetadataWriteSpec(BaseModel):
    sub_queues: list[UUID4] = []
    service_account: UUID4 | None = None

    @staticmethod
    def _facility(info: ValidationInfo):
        facility = (info.context or {}).get("facility")
        if facility is None:
            raise ValueError("facility context is required to validate token display metadata")
        return facility

    @field_validator("sub_queues")
    @classmethod
    def validate_sub_queues(cls, value, info: ValidationInfo):
        if not value:
            return value
        if len(set(value)) != len(value):
            raise ValueError("Duplicate sub queues are not allowed")

        facility = cls._facility(info)
        found = {
            str(external_id): pk
            for external_id, pk in TokenSubQueue.objects.filter(
                external_id__in=value,
                facility=facility,
            ).values_list("external_id", "id")
        }
        missing = [str(external_id) for external_id in value if str(external_id) not in found]
        if missing:
            raise ValueError("Active sub queues not found in this facility: " + ", ".join(missing))
        return value

    @field_validator("service_account")
    @classmethod
    def validate_service_account(cls, value, info: ValidationInfo):
        if value is None:
            return value
        if not User.objects.filter(external_id=value, is_service_account=True).exists():
            raise ValueError("Service account does not exist")
        return value

    def to_metadata(self, facility) -> dict:
        sub_queue_ids_by_external_id = {
            str(external_id): pk
            for external_id, pk in TokenSubQueue.objects.filter(
                external_id__in=self.sub_queues, facility=facility
            ).values_list("external_id", "id")
        }
        return {
            # Order is meaningful: it is the column order on the display board.
            "sub_queue_ids": [sub_queue_ids_by_external_id[str(external_id)] for external_id in self.sub_queues],
            "service_account_id": (
                User.objects.filter(external_id=self.service_account).values_list("id", flat=True).first()
                if self.service_account
                else None
            ),
        }


class TokenDisplayDeviceMetadataReadSpec(BaseModel):
    sub_queues: list[dict] = []
    service_account: dict | None = None
    display_path: str | None = None

    @classmethod
    def from_device(cls, obj: Device) -> "TokenDisplayDeviceMetadataReadSpec":
        from token_display.utils import build_display_path

        metadata = obj.metadata or {}

        sub_queue_ids = metadata.get("sub_queue_ids") or []
        sub_queues_by_id = {sub_queue.id: sub_queue for sub_queue in TokenSubQueue.objects.filter(id__in=sub_queue_ids)}
        # Preserve configured order; drop any sub-queue deleted out from under us.
        sub_queues = [sub_queues_by_id[pk] for pk in sub_queue_ids if pk in sub_queues_by_id]

        service_account = User.objects.filter(id=metadata.get("service_account_id")).first()

        return cls(
            sub_queues=[TokenSubQueueReadSpec.serialize(sub_queue).to_json() for sub_queue in sub_queues],
            service_account=(UserSpec.serialize(service_account).to_json() if service_account else None),
            display_path=build_display_path(sub_queues, service_account),
        )
