# Generated by Django 3.0.7 on 2020-11-17 19:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('data_ocean', '0014_register_status'),
    ]

    operations = [
        migrations.RenameModel('EndPoint', 'Dataset'),
        migrations.AddField(
            model_name='dataset',
            name='total_records',
            field=models.PositiveIntegerField(blank=True, default=1, null=True, verbose_name='')
        ),
        migrations.AlterModelOptions(
            name='dataset',
            options={'ordering': ['id'], 'verbose_name': 'набір даних'},
        ),
    ]
