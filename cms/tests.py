from django.core.exceptions import ValidationError
from django.test import TestCase, tag

from .models import Block, Page, Reference, TextBlock


class PolymorphicCasting(TestCase):

    def test_casting_to_child_type(self):
        page = Page.objects.create(title='A')
        block = Block.objects.create(parent_page=page, position=0)

        text_block = block.cast_to(TextBlock)  # noqa

        cast_block = Block.objects.get(id=text_block.id)
        self.assertEqual(type(cast_block), TextBlock)

        self.assertEqual(TextBlock.objects.get(id=block.id), text_block)


class ReferenceCreation(TestCase):

    def setUp(self):
        self.a = Page.objects.create(title='A')
        self.b = Page.objects.create(title='B')

        self.b_block = Block.objects.create(parent_page=self.b, position=0)

    @tag('story')
    def test_referenced_page_being_deleted_prevents_publishing_of_block_with_references_to_it_and_its_blocks(self):  # noqa
        # Barret creates a block.
        block = TextBlock.objects.create(parent_page=self.a, position=9)

        # Barret references page B within his block.
        page_reference = Reference.objects.create(
            containing_block=block,
            referenced_page=self.b,
        )
        page_reference_id = page_reference.id
        block.content += f'{Reference.hook}({page_reference_id})\n\n'

        # Barret also references a block on page B within his block.
        block_reference = Reference.objects.create(
            containing_block=block,
            referenced_block=self.b_block,
        )
        block_reference_id = block_reference.id
        block.content += f'{Reference.hook}({block_reference_id})\n\n'

        # Aeris deletes page B without issue.
        self.b.delete()  # Should not raise.

        # In doing so, Aeris has also deleted the reference Barret just
        # created.
        references = (page_reference_id, block_reference_id)
        self.assertEqual(
            Reference.objects.filter(id__in=references).exists(),
            False,
        )

        # Barret attempts to save his block and receives a
        # `ValidationError`.
        with self.assertRaises(ValidationError):
            block.validate_references()


class BlockRedistribution(TestCase):

    def setUp(self):
        self.page = Page.objects.create(title='A')

        self.blocks = {
            'c': Block.objects.create(parent_page=self.page, position=2),
            'b': Block.objects.create(parent_page=self.page, position=1),
            'a': Block.objects.create(parent_page=self.page, position=0),
        }

    @tag('functional')
    def test_redistribute_positions_creates_space_at_the_beginning(self):
        blocks = self.page.blocks.redistribute_positions()

        self.assertGreater(blocks[0].position, 0)
        self.assertGreater(blocks[1].position, 0)
        self.assertGreater(blocks[2].position, 0)

    @tag('functional')
    def test_redistribute_positions_creates_space_between_blocks(self):
        blocks = self.page.blocks.redistribute_positions().order_by('position')

        self.assertGreater(blocks[1].position - blocks[0].position, 1)
        self.assertGreater(blocks[2].position - blocks[1].position, 1)

    @tag('functional')
    def test_redistribute_positions_errors_if_used_on_blocks_from_more_than_one_page(self):  # noqa
        other_page = Page.objects.create(title='B')
        Block.objects.create(parent_page=other_page, position=0)

        with self.assertRaises(ValueError):
            Block.objects.redistribute_positions()

    @tag('functional')
    def test_redistribute_positions_errors_if_not_used_on_all_blocks_from_a_page(self):  # noqa
        blocks = Block.objects.filter(position__gt=0)

        with self.assertRaises(ValueError):
            blocks.redistribute_positions()


