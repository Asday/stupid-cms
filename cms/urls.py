from django.urls import path

from .views import (
    AddBlockView,
    AddBlockOfTypeView,
    AddPageView,
    AddReferenceView,
    DeleteBlockView,
    DeleteReferenceView,
    EditBlockView,
    MovePageView,
    PathPageView,
    UUIDPageView,
)


app_name = 'cms'

urlpatterns = [
    path('add-page/', AddPageView.as_view(), name='add_page'),
    path('move-page/<int:pk>/', MovePageView.as_view(), name='move_page'),
    path('add-block/', AddBlockView.as_view(), name='add_block'),
    path(
        'add-block-of-type/',
        AddBlockOfTypeView.as_view(),
        name='add_block_of_type',
    ),
    path('edit-block/<int:pk>/', EditBlockView.as_view(), name='edit_block'),
    path(
        'delete-block/<int:pk>/',
        DeleteBlockView.as_view(),
        name='delete_block',
    ),
    path('add-reference/', AddReferenceView.as_view(), name='add_reference'),
    path(
        'delete-reference/<int:pk>/',
        DeleteReferenceView.as_view(),
        name='delete_reference',
    ),
    path('<uuid:uuid>/', UUIDPageView.as_view(), name='uuid_page'),
    path('<path:path>/<slug:slug>/', PathPageView.as_view(), name='path_page'),
    path('<slug:slug>/', PathPageView.as_view(), name='path_page_root'),
]
