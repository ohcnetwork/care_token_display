import re

from care.emr.api.viewsets.base import EMRBaseViewSet, EMRListMixin
from care.emr.models import Device, Token, TokenSubQueue
from care.emr.resources.scheduling.token.spec import TokenStatusOptions
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueStatusOptions,
)
from care.security.authorization import AuthorizationController
from care.utils.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_naive
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from token_display.authentication import QueryParamTokenAuthentication
from token_display.spec import (
    TokenDisplayAspectRatio,
    TokenDisplayDensity,
    TokenDisplayDeviceMetadataBaseSpec,
)
from token_display.utils import fmt_schedule_resource_name, fmt_token_number

# A `prefix-<lang>.wav` fragment must exist for each accepted lang code.
# Defensive against arbitrary-string injection into the fragment URL.
_VA_LANG_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")

# device_type registered in apps.py — keep in sync.
TOKEN_DISPLAY_DEVICE_TYPE = "token-display"


def _device_metadata_value(metadata: dict, key: str, default):
    """Read a value from device.metadata, falling back to ``default`` for
    legacy device entries that pre-date a given metadata field."""
    value = metadata.get(key)
    return value if value is not None else default


class DeviceTokenDisplayViewSet(EMRBaseViewSet, EMRListMixin):
    """
    Read-only list endpoint that returns the per-row payload a token-display
    device should render. Keyed by the device's ``external_id`` and driven
    entirely from the device's stored ``metadata``.

    URL: ``/api/token_display/device/<device_external_id>/``
    """

    database_model = TokenSubQueue
    authentication_classes = [QueryParamTokenAuthentication]
    pagination_class = None

    def get_device(self) -> Device:
        device = get_object_or_404(
            Device.objects.all(),
            external_id=self.kwargs["device_external_id"],
            care_type=TOKEN_DISPLAY_DEVICE_TYPE,
        )
        return device

    def get_sub_queues(self, device: Device):
        sub_queue_ids = device.metadata.get("sub_queue_ids", []) or []
        if not sub_queue_ids:
            return []
        sub_queues = TokenSubQueue.objects.filter(
            external_id__in=sub_queue_ids,
            status=TokenSubQueueStatusOptions.active.value,
        )
        order = {str(eid): index for index, eid in enumerate(sub_queue_ids)}
        return sorted(
            sub_queues, key=lambda sq: order.get(str(sq.external_id), len(order))
        )

    def authorize_list(self, sub_queues):
        for sub_queue in sub_queues:
            if not AuthorizationController.call(
                "can_list_token", sub_queue.resource, self.request.user
            ):
                raise PermissionDenied(
                    "You do not have permission read tokens for this resource"
                )

    def serialize_row(self, sub_queue: TokenSubQueue) -> dict:
        today = make_naive(timezone.now()).date()
        token = (
            Token.objects.filter(
                queue__resource=sub_queue.resource,
                queue__date=today,
                queue__is_primary=True,
                sub_queue=sub_queue,
                status=TokenStatusOptions.IN_PROGRESS.value,
            )
            .order_by("-modified_date")
            .first()
        )
        token_code = fmt_token_number(token) if token else None

        upcoming_tokens_qs = Token.objects.filter(
            queue__resource=sub_queue.resource,
            queue__date=today,
            queue__is_primary=True,
            sub_queue=sub_queue,
            status=TokenStatusOptions.CREATED.value,
        ).order_by("created_date")[:2]
        upcoming_tokens = [fmt_token_number(t) for t in upcoming_tokens_qs]

        return {
            "id": str(sub_queue.external_id),
            "sub_queue_name": sub_queue.name,
            "resource_name": fmt_schedule_resource_name(sub_queue.resource),
            "token_code": token_code,
            "upcoming_tokens": upcoming_tokens,
        }

    def device_config(self, device: Device) -> dict:
        metadata = device.metadata or {}
        # Sanitize lang codes; clients use these directly as URL path
        # segments when fetching audio fragments, so don't trust raw
        # operator-supplied metadata.
        raw_langs = metadata.get("voice_announcement_languages") or []
        langs = [lang for lang in raw_langs if _VA_LANG_RE.match(str(lang))]
        poll_interval_default = (
            TokenDisplayDeviceMetadataBaseSpec.model_fields["poll_interval"].default
        )
        return {
            "density": _device_metadata_value(
                metadata, "density", TokenDisplayDensity.DEFAULT.value
            ),
            "aspect_ratio": _device_metadata_value(
                metadata, "aspect_ratio", TokenDisplayAspectRatio.WIDESCREEN.value
            ),
            "poll_interval": _device_metadata_value(
                metadata, "poll_interval", poll_interval_default
            ),
            "voice_announcement_languages": langs,
        }

    def list(self, request, *args, **kwargs):
        device = self.get_device()
        sub_queues = self.get_sub_queues(device)
        self.authorize_list(sub_queues)
        rows = [self.serialize_row(sq) for sq in sub_queues]
        return Response(
            {
                "device": self.device_config(device),
                "rows": rows,
            }
        )


class DeviceTokenDisplayPageView(APIView):
    """
    Server-renders the airport-departure shell for a token-display device.

    The page itself is a thin client: it shows a loading state, then polls
    ``/api/token_display/device/<device_id>/`` every
    ``device.metadata.poll_interval`` seconds to render every configured
    sub-queue (no pagination — all sub-queues share the canvas). The voice
    announcer runs after each successful poll using audio fragments
    preloaded at boot.
    """

    authentication_classes = [QueryParamTokenAuthentication]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "token_display/device.html"

    def get(self, request, device_external_id):
        # Validate the device + user up-front so the shell can return a
        # proper 403/404 HTML response instead of letting the polling JS
        # render an empty frame on top of an inaccessible device.
        api = DeviceTokenDisplayViewSet()
        api.kwargs = {"device_external_id": device_external_id}
        api.request = request
        device = api.get_device()
        api.authorize_list(api.get_sub_queues(device))

        return Response(
            {
                "device_id": str(device_external_id),
                "token": request.query_params.get("token") or "",
                "device": api.device_config(device),
            }
        )
