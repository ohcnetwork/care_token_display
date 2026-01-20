from django.utils import timezone
from django.utils.timezone import make_naive
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

from token_display.authentication import QueryParamTokenAuthentication
from token_display.utils import (
    fmt_schedule_resource_name,
    fmt_token_number,
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
        Render the full token display page with static data.
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
                .order_by("created_date")
                .first()
            )

            sub_queues_with_data.append(
                {
                    "id": sub_queue.external_id,
                    "col_span": col_span,
                    "sub_queue_name": sub_queue.name,
                    "resource_name": fmt_schedule_resource_name(sub_queue.resource),
                    "token": fmt_token_number(token) if token else "--",
                }
            )

        return Response(
            {
                "sub_queues": sub_queues_with_data,
                "item_count": item_count,
                "grid_class": grid_class,
            }
        )
