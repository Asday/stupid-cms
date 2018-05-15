from django.urls import path, re_path

from .views import PathPageView, UUIDPageView


app_name = 'cms'

urlpatterns = [
    path('<uuid:uuid>/', UUIDPageView.as_view(), name='uuid_page'),
    path('<path:path>/<slug:slug>/', PathPageView.as_view(), name='path_page'),
    path('<slug:slug>/', PathPageView.as_view(), name='path_page_root'),
]
