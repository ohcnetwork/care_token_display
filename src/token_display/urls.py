from django.shortcuts import HttpResponse
from django.urls import path

from token_display.views.device import DeviceTokenDisplayViewSet


def healthy(request):
    return HttpResponse("OK")


urlpatterns = [
    path("health", healthy),
    path(
        "device/<uuid:device_external_id>/",
        DeviceTokenDisplayViewSet.as_view({"get": "list"}),
        name="device-token-display-api",
    ),
]
