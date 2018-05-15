# Generated by Django 2.0.5 on 2018-05-15 22:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0005_page_denormalised_titles'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='block',
            options={},
        ),
        migrations.AddField(
            model_name='block',
            name='position',
            field=models.PositiveSmallIntegerField(default=0, editable=False),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='block',
            unique_together={('parent_page', 'position')},
        ),
    ]
