from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, DetailView

from .forms import PageForm
from .models import Page


class StaffOnlyMixin(UserPassesTestMixin):

    def test_func(self):
        return self.request.user.is_staff


class PageView(DetailView):
    model = Page
    context_object_name = 'page'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['breadcrumbs'] = self.object.get_breadcrumbs()

        return context


class PathPageView(PageView):

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            denormalised_path=self.kwargs.get('path', ''),
            slug=self.kwargs['slug'],
        )


class UUIDPageView(PageView):

    def get_object(self):
        return get_object_or_404(self.get_queryset(), uuid=self.kwargs['uuid'])

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['alter_URL'] = True

        return context


class AddPageView(StaffOnlyMixin, CreateView):
    model = Page
    form_class = PageForm

    def get_initial(self):
        initial = super().get_initial()

        initial['parent'] = self.request.GET.get('from', None)

        return initial
