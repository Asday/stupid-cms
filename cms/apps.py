import os

from django.apps import AppConfig

import markdown
from mdx_bleach.extension import BleachExtension
from mdx_bleach.whitelist import (
    ALLOWED_ATTRIBUTES as MDX_ALLOWED_ATTRIBUTES,
    ALLOWED_TAGS as MDX_ALLOWED_TAGS,
)
import tinycss


class CmsConfig(AppConfig):
    name = 'cms'
    markdown_parser = None

    def ready(self):
        self.markdown_parser = self._create_markdown_parser()

    def _create_markdown_parser(self):
        here = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(here, 'static/styles/codehilite.css')

        stylesheet = tinycss.make_parser().parse_stylesheet_file(css_path)

        codehilite_classes = set()
        for rule in stylesheet.rules:
            delim = None
            for token in rule.selector:
                if token.type == 'DELIM':
                    delim = token.value
                    continue

                if token.type == 'IDENT':
                    if delim == '.':
                        codehilite_classes.add(token.value)
                        delim = None

        def codehilite_attrs(_tag, name, value):
            if name != 'class':
                return False

            if value in codehilite_classes:
                return True

            return False

        allowed_attributes = MDX_ALLOWED_ATTRIBUTES.copy()
        allowed_attributes.update({
            'div': codehilite_attrs,
            'span': codehilite_attrs,
        })

        return markdown.Markdown(extensions=(
            BleachExtension(
                tags=MDX_ALLOWED_TAGS + ['div', 'span'],
                attributes=allowed_attributes,
            ),
            'markdown.extensions.codehilite',
            'markdown.extensions.fenced_code',
        ))
