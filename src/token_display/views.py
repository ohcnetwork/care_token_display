import re

from care.emr.models import Token, TokenSubQueue
from care.emr.resources.scheduling.token.spec import TokenStatusOptions
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueStatusOptions,
)
from care.security.authorization import AuthorizationController
from django.db.models import Exists, OuterRef
from django.utils import timezone
from django.utils.timezone import make_naive
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from token_display.authentication import QueryParamTokenAuthentication
from token_display.settings import plugin_settings
from token_display.utils import (
    fmt_schedule_resource_name,
    fmt_token_number,
)

TRUTHY_QUERY_VALUES = {"1", "true", "yes"}

# A `prefix-<lang>.wav` fragment must exist for each accepted lang code.
# Validation is purely defensive against arbitrary-string injection into the
# fragment URL; the fragment loader will surface a missing-file error if the
# operator names a lang we don't have audio for.
_VA_LANG_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


def _parse_bool_query_param(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in TRUTHY_QUERY_VALUES


def _parse_va_lang_query_param(value: str | None) -> list[str] | None:
    """Parse a comma-separated `?va_lang=` value.

    Returns ``None`` when the parameter is absent so the caller can fall back
    to the configured default. An explicit empty value (``?va_lang=``) yields
    an empty list, which suppresses voice playback. Invalid tokens are
    silently dropped.
    """
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return [p for p in parts if _VA_LANG_RE.match(p)]


class SubQueuesTokenDisplayView(APIView):
    """
    Main view that renders the full SSR token display page for a facility.
    """

    authentication_classes = [QueryParamTokenAuthentication]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "token_display/display.html"

    def get_sub_queue_objects(self, only_with_active_tokens: bool = False):
        external_ids = self.kwargs["sub_queue_external_ids"].split(",")
        sub_queues = TokenSubQueue.objects.filter(
            external_id__in=external_ids,
            status=TokenSubQueueStatusOptions.active.value,
        )
        if only_with_active_tokens:
            active_token_exists = Token.objects.filter(
                sub_queue=OuterRef("pk"),
                queue__resource=OuterRef("resource"),
                queue__date=make_naive(timezone.now()).date(),
                queue__is_primary=True,
                status__in=[
                    TokenStatusOptions.CREATED.value,
                    TokenStatusOptions.IN_PROGRESS.value,
                ],
            )
            sub_queues = sub_queues.annotate(
                _has_active_tokens=Exists(active_token_exists)
            ).filter(_has_active_tokens=True)
        order = {external_id: index for index, external_id in enumerate(external_ids)}
        return sorted(
            sub_queues, key=lambda sq: order.get(str(sq.external_id), len(order))
        )

    def authorize_request(self):
        # Authorize against the unfiltered set so permission errors are not
        # masked by the active-tokens filter.
        for sub_queue in self.get_sub_queue_objects():
            if not AuthorizationController.call(
                "can_list_token", sub_queue.resource, self.request.user
            ):
                raise PermissionDenied(
                    "You do not have permission read tokens for this resource"
                )

    def get(self, request, sub_queue_external_ids: str):
        """
        Render the full token display page with static data.
        """
        self.authorize_request()
        only_with_active_tokens = _parse_bool_query_param(
            request.query_params.get("only_with_active_tokens")
        )
        va_lang_override = _parse_va_lang_query_param(
            request.query_params.get("va_lang")
        )
        va_langs = (
            va_lang_override
            if va_lang_override is not None
            else list(plugin_settings.VA_DEFAULT_LANG or [])
        )
        sub_queues = self.get_sub_queue_objects(
            only_with_active_tokens=only_with_active_tokens
        )
        item_count = len(sub_queues)

        # Determine grid class and column spans
        if item_count == 1:
            grid_class = "grid-cols-1"
        elif item_count < 5:
            grid_class = "grid-cols-2"
        else:
            grid_class = "grid-cols-6"

        # Calculate column spans and fetch token data for each sub-queue
        sub_queues_with_data = []
        for index, sub_queue in enumerate(sub_queues):
            if item_count == 3 and index == 2:
                col_span = "col-span-2"
            elif item_count <= 4:
                col_span = "col-span-1"
            else:
                # For 6-column grid
                last_row_count = item_count % 3
                if last_row_count == 1 and index == item_count - 1:
                    col_span = "col-span-6"
                elif last_row_count == 2 and index >= item_count - 2:
                    col_span = "col-span-3"
                else:
                    col_span = "col-span-2"

            # Fetch the current token for this sub-queue
            token = (
                Token.objects.filter(
                    queue__resource=sub_queue.resource,
                    queue__date=make_naive(timezone.now()).date(),
                    queue__is_primary=True,
                    sub_queue=sub_queue,
                    status=TokenStatusOptions.IN_PROGRESS.value,
                )
                .order_by("-modified_date")
                .first()
            )

            token_code = fmt_token_number(token) if token else None
            sub_queues_with_data.append(
                {
                    "id": str(sub_queue.external_id),
                    "col_span": col_span,
                    "sub_queue_name": sub_queue.name,
                    "resource_name": fmt_schedule_resource_name(sub_queue.resource),
                    "token": token_code or "--",
                    "token_code": token_code,
                }
            )

        # When no announcement languages are configured, suppress the
        # announcer markup entirely and let the static <meta refresh>
        # fallback (rendered in the template) drive page reloads.
        announcement_payload = (
            None
            if not va_langs
            else {
                "sub_queues": [
                    {"id": entry["id"], "token_code": entry["token_code"]}
                    for entry in sub_queues_with_data
                ],
                "langs": va_langs,
                "auto_refresh_interval": plugin_settings.AUTO_REFRESH_INTERVAL,
            }
        )

        return Response(
            {
                "sub_queues": sub_queues_with_data,
                "item_count": item_count,
                "auto_refresh_interval": plugin_settings.AUTO_REFRESH_INTERVAL,
                "grid_class": grid_class,
                "only_with_active_tokens": only_with_active_tokens,
                "announcement_payload": announcement_payload,
            }
        )
