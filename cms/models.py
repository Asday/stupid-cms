from functools import reduce
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.shortcuts import reverse
from django.utils.text import slugify

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
        return f'Page "{self.title}"'

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


class Block(PolymorphicModel):
    parent_page = models.ForeignKey(
        'cms.Page',
        related_name='blocks',
        on_delete=models.CASCADE,
    )
    position = models.PositiveSmallIntegerField(editable=False)

    objects = PolymorphicManager.from_queryset(BlockQuerySet)()

    class Meta:
        unique_together = ('parent_page', 'position')

    def get_absolute_url(self):
        return f'{self.parent_page.get_absolute_url()}#{self.id}'


class TextBlock(Block):
    template_name = 'cms/blocks/textblock.html'

    content = models.TextField()


class Reference(models.Model):
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

    def save(self, *args, **kwargs):
        if self.referenced_block is None and self.referenced_page is None:
            raise ValidationError(
                '`Reference`s must refer to either a `Page` or a'
                ' `Block`.'
            )

        return super().save(*args, **kwargs)
