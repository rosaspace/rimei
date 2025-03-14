# Generated by Django 5.1.6 on 2025-03-13 19:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0011_logisticscompany"),
    ]

    operations = [
        migrations.AddField(
            model_name="clockrecord",
            name="employee_name",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to="container.employee",
            ),
            preserve_default=False,
        ),
    ]
