from django.shortcuts import HttpResponse
from django.urls import path

from token_display.views import (
    SubQueuesTokenDisplayView,
    SubQueueTokenDisplayPartialView,
)


def healthy(request):
    return HttpResponse("OK")


urlpatterns = [
    path("health", healthy),
]
