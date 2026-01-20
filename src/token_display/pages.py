from django.urls import path

from token_display.views import SubQueuesTokenDisplayView

urlpatterns = [
    path(
        "sub_queues/<str:sub_queue_external_ids>/",
        SubQueuesTokenDisplayView.as_view(),
        name="sub-queues-token-display",
    ),
]