class PositionGeneration(TestCase):

    def setUp(self):
        self.page = Page.objects.create(title='A')

    @tag('functional')
    def test_position_with_space_before_it_is_generated_when_no_blocks_exist(self):  # noqa
        self.assertGreater(self.page.get_position_after(), 0)

    @tag('functional')
    def test_position_lower_than_all_others_is_generated_when_after_is_none(self):  # noqa
        Block.objects.create(parent_page=self.page, position=1)

        self.assertEqual(self.page.get_position_after(), 0)

    @tag('functional')
    def test_position_lower_than_all_others_is_generated_when_after_is_none_and_no_space_is_available(self):  # noqa
        block = Block.objects.create(parent_page=self.page, position=0)

        new_position = self.page.get_position_after()
        block.refresh_from_db()

        self.assertLess(new_position, block.position)

    @tag('functional')
    def test_position_is_correctly_generated_between_blocks(self):
        first = Block.objects.create(parent_page=self.page, position=0)
        Block.objects.create(parent_page=self.page, position=2)

        self.assertEqual(self.page.get_position_after(first.id), 1)

    @tag('functional')
    def test_position_is_correctly_generated_between_blocks_with_no_space(self):  # noqa
        first = Block.objects.create(parent_page=self.page, position=0)
        second = Block.objects.create(parent_page=self.page, position=1)

        new_position = self.page.get_position_after(first.id)
        first.refresh_from_db()
        second.refresh_from_db()

        self.assertGreater(new_position, first.position)
        self.assertLess(new_position, second.position)

    @tag('functional')
    def test_position_is_correctly_generated_after_last_block(self):
        block = Block.objects.create(parent_page=self.page, position=0)

        self.assertGreater(self.page.get_position_after(block.id), 0)

    @tag('functional')
    def test_position_is_correctly_generated_after_last_block_with_high_position(self):  # noqa
        block = Block.objects.create(parent_page=self.page, position=32767)

        new_position = self.page.get_position_after(block.id)
        block.refresh_from_db()

        self.assertGreater(new_position, block.position)
        self.assertLessEqual(new_position, 32767)


class SidebarLinkGeneration(TestCase):

    def setUp(self):
        """
        A
        |
        +- B
        |  |
        |  +- C
        |  |  |
        |  |  +- D
        |  |  |
        |  |  +- E
        |  |
        |  +- F
        |  |
        |  +- G
        |     |
        |     +- H
        |
        +- I

        J
        """

        pages = {}

        pages['A'] = Page.objects.create(title='A')
        pages['B'] = Page.objects.create(title='B', parent=pages['A'])
        pages['C'] = Page.objects.create(title='C', parent=pages['B'])
        pages['D'] = Page.objects.create(title='D', parent=pages['C'])
        pages['E'] = Page.objects.create(title='E', parent=pages['C'])
        pages['F'] = Page.objects.create(title='F', parent=pages['B'])
        pages['G'] = Page.objects.create(title='G', parent=pages['B'])
        pages['H'] = Page.objects.create(title='H', parent=pages['G'])
        pages['I'] = Page.objects.create(title='I', parent=pages['A'])
        pages['J'] = Page.objects.create(title='J')

        self.pages = pages

    @tag('functional')
    def test_root_page_with_no_children_sees_only_root_pages_in_sidebar(self):
        self.assertEqual(
            self.pages['J'].get_sidebar_links(),
            [
                {'title': 'A', 'url': '/a/'},
                {'title': 'J', 'url': '/j/'},
            ],
        )

    @tag('functional')
    def test_root_page_with_children_sees_only_root_pages_and_own_direct_children(self):  # noqa
        self.assertEqual(
            self.pages['A'].get_sidebar_links(),
            [
                {
                    'title': 'A',
                    'url': '/a/',
                    'children': [
                        {'title': 'B', 'url': '/a/b/'},
                        {'title': 'I', 'url': '/a/i/'},
                    ],
                },
                {'title': 'J', 'url': '/j/'},
            ],
        )

    @tag('functional')
    def test_leaf_page_with_cousins_sees_all_root_pages_all_parents_all_siblings_and_all_children_but_not_cousins(self):  # noqa
        # I hate tests.
        self.maxDiff = 1122
        self.assertEqual(
            self.pages['C'].get_sidebar_links(),
            [
                {
                    'title': 'A',
                    'url': '/a/',
                    'children': [
                        {
                            'title': 'B',
                            'url': '/a/b/',
                            'children': [
                                {
                                    'title': 'C',
                                    'url': '/a/b/c/',
                                    'children': [
                                        {'title': 'D', 'url': '/a/b/c/d/'},
                                        {'title': 'E', 'url': '/a/b/c/e/'},
                                    ],
                                },
                                {'title': 'F', 'url': '/a/b/f/'},
                                {'title': 'G', 'url': '/a/b/g/'},
                            ],
                        },
                    ],
                },
                {'title': 'J', 'url': '/j/'},
            ],
        )

    @tag('functional', 'regression')
    def test_second_level_page_sees_below_root_level(self):
        # Clear out setUp'd instances.  We're reproducing something!
        for page in Page.objects.all().order_by('-pk'):
            page.delete()

        ro = Page.objects.create(title='ro')
        coro = Page.objects.create(title='coro', parent=ro)
        Page.objects.create(title='dc', parent=coro)
        Page.objects.create(title='sb', parent=coro)

        self.assertEqual(
            coro.get_sidebar_links(),
            [
                {
                    'title': 'ro',
                    'url': '/ro/',
                    'children': [
                        {
                            'title': 'coro',
                            'url': '/ro/coro/',
                            'children': [
                                {'title': 'dc', 'url': '/ro/coro/dc/'},
                                {'title': 'sb', 'url': '/ro/coro/sb/'},
                            ],
                        },
                    ],
                },
            ],
        )


