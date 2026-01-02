from uuid import UUID

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View

from care.emr.models import Token, TokenSubQueue
from care.emr.resources.scheduling.token.spec import TokenStatusOptions
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueStatusOptions,
)
from care.utils.shortcuts import get_object_or_404
from care.utils.time_util import care_now
from token_display.settings import plugin_settings
from token_display.utils import (
    fmt_schedule_resource_name,
    fmt_token_number,
    get_token_display_cache_key,
)


def authenticate_request(request: HttpRequest) -> bool:
    from rest_framework.authtoken.models import Token as AuthToken

    get_object_or_404(AuthToken, key=request.GET.get("token"))


class SubQueuesTokenDisplayView(View):
    """
    Main view that renders the full SSR token display page for a facility.
    """

    def get(self, request: HttpRequest, sub_queue_external_ids: str) -> HttpResponse:
        """
        Render the full token display page with HTMX setup.
        """
        authenticate_request(request)
        sub_queues = TokenSubQueue.objects.filter(
            external_id__in=sub_queue_external_ids.split(","),
            status=TokenSubQueueStatusOptions.active.value,
        ).values_list("external_id", flat=True)
        item_count = len(sub_queues)

        # Determine grid class and column spans
        if item_count == 1:
            grid_class = "grid-cols-1"
        elif item_count < 5:
            grid_class = "grid-cols-2"
        else:
            grid_class = "grid-cols-6"

        # Calculate column spans for each item
        sub_queues_with_spans = []
        for index, sub_queue_id in enumerate(sub_queues):
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

            sub_queues_with_spans.append(
                {
                    "id": sub_queue_id,
                    "col_span": col_span,
                }
            )

        context = {
            "sub_queues": sub_queues_with_spans,
            "item_count": item_count,
            "grid_class": grid_class,
            "refresh_interval": plugin_settings.TOKEN_DISPLAY_REFRESH_INTERVAL,
            "auth_token": request.GET.get("token"),
        }
        return render(request, "token_display/display.html", context)


class SubQueueTokenDisplayPartialView(View):
    """
    Partial view that returns only the data portion for HTMX swapping.
    """

    def get(
        self,
        request: HttpRequest,
        sub_queue_external_id: UUID,
    ) -> HttpResponse:
        """
        Return the partial HTML with updated token data for a specific sub queue.
        """
        authenticate_request(request)
        cache_key = get_token_display_cache_key(sub_queue_external_id)
        cached_html = cache.get(cache_key)
        if cached_html is not None:
            return HttpResponse(cached_html)

        sub_queue = get_object_or_404(
            TokenSubQueue,
            external_id=sub_queue_external_id,
            status=TokenSubQueueStatusOptions.active.value,
        )
        token = (
            Token.objects.filter(
                queue__resource=sub_queue.resource,
                queue__date=care_now().date(),
                queue__is_primary=True,
                sub_queue=sub_queue,
                status=TokenStatusOptions.IN_PROGRESS.value,
            )
            .order_by("created_date")
            .first()
        )
        context = {
            "sub_queue_name": sub_queue.name,
            "resource_name": fmt_schedule_resource_name(sub_queue.resource),
            "token": fmt_token_number(token) if token else "--",
            "refresh_interval": plugin_settings.TOKEN_DISPLAY_REFRESH_INTERVAL,
        }

        rendered_html = render(request, "token_display/partial.html", context)
        cache.set(
            cache_key,
            rendered_html.content.decode("utf-8"),
            plugin_settings.TOKEN_DISPLAY_CACHE_TIMEOUT,
        )

        return rendered_html
