# Generated by Django 5.1.6 on 2025-06-17 03:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="containerstatement",
            name="container_id_str",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
