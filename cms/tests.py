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
