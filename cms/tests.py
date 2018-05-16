from django.core.exceptions import ValidationError
from django.test import TestCase, tag

from .models import Page


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
    def test_root_page_with_children_sees_only_root_pages_and_own_direct_children(self):
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
    def test_leaf_page_with_cousins_sees_all_root_pages_all_parents_all_siblings_and_all_children_but_not_cousins(self):
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
        dc = Page.objects.create(title='dc', parent=coro)
        sb = Page.objects.create(title='sb', parent=coro)

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
