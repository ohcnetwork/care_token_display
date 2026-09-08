from care.emr.registries.device_type.device_registry import DeviceTypeBase

from token_display.spec import (
    TokenDisplayDeviceMetadataReadSpec,
    TokenDisplayDeviceMetadataWriteSpec,
)

CARE_DEVICE_TYPE = "token_display"


class TokenDisplayDevice(DeviceTypeBase):
    """A physical/virtual screen that renders the SSR token board.

    The device's metadata *is* the preset — which sub-queues this screen shows
    and which service account authenticates its SSR page — so no extra table is
    needed. Only PKs are persisted; external ids are resolved on the way in and
    re-hydrated on the way out.
    """

    @staticmethod
    def _write(request_data, obj):
        # care_fe spreads plug metadata onto the top level of the device
        # request body (care_fe DeviceForm.tsx:189-194), it does not nest it
        # under `care_metadata`. Mirrors camera_device/device.py:20.
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
