# Generated by Django 5.1.6 on 2025-05-02 04:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0040_alter_rmproduct_location_alter_rmproduct_shelfrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="inboundcategory",
            name="Name",
            field=models.CharField(default="", max_length=255),
        ),
    ]
