from django.urls import path

from token_display.views.device import DeviceTokenDisplayPageView
from token_display.views.sub_queues import SubQueuesTokenDisplayView

urlpatterns = [
    path(
        "sub_queues/<str:sub_queue_external_ids>/",
        SubQueuesTokenDisplayView.as_view(),
        name="sub-queues-token-display",
    ),
    path(
        "device/<uuid:device_external_id>/",
        DeviceTokenDisplayPageView.as_view(),
        name="device-token-display",
    ),
]
