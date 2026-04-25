from django.urls import path

from token_display.views import SubQueuesTokenDisplayView, TokenAnnouncementView

urlpatterns = [
    path(
        "sub_queues/<str:sub_queue_external_ids>/",
        SubQueuesTokenDisplayView.as_view(),
        name="sub-queues-token-display",
    ),
    path(
        "announcement/<str:sub_queue_external_id>/<str:token_code>/",
        TokenAnnouncementView.as_view(),
        name="token-announcement",
    ),
]