class PathDenormalisationTestCase(TestCase):

    def setUp(self):
        """
        A
        |
        +- B
           |
           + C
           |
           + D

        E
        """

        pages = {}

        pages['A'] = Page.objects.create(title='A')
        pages['B'] = Page.objects.create(title='B', parent=pages['A'])
        pages['C'] = Page.objects.create(title='C', parent=pages['B'])
        pages['D'] = Page.objects.create(title='D', parent=pages['B'])
        pages['E'] = Page.objects.create(title='E')

        self.pages = pages

    @tag('functional')
    def test_newly_created_root_page_has_correct_path(self):
        page = Page.objects.create(title='1')

        self.assertEqual(page.denormalised_path, '')

    @tag('functional')
    def test_newly_created_leaf_page_has_correct_path(self):
        page = Page.objects.create(title='1', parent=self.pages['E'])

        self.assertEqual(page.denormalised_path, 'e')

    @tag('functional')
    def test_newly_created_deep_leaf_page_has_correct_path(self):
        page = Page.objects.create(title='1', parent=self.pages['C'])

        self.assertEqual(page.denormalised_path, 'a/b/c')

    @tag('functional')
    def test_root_page_has_correct_path_after_becoming_a_leaf(self):
        self.pages['E'].parent = self.pages['A']
        self.pages['E'].save()

        self.assertEqual(self.pages['E'].denormalised_path, 'a')

    @tag('functional')
    def test_root_page_has_correct_path_after_becoming_a_deep_leaf(self):
        self.pages['E'].parent = self.pages['C']
        self.pages['E'].save()

        self.assertEqual(self.pages['E'].denormalised_path, 'a/b/c')

    @tag('functional')
    def test_child_pages_have_correct_paths_after_parent_moves_under_a_different_page(self):  # noqa
        self.pages['B'].parent = self.pages['E']
        self.pages['B'].save()

        self.pages['C'].refresh_from_db()
        self.pages['D'].refresh_from_db()

        self.assertEqual(self.pages['C'].denormalised_path, 'e/b')
        self.assertEqual(self.pages['D'].denormalised_path, 'e/b')

    @tag('functional')
    def test_child_pages_have_correct_paths_after_parent_moves_to_root(self):
        self.pages['B'].parent = None
        self.pages['B'].save()

        self.pages['C'].refresh_from_db()
        self.pages['D'].refresh_from_db()

        self.assertEqual(self.pages['C'].denormalised_path, 'b')
        self.assertEqual(self.pages['D'].denormalised_path, 'b')

    @tag('functional')
    def test_page_cannot_become_a_child_of_itself(self):
        self.pages['A'].parent = self.pages['A']

        with self.assertRaises(ValidationError):
            self.pages['A'].save()

    @tag('functional')
    def test_page_cannot_become_a_descendant_of_itself(self):
        self.pages['A'].parent = self.pages['B']

        with self.assertRaises(ValidationError):
            self.pages['A'].save()

    @tag('functional')
    def test_breadcrumb_generation_of_root_page(self):
        self.assertEqual(
            self.pages['A'].get_breadcrumbs(),
            [{'title': 'A', 'url': '/a/'}],
        )

    @tag('functional')
    def test_breadcrumb_generation_of_deep_leaf(self):
        self.assertEqual(
            self.pages['C'].get_breadcrumbs(),
            [
                {'title': 'C', 'url': '/a/b/c/'},
                {'title': 'B', 'url': '/a/b/'},
                {'title': 'A', 'url': '/a/'},
            ],
        )
