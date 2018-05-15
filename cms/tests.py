from django.core.exceptions import ValidationError
from django.test import TestCase, tag

from .models import Page


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
