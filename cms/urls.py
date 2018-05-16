from django.urls import path

from .views import (
    AddBlockView,
    AddBlockOfTypeView,
    AddPageView,
    PathPageView,
    UUIDPageView,
)


app_name = 'cms'

urlpatterns = [
    path('add-page/', AddPageView.as_view(), name='add_page'),
    path('add-block/', AddBlockView.as_view(), name='add_block'),
    path(
        'add-block-of-type/',
        AddBlockOfTypeView.as_view(),
        name='add_block_of_type',
    ),
    path('<uuid:uuid>/', UUIDPageView.as_view(), name='uuid_page'),
    path('<path:path>/<slug:slug>/', PathPageView.as_view(), name='path_page'),
    path('<slug:slug>/', PathPageView.as_view(), name='path_page_root'),
]
