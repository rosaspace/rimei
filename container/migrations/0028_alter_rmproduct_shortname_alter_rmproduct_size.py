# Generated by Django 5.1.6 on 2025-04-19 04:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0027_alter_rmproduct_shortname_alter_rmproduct_size"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rmproduct",
            name="shortname",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="rmproduct",
            name="size",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
