from django.urls import path, re_path

from .views import PathPageView, UUIDPageView


urlpatterns = [
    path('<uuid:uuid>/', UUIDPageView.as_view()),
    path('<path:path>/<slug:slug>/', PathPageView.as_view()),
    path('<slug:slug>/', PathPageView.as_view()),
]
