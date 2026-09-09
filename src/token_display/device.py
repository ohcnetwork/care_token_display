from care.emr.registries.device_type.device_registry import DeviceTypeBase

from token_display.spec import (
    TokenDisplayDeviceMetadataReadSpec,
    TokenDisplayDeviceMetadataWriteSpec,
)

CARE_DEVICE_TYPE = "token_display"


class TokenDisplayDevice(DeviceTypeBase):

    @staticmethod
    def _write(request_data, obj):
        validated = TokenDisplayDeviceMetadataWriteSpec.model_validate(
            request_data,
            context={"facility": obj.facility},
        )
        obj.metadata = validated.to_metadata(obj.facility)
        obj.save(update_fields=["metadata"])
        return obj

    def handle_create(self, request_data, obj):
        return self._write(request_data, obj)

    def handle_update(self, request_data, obj):
        return self._write(request_data, obj)

    def list(self, obj):
        return {}

    def retrieve(self, obj):
        return TokenDisplayDeviceMetadataReadSpec.from_device(obj).model_dump(mode="json")
