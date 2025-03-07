# Generated by Django 4.1.7 on 2025-03-06 04:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('container', '0002_rename_file_name_container_container_pdfname_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Permission',
            fields=[
                ('index', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserAndPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('permissionIndex', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='container.permission')),
                ('userId', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('userId', 'permissionIndex')},
            },
        ),
    ]
