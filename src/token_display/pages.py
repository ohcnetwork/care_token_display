from django.urls import path

from token_display.views import (
    SubQueuesTokenDisplayView,
    SubQueueTokenDisplayPartialView,
)

urlpatterns = [
    path(
        "sub_queues/<str:sub_queue_external_ids>/",
        SubQueuesTokenDisplayView.as_view(),
        name="sub-queues-token-display",
    ),
    path(
        "sub_queue/<uuid:sub_queue_external_id>/partial/",
        SubQueueTokenDisplayPartialView.as_view(),
        name="sub-queue-token-display-partial",
    ),
]
