from care.emr.models import TokenSubQueue
from care.emr.registries.device_type.device_registry import DeviceTypeBase
from care.emr.resources.scheduling.resource.spec import serialize_resource
from token_display.spec import TokenDisplayDeviceMetadataWriteSpec, MetadataSubQueueSpec, \
    TokenDisplayDeviceMetadataReadSpec


class TokenDisplayDevice(DeviceTypeBase):
    @classmethod
    def get_sub_queues(cls, obj):
        sub_queues = []
        for sub_queue_id in obj.metadata["sub_queue_ids"]:
            try:
                instance = TokenSubQueue.objects.get(external_id=sub_queue_id)
                sub_queues.append(
                    MetadataSubQueueSpec(
                        id=str(instance.external_id),
                        name=instance.name,
                        status=instance.status,
                        resource_type=instance.resource.resource_type,
                        resource=serialize_resource(instance.resource)
                    )
                )
            except TokenSubQueue.DoesNotExist:
                pass
        return sub_queues

    def handle_create(self, request_data, obj):
        validated_data = TokenDisplayDeviceMetadataWriteSpec(**request_data)
        obj.metadata = validated_data.model_dump(mode="json")
        obj.save(update_fields=["metadata"])
        return obj

    def handle_update(self, request_data, obj):
        validated_data = TokenDisplayDeviceMetadataWriteSpec(**request_data)
        obj.metadata = validated_data.model_dump(mode="json")
        obj.save(update_fields=["metadata"])
        return obj

    def list(self, obj):
        return self.retrieve(obj)

    def retrieve(self, obj):
        metadata = obj.metadata
        metadata["sub_queues"] = self.get_sub_queues(obj)
        return TokenDisplayDeviceMetadataReadSpec(**metadata).model_dump(mode="json")

    def perform_action(self, obj, action, request):
        raise NotImplementedError("Actions are not supported for this device type.")
