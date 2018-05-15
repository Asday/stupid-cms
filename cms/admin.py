from django.contrib import admin

from polymorphic.admin import PolymorphicParentModelAdmin

from .models import Block, Page, TextBlock


@admin.register(Block)
class BlockAdmin(PolymorphicParentModelAdmin):
    base_model = Block
    child_models = (
        TextBlock,
    )


admin.site.register(TextBlock)
admin.site.register(Page)
