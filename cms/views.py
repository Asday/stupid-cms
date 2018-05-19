from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    View,
)

from .forms import BlockTypeChoiceForm, PageForm, TextBlockForm
from .models import Block, Page, TextBlock


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


class AddBlockView(StaffOnlyMixin, FormView):
    form_class = BlockTypeChoiceForm
    template_name = 'cms/block_form.html'
    success_url = reverse_lazy('cms:add_block_of_type')

    def form_valid(self, form):
        parameters = self.request.GET.copy()
        parameters['blocktype'] = form.cleaned_data['blocktype']

        return HttpResponseRedirect(
            f'{self.get_success_url()}?{parameters.urlencode()}'
        )


class AddGenericBlockOfTypeBaseView(CreateView):

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        parent_page = get_object_or_404(
            Page.objects.all(),
            uuid=self.request.GET.get('page', '')
        )

        position = parent_page.get_position_after(
            self.request.GET.get('after')
        )

        kwargs.update({
            'parent_page': parent_page,
            'position': position,
        })

        return kwargs


class AddTextBlockView(StaffOnlyMixin, AddGenericBlockOfTypeBaseView):
    model = TextBlock
    form_class = TextBlockForm


class AddBlockOfTypeView(StaffOnlyMixin, View):
    handlers = {
        'textblock': AddTextBlockView.as_view(),
    }

    def dispatch(self, request, *args, **kwargs):
        blocktype = request.GET.get('blocktype', '').lower()
        if blocktype not in self.handlers:
            return HttpResponseBadRequest('Malformed blocktype')

        return self.handlers[blocktype](request, *args, **kwargs)


class DeleteBlockView(StaffOnlyMixin, DeleteView):
    model = Block
    context_object_name = 'cms_block'

    def get_template_names(self):
        # The default implementation is a little too clever here, as
        # we're using `PolymorphicModel`s, it detects the model's name
        # as the most specific option.  In our case, we want the most
        # generic, so only one template is needed.
        #
        # There are several options here; explicitly set
        # `self.template_name`, which is nice and simple, but locks us
        # in to being blocks should we want to reuse later.  We could
        # reimplement the default implementation, but change one line
        # to account for the polymorphism of our models, but future
        # improvements to the function would need to be copied over.
        # Temporarily patching the model name seems the least
        # subversive way to do things, whilst still being subversive
        # enough to be fun.

        old_model_name = self.object._meta.model_name
        self.object._meta.model_name = self.model._meta.model_name

        template_names = super().get_template_names()

        self.object._meta.model_name = old_model_name

        return template_names

    def get_success_url(self):
        return self.object.parent_page.get_absolute_url()


class AddPageView(StaffOnlyMixin, CreateView):
    model = Page
    form_class = PageForm

    def get_initial(self):
        initial = super().get_initial()

        initial['parent'] = self.request.GET.get('from', None)

        return initial
