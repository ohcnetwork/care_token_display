from django.shortcuts import HttpResponse
from django.urls import path


def healthy(request):
    return HttpResponse("OK")


urlpatterns = [
    path("health", healthy),
]
