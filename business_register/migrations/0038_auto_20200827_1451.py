# Generated by Django 3.0.7 on 2020-08-27 14:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business_register', '0037_auto_20200820_1328'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pep',
            name='code',
            field=models.CharField(max_length=15, unique=True),
        ),
    ]
