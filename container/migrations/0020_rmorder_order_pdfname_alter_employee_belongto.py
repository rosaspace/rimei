# Generated by Django 5.1.6 on 2025-03-20 13:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0019_employee_belongto"),
    ]

    operations = [
        migrations.AddField(
            model_name="rmorder",
            name="order_pdfname",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="employee",
            name="belongTo",
            field=models.CharField(default="CabinetsDepot", max_length=255),
        ),
    ]
