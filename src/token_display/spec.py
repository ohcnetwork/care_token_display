import enum

from pydantic import BaseModel, UUID4, field_validator, Field

from care.emr.models import TokenSubQueue
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueStatusOptions,
)


class TokenDisplayDensity(enum.Enum):
    DEFAULT = "default"
    COMPACT = "compact"


class TokenDisplayAspectRatio(enum.Enum):
    WIDESCREEN = "16/9"
    ULTRAWIDE = "21/9"
    LEGACY = "4/3"
    PORTRAIT = "9/16"


class MetadataSubQueueSpec(BaseModel):
    id: UUID4
    name: str
    status: TokenSubQueueStatusOptions
    resource_type: str
    resource: dict


class TokenDisplayDeviceMetadataBaseSpec(BaseModel):
    voice_announcement_languages: list[str] = []
    sub_queues_per_page: int | None = Field(default=None, ge=1, le=100)
    density: TokenDisplayDensity = TokenDisplayDensity.DEFAULT
    aspect_ratio: TokenDisplayAspectRatio = TokenDisplayAspectRatio.WIDESCREEN
    # Seconds between polls of the device API by the SSR page. Independent
    # of any plugin-wide refresh setting so each TV can be tuned individually.
    poll_interval: int = Field(default=5, ge=1, le=300)


class TokenDisplayDeviceMetadataReadSpec(TokenDisplayDeviceMetadataBaseSpec):
    sub_queues: list[MetadataSubQueueSpec]


class TokenDisplayDeviceMetadataWriteSpec(TokenDisplayDeviceMetadataBaseSpec):
    sub_queue_ids: list[UUID4] = []

    @field_validator("sub_queue_ids", mode="before")
    @classmethod
    def validate_sub_queues(cls, value: list[UUID4]):
        resource_type = None
        for sub_queue_id in value:
            try:
                sub_queue = TokenSubQueue.objects.get(external_id=sub_queue_id)
                resource_type = resource_type or sub_queue.resource.resource_type
                if resource_type != sub_queue.resource.resource_type:
                    raise ValueError("All sub-queues must be of the same resource type")
            except TokenSubQueue.DoesNotExist:
                raise ValueError(f"Invalid sub_queue_id: {sub_queue_id}")
        return value
