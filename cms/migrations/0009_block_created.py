# Generated by Django 2.0.5 on 2018-05-24 20:06

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0008_block_published'),
    ]

    operations = [
        migrations.AddField(
            model_name='block',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
