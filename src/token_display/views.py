from uuid import UUID

from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from care.emr.models import Token, TokenSubQueue
from care.emr.resources.scheduling.token.spec import TokenStatusOptions
from care.emr.resources.scheduling.token_sub_queue.spec import (
    TokenSubQueueStatusOptions,
)
from care.security.authorization import AuthorizationController
from care.utils.shortcuts import get_object_or_404
from care.utils.time_util import care_now
from token_display.authentication import QueryParamTokenAuthentication
from token_display.settings import plugin_settings
from token_display.utils import (
    fmt_schedule_resource_name,
    fmt_token_number,
    get_token_display_cache_key,
)


class SubQueuesTokenDisplayView(APIView):
    """
    Main view that renders the full SSR token display page for a facility.
    """

    authentication_classes = [QueryParamTokenAuthentication]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "token_display/display.html"

    def get_sub_queue_objects(self):
        external_ids = self.kwargs["sub_queue_external_ids"].split(",")
        return TokenSubQueue.objects.filter(
            external_id__in=external_ids,
            status=TokenSubQueueStatusOptions.active.value,
        )

    def authorize_request(self):
        for sub_queue in self.get_sub_queue_objects():
            if not AuthorizationController.call(
                "can_list_token", sub_queue.resource, self.request.user
            ):
                raise PermissionDenied(
                    "You do not have permission read tokens for this resource"
                )

    def get(self, request, sub_queue_external_ids: str):
        """
        Render the full token display page with HTMX setup.
        """
        self.authorize_request()
        sub_queues = self.get_sub_queue_objects()
        item_count = sub_queues.count()

        # Determine grid class and column spans
        if item_count == 1:
            grid_class = "grid-cols-1"
        elif item_count < 5:
            grid_class = "grid-cols-2"
        else:
            grid_class = "grid-cols-6"

        # Calculate column spans for each item
        sub_queues_with_spans = []
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

            sub_queues_with_spans.append(
                {
                    "id": sub_queue.external_id,
                    "col_span": col_span,
                }
            )

        return Response(
            {
                "sub_queues": sub_queues_with_spans,
                "item_count": item_count,
                "grid_class": grid_class,
                "refresh_interval": plugin_settings.TOKEN_DISPLAY_REFRESH_INTERVAL,
                "auth_token": self.request.GET.get("token"),
            }
        )


class SubQueueTokenDisplayPartialView(APIView):
    """
    Partial view that returns only the data portion for HTMX swapping.
    """

    authentication_classes = [QueryParamTokenAuthentication]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "token_display/partial.html"

    def get_sub_queue_obj(self):
        return get_object_or_404(
            TokenSubQueue,
            external_id=self.kwargs["sub_queue_external_id"],
            status=TokenSubQueueStatusOptions.active.value,
        )

    def authorize_request(self):
        resource = self.get_sub_queue_obj().resource
        if not AuthorizationController.call(
            "can_list_token", resource, self.request.user
        ):
            raise PermissionDenied(
                "You do not have permission read tokens for this resource"
            )

    def get(self, request, sub_queue_external_id: UUID):
        """
        Return the partial HTML with updated token data for a specific sub queue.
        """
        self.authorize_request()

        cache_key = get_token_display_cache_key(sub_queue_external_id)
        cached_context = cache.get(cache_key)
        if cached_context is not None:
            return Response(cached_context)

        sub_queue = self.get_sub_queue_obj()
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

        cache.set(
            cache_key,
            context,
            plugin_settings.TOKEN_DISPLAY_CACHE_TIMEOUT,
        )

        return Response(context)
