# Generated by Django 5.1.6 on 2025-05-01 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0035_rmproduct_shelfrecord"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rmproduct",
            name="Location",
            field=models.CharField(default="", max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="rmproduct",
            name="ShelfRecord",
            field=models.CharField(default="", max_length=255, null=True),
        ),
    ]
