# Generated by Django 5.1.6 on 2025-03-12 03:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0006_invoicecustomer_rmproduct_rminventory"),
    ]

    operations = [
        migrations.AddField(
            model_name="rmorder",
            name="bill_to",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="rmorder",
            name="order_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="rmorder",
            name="ship_to",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
