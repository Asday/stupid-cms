# Generated by Django 2.0.5 on 2018-05-19 18:53

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cms', '0006_auto_20180515_2233'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnsavedWork',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.TextField(db_index=True)),
                ('work', models.TextField()),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='unsaved_works', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='unsavedwork',
            unique_together={('user', 'path')},
        ),
    ]
