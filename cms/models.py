from functools import reduce
import re
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.shortcuts import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.text import Truncator, mark_safe, slugify

from polymorphic.models import PolymorphicManager, PolymorphicModel
from polymorphic.query import PolymorphicQuerySet


"""
Pages are ordered in a hierarchy.  Each Page exists as a child of
 either another Page, or as a top level Page.

Pages contain Blocks, which can be of many types.

Blocks can contain References, which refer to a Page or Block.
"""


class Page(models.Model):
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)

    parent = models.ForeignKey(
        'self',
        related_name='children',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    denormalised_path = models.TextField(
        help_text=(
            'Ordered slash-separated list of parent `Page`s\' slugs,'
            ' starting from the top level `Page`.  This does not'
            ' include the current `Page`.'
        ),
        editable=False,
        db_index=True,
    )
    denormalised_titles = models.TextField(
        help_text=(
            'Ordered newline-separated list of parent `Page`s\' titles,'
            ' starting from the top level `Page`.  This does not'
            ' include the current `Page`.'
        ),
        editable=False,
    )

    title = models.CharField(max_length=1024)
    slug = models.SlugField(blank=True)

    class Meta:
        unique_together = ('denormalised_path', 'slug')

    def __str__(self):
        titles = [
            title for title in self.denormalised_titles.split('\n') if title
        ]

        return ' / '.join(titles + [self.title])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._old_slug = self.slug
        self._old_parent_id = self.parent_id

        self._children_paths_redenormalisation_scheduled = False

    @property
    def _denormalised_path_parts(self):
        return [
            part for part in [self.parent.denormalised_path, self.parent.slug]
            if part
        ]

    def generate_denormalised_path(self):
        if self.parent:
            return '/'.join(self._denormalised_path_parts)

        return ''

    @property
    def _denormalised_title_parts(self):
        return [
            part for part
            in [self.parent.denormalised_titles, self.parent.title]
            if part
        ]

    def generate_denormalised_titles(self):
        if self.parent:
            return '\n'.join(self._denormalised_title_parts)

        return ''

    def _denormalise_path(self):
        # Update own `denormalised_path`
        self.denormalised_path = self.generate_denormalised_path()
        self.denormalised_titles = self.generate_denormalised_titles()

        self._children_paths_redenormalisation_scheduled = True

    def _redenormalise_children_paths(self):
        for child in self.children.all():
            child.save(redenormalise_path=True)

    def _redenormalise_children_paths_if_needed(self):
        if self._children_paths_redenormalisation_scheduled:
            self._redenormalise_children_paths()

        self._children_paths_redenormalisation_scheduled = False

    @property
    def _path_needs_redenormalising(self):
        # Do we need to initialise the denormalised path?
        if not self.denormalised_path and self.parent is not None:
            return True

        # If we've just been moved to the top level, we'll need to
        # blank `denormalised_path` and update our children anyway.
        if self.denormalised_path and self.parent is None:
            return True

        # Has our slug changed?
        if self._old_slug != self.slug:
            return True

        # Have we been adopted?
        if self._old_parent_id != self.parent_id:
            return True

        return False

    def _redenormalise_path_if_needed(self, force=False):
        if force or self._path_needs_redenormalising:
            self._denormalise_path()

    def _validate_noncyclic_hierarchy(self):
        # If we've not been adopted, short-circuit.
        if self.pk is not None and self._old_parent_id == self.parent_id:
            return

        # If we've become a root, also short-circuit.
        if self.parent is None:
            return

        parent = self.parent
        while parent is not None:
            if parent.id == self.id:
                raise ValidationError(
                    'Pages cannot be descendants of themselves.'
                )

            parent = parent.parent

    def get_absolute_url(self):
        url = 'path_page'
        kwargs = {'slug': self.slug, 'path': self.denormalised_path}
        if self.parent is None:
            url += '_root'
            kwargs.pop('path')

        return reverse(f'cms:{url}', kwargs=kwargs)

    def get_breadcrumbs(self):
        # Let's do some janky string manip to avoid thousands of
        # database queries.
        def create_crumb(path, slug, title):
            kwargs = {'slug': slug}
            if path:
                kwargs['path'] = path

            name = 'cms:path_page' if path else 'cms:path_page_root'
            return {
                'title': title,
                'url': reverse(name, kwargs=kwargs),
            }

        path = self.denormalised_path
        slug = self.slug
        title = self.title
        titles = []
        if self.denormalised_titles:
            titles = self.denormalised_titles.split('\n')

        crumbs = [create_crumb(path, slug, title)]
        while titles:
            *path, slug = path.rsplit('/', 1)
            path = path[0] if path else ''
            title = titles.pop()

            crumbs.append(create_crumb(path, slug, title))

        return crumbs

    def get_parents(self):
        if self.parent is None:
            return []

        parents = [self.parent]
        while parents[-1].parent is not None:
            parents.append(parents[-1].parent)

        return parents

    def get_sidebar_links(self):
        # TODO:  Denormalisation target.
        # Also complete gutting and rewriting target 'cause this looks
        # like pure, unrefined, ass.
        """
        Returns a nested data structure encompassing all top-level
        `Page`s, all parents of the current `Page`, all the current
        `Page`'s siblings, and all the current `Page`'s direct
        children.
        """

        def make_link(page):
            return {'title': page.title, 'url': page.get_absolute_url()}

        root_pages = Page.objects.filter(parent=None).order_by('title')
        parents = self.get_parents()
        if self.parent is not None:
            siblings = self.parent.children.all().order_by('title')
        else:
            siblings = root_pages
        children = self.children.all().order_by('title')

        # Build the tree from the leaves "upwards".
        child_links = [make_link(child) for child in children]

        sibling_links = []
        for sibling in siblings:
            sibling_links.append(make_link(sibling))
            if sibling.id == self.id and child_links:
                sibling_links[-1]['children'] = child_links

        if self.parent is None:
            return sibling_links

        def parent_reducer(parent, grandparent):
            grandparent['children'] = [parent]

            return grandparent

        parent_links = list(map(make_link, parents))
        parent_links[0]['children'] = sibling_links
        current_branch = reduce(parent_reducer, parent_links)

        links = []
        for root_page in root_pages:
            if root_page.id == parents[-1].id:
                links.append(current_branch)
            else:
                links.append(make_link(root_page))

        return links

    def get_first_position(self):
        blocks = self.blocks.order_by('position')
        if not blocks.exists():
            return 100

        if blocks.first().position == 0:
            blocks = blocks.redistribute_positions()

        return blocks.first().position // 2

    def get_position_after(self, after=None):
        if after is None:
            return self.get_first_position()

        after = self.blocks.get(id=after)
        blocks_after = self.blocks.filter(position__gte=after.position)

        if blocks_after.count() == 1:
            if blocks_after.get().position == 32767:
                # No space after; redistribute and try again.
                self.blocks.redistribute_positions()

                return self.get_position_after(after.id)

            return after.position + 100

        after, before = blocks_after[:2]

        if before.position - after.position < 2:
            # No space; redistribute and try again.
            self.blocks.redistribute_positions()

            return self.get_position_after(after.id)

        return (after.position + before.position) // 2

    def delete(self, *args, **kwargs):
        for reference in self.referees.from_unpublished():
            reference.delete()

        for reference in self.blocks.referees().from_unpublished():
            reference.delete()

        return super().delete(*args, **kwargs)

    def save(self, *args, redenormalise_path=False, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)

        self._validate_noncyclic_hierarchy()

        self._redenormalise_path_if_needed(force=redenormalise_path)

        ret = super().save(*args, **kwargs)

        self._redenormalise_children_paths_if_needed()

        return ret


class BlockQuerySet(PolymorphicQuerySet):

    def redistribute_positions(self):
        if not self.exists():
            return self

        parent_pages = set(self.values_list('parent_page', flat=True))
        if len(parent_pages) > 1:
            raise ValueError(
                'You may only redistribute blocks within one page at a'
                ' time.'
            )

        if self[0].parent_page.blocks.count() != self.count():
            raise ValueError(
                'You must redistribute all blocks from a page at once.'
            )

        space = round(32767 * 0.8)
        gap_size = space // self.count()

        position = round(32767 * 0.1)
        with transaction.atomic():
            for block in self.order_by('position'):
                block.position = position
                block.save()

                position += gap_size

        return self

    def published(self):
        return self.filter(published=True)

    def unpublished(self):
        return self.filter(published=False)

    def old_unpublished(self):
        ttl = self.model._meta.app_config.delete_unpublished_blocks_after
        best_before = timezone.now() - ttl

        return self.unpublished().filter(created__lte=best_before)

    def delete_old_unpublished(self):
        self.old_unpublished().delete()

    def referees(self):
        return Reference.objects.filter(referenced_block__in=self.values('pk'))


class CastablePolymorphicModelMixin(object):

    def cast_to(self, child_type, extra_attrs=None, extra_kwargs=None):
        extra_attrs = extra_attrs or {}
        extra_kwargs = extra_kwargs or {}

        if not issubclass(child_type, type(self)):
            raise ValidationError(
                f'{child_type.__name__} is not a subclass of'
                f'{type(self).__name__}'
            )

        field_names = (
            field.name for field in self._meta.fields
            if field.name not in ('id', 'polymorphic_ctype')
        )

        child_instance = child_type(**extra_kwargs)
        for field_name in field_names:
            setattr(child_instance, field_name, getattr(self, field_name))

        for attr_name, attr_value in extra_attrs.items():
            setattr(child_instance, attr_name, attr_value)

        setattr(
            child_instance,
            f'{type(self).__name__.lower()}_ptr_id',
            self.pk,
        )
        self.polymorphic_ctype = ContentType.objects.get(
            app_label=self._meta.app_label,
            model=self._meta.model_name,
        )

        self.save()
        child_instance.save()

        return child_instance


class Block(CastablePolymorphicModelMixin, PolymorphicModel):
    parent_page = models.ForeignKey(
        'cms.Page',
        related_name='blocks',
        on_delete=models.CASCADE,
    )
    position = models.PositiveSmallIntegerField(editable=False)
    published = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    objects = PolymorphicManager.from_queryset(BlockQuerySet)()

    class Meta:
        unique_together = ('parent_page', 'position')

    def render(self):
        raise NotImplementedError()

    def get_content(self):
        raise NotImplementedError()

    def validate_references(self, content=None):
        reference_ids = Reference.find_references(
            content or self.get_content(),
        )
        references = Reference.objects.filter(
            id__in=reference_ids,
            containing_block=self,
        )

        if references.count() != len(reference_ids):
            ids = references.values_list('id', flat=True)
            missing_ids = reference_ids.difference(ids)

            if not missing_ids:
                return

            error_message = (
                f'Reference {missing_ids} does not exist, or belong to'
                ' this block.  Please recreate it.'
            )
            error_message_plural = (
                f'References {missing_ids} do not exist, or belong to'
                ' this block.  Please recreate them.'
            )

            if len(missing_ids) == 1:
                error_message = error_message
            else:
                error_message = error_message_plural

            raise ValidationError(error_message)

    def publish(self, commit=True):
        self.validate_references()

        self.published = True

        if commit:
            self.save()

    def get_absolute_url(self):
        return f'{self.parent_page.get_absolute_url()}#{self.id}'


class TextBlock(Block):
    template_name = 'cms/blocks/textblock.html'

    content = models.TextField()

    def __str__(self):
        # If the first line is a heading, return that.
        lines = self.content.strip().split('\n')
        if lines[0].strip().startswith('#'):
            return lines[0].strip()[1:].strip()

        # Otherwise return a truncation of the block.
        return Truncator(self.content).chars(25)

    def get_content(self):
        return self.content

    def render(self):
        content = self.get_content()
        for reference in self.references.all():
            content = reference.update_references(content)

        return mark_safe(
            self._meta.app_config.markdown_parser.convert(content)
        )


class ReferenceQuerySet(models.QuerySet):

    def from_unpublished(self):
        return self.filter(containing_block__published=False)


class Reference(models.Model):
    hook = '!ref'
    generic_hook_re = re.compile(f'(?<!\\\\){hook}\\((?P<ref>\\d+)\)')

    containing_block = models.ForeignKey(
        'cms.Block',
        related_name='references',
        on_delete=models.CASCADE,
    )

    referenced_block = models.ForeignKey(
        'cms.Block',
        related_name='referees',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    referenced_page = models.ForeignKey(
        'cms.Page',
        related_name='referees',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    objects = models.Manager.from_queryset(ReferenceQuerySet)()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hook_re = re.compile(f'(?<!\\\\){self.hook}\\({self.id}\)')

    def _validate(self):
        if (self.referenced_block, self.referenced_page).count(None) != 1:
            raise ValidationError(
                '`Reference`s must refer to either a `Page` or a'
                ' `Block`.'
            )

    @property
    def hook_text(self):
        return f'{self.hook}({self.id})'

    @property
    def reference(self):
        self._validate()

        return self.referenced_block or self.referenced_page

    @property
    def referenced_title(self):
        self._validate()

        if self.referenced_block:
            return f'{self.reference.parent_page}, {self.reference}'

        return self.reference

    @cached_property
    def href(self):
        return self.reference.get_absolute_url()

    def update_references(self, content):
        return self.hook_re.sub(self.href, content)

    @classmethod
    def find_references(cls, content):
        return set(cls.generic_hook_re.findall(content))

    def save(self, *args, **kwargs):
        self._validate()

        return super().save(*args, **kwargs)


class UnsavedWorkQuerySet(models.QuerySet):

    def old(self):
        ttl = self.model._meta.app_config.delete_unsaved_work_after
        best_before = timezone.now() - ttl

        return self.filter(updated__lte=best_before)

    def delete_old_unsaved_work(self):
        return self.old().delete()


class UnsavedWork(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='unsaved_works',
        on_delete=models.CASCADE,
    )

    path = models.TextField(db_index=True)
    work = models.TextField()

    updated = models.DateTimeField(auto_now=True, db_index=True)

    objects = models.Manager.from_queryset(UnsavedWorkQuerySet)()

    class Meta:
        unique_together = ('user', 'path')

    @property
    def fresh(self):
        ttl = self._meta.app_config.delete_unsaved_work_after
        best_before = timezone.now() - ttl

        if self.updated < best_before:
            return False

        return True
