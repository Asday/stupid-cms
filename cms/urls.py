from django.urls import path

from .views import AddPageView, PathPageView, UUIDPageView


app_name = 'cms'

urlpatterns = [
    path('add-page/', AddPageView.as_view(), name='add_page'),
    path('<uuid:uuid>/', UUIDPageView.as_view(), name='uuid_page'),
    path('<path:path>/<slug:slug>/', PathPageView.as_view(), name='path_page'),
    path('<slug:slug>/', PathPageView.as_view(), name='path_page_root'),
]
