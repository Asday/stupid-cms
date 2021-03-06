import json
from urllib.parse import unquote, urlencode

from django.contrib.admin.utils import NestedObjects
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import ProtectedError
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
    View,
)

from .forms import (
    BlockTypeChoiceForm,
    MoveBlockForm,
    MovePageForm,
    PageForm,
    ReferenceForm,
    TextBlockForm,
)
from .models import Block, Page, Reference, TextBlock, UnsavedWork


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

        page_uuid = parameters.get('page', '')
        after = parameters.get('after', None)
        parent_page = get_object_or_404(Page.objects.all(), uuid=page_uuid)
        position = parent_page.get_position_after(after)

        parameters.pop('page', None)
        parameters.pop('after', None)

        block = Block.objects.create(
            parent_page=parent_page,
            position=position,
        )

        parameters['block_id'] = block.id

        return HttpResponseRedirect(
            f'{self.get_success_url()}?{parameters.urlencode()}'
        )


class UnsavedWorkMixin(object):
    alternate_submit_button_name = None
    alternate_success_url = None

    def stash_unsaved_work(self, request):
        UnsavedWork.objects.update_or_create(
            user=request.user,
            path=request.get_raw_uri(),
            defaults={'work': json.dumps(self.request.POST)},
        )

    def post(self, request, *args, **kwargs):
        if self.get_alternate_submit_button_name() in self.request.POST:
            self.stash_unsaved_work(request)

            return HttpResponseRedirect(self.get_alternate_success_url())

        return super().post(request, *args, **kwargs)

    def get_alternate_submit_button_name(self):
        if self.alternate_submit_button_name is None:
            raise ImproperlyConfigured(
                'You must specify an `alternate_submit_button_name`, or'
                ' override `.get_alternate_submit_button_name()` on'
                f' {self.__class__.__name__}.'
            )

        return self.alternate_submit_button_name

    def get_alternate_success_url(self):
        if self.alternate_success_url is None:
            raise ImproperlyConfigured(
                'You must specify a `alternate_success_url`, or'
                ' override `.get_alternate_success_url()` on'
                f' {self.__class__.__name__}.'
            )

        return self.alternate_success_url

    def get_unsaved_work(self):
        try:
            unsaved_work = UnsavedWork.objects.get(
                user=self.request.user,
                path=self.request.get_raw_uri(),
            )
        except UnsavedWork.DoesNotExist:
            return None
        else:  # noexcept
            if unsaved_work.fresh:
                return unsaved_work
            else:
                UnsavedWork.objects.delete_old_unsaved_work()

                return None

    def get_initial(self):
        initial = super().get_initial()

        unsaved_work = self.get_unsaved_work()
        if unsaved_work is not None:
            initial.update(json.loads(unsaved_work.work))

        return initial

    def form_valid(self, form):
        unsaved_work = self.get_unsaved_work()
        if unsaved_work is not None:
            unsaved_work.delete()

        return super().form_valid(form)


class GetCurrentURLMixin(object):

    def get_current_url(self):
        raw_uri = self.request.get_raw_uri()
        current_url = raw_uri[raw_uri.index(self.request.path):]

        return current_url


class AddReferenceMixin(GetCurrentURLMixin, UnsavedWorkMixin):
    alternate_submit_button_name = 'addReference'

    def get_alternate_success_url(self):
        parameters = {
            'block_id': self.get_object().id,
            'next': self.get_current_url(),
        }

        url = reverse('cms:add_reference')

        return f'{url}?{urlencode(parameters)}'


class AddReferenceView(CreateView):
    model = Reference
    form_class = ReferenceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs['containing_block'] = get_object_or_404(
            Block.objects.all(),
            id=self.request.GET.get('block_id', None),
        )

        return kwargs

    def get_success_url(self):
        return unquote(self.request.GET.get('next', ''))


class DeleteReferenceView(GetCurrentURLMixin, DeleteView):
    model = Reference
    context_object_name = 'reference'

    def get_success_url(self):
        return unquote(self.request.GET.get('next', ''))


