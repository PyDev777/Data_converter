# Generated by Django 2.2 on 2020-06-03 11:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_ocean', '0002_register'),
        ('business_register', '0008_auto_20200528_0707'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='hash_code',
            field=models.CharField(default=1, max_length=510),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalcompany',
            name='hash_code',
            field=models.CharField(default='1', max_length=510),
            preserve_default=False,
        ),
    ]