class AddGenericBlockOfTypeBaseView(AddReferenceMixin, CreateView):

    def get_block_extra_attrs(self):
        return {}

    def get_block_extra_kwargs(self):
        return {}

    def get_object(self):
        block = get_object_or_404(
            Block.objects.all(),
            id=self.request.GET.get('block_id', ''),
        )

        if type(block) != self.model:
            block = block.cast_to(
                self.model,
                extra_attrs=self.get_block_extra_attrs(),
                extra_kwargs=self.get_block_extra_kwargs(),
            )

        return block

    def get_form_kwargs(self):
        self.object = self.get_object()

        return super().get_form_kwargs()

    def form_valid(self, form):
        form.instance.publish()

        self.model.objects.delete_old_unpublished()

        return super().form_valid(form)


class AddTextBlockView(StaffOnlyMixin, AddGenericBlockOfTypeBaseView):
    model = TextBlock
    form_class = TextBlockForm
    context_object_name = 'cms_block'


class AddBlockOfTypeView(StaffOnlyMixin, View):
    handlers = {
        'textblock': AddTextBlockView.as_view(),
    }

    def dispatch(self, request, *args, **kwargs):
        blocktype = request.GET.get('blocktype', '').lower()
        if blocktype not in self.handlers:
            return HttpResponseBadRequest('Malformed blocktype')

        return self.handlers[blocktype](request, *args, **kwargs)


class PolymorphicTemplateNameOverrideMixin(object):

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


class DeleteBlockView(
        StaffOnlyMixin,
        PolymorphicTemplateNameOverrideMixin,
        DeleteView,
        ):
    model = Block
    context_object_name = 'cms_block'

    def get_success_url(self):
        return self.object.parent_page.get_absolute_url()


class EditBlockView(AddReferenceMixin, StaffOnlyMixin, UpdateView):
    model = Block
    form_classes = {
        TextBlock: TextBlockForm,
    }
    template_name_suffix = '_edit_form'
    context_object_name = 'cms_block'

    def get_form_class(self):
        return self.form_classes[type(self.object)]


class AddPageView(StaffOnlyMixin, CreateView):
    model = Page
    form_class = PageForm

    def get_initial(self):
        initial = super().get_initial()

        initial['parent'] = self.request.GET.get('from', None)

        return initial


class MovePageView(StaffOnlyMixin, UpdateView):
    model = Page
    form_class = MovePageForm
    template_name_suffix = '_move_form'


class MoveBlockView(
        StaffOnlyMixin,
        PolymorphicTemplateNameOverrideMixin,
        UpdateView,
        ):
    model = Block
    form_class = MoveBlockForm
    template_name_suffix = '_move_form'


class DeletePageView(StaffOnlyMixin, DeleteView):
    model = Page
    context_object_name = 'page'
    protected_objects = None

    def delete(self, request, *args, **kwargs):
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError as e:
            self.protected_objects = e.protected_objects

            return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['protected_objects'] = self.protected_objects

        collector = NestedObjects(using='default')
        collector.collect([self.object])
        to_be_deleted = collector.nested()

        def remove_unpublished(tree):
            filtered_tree = []
            for item in tree:
                if type(item) == list:
                    filtered_tree.append(remove_unpublished(item))

                elif type(item) == Page:
                    filtered_tree.append(item)

                elif issubclass(type(item), Block) and type(item) != Block:
                    if item.published:
                        filtered_tree.append(item)

                elif type(item) == Reference:
                    if item.containing_block.published:
                        filtered_tree.append(item)

            return filtered_tree

        context['to_be_deleted'] = remove_unpublished(to_be_deleted)

        return context

    def get_success_url(self):
        if self.object.parent:
            return self.object.parent.get_absolute_url()

        else:
            return '/'


class HomeView(ListView):
    queryset = Page.objects.filter(parent=None)
    context_object_name = 'pages'
