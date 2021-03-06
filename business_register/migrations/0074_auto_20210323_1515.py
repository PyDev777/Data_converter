# Generated by Django 3.0.7 on 2021-03-23 15:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business_register', '0073_auto_20210323_1515'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignee',
            name='edrpou',
            field=models.CharField(blank=True, default='', help_text='EDRPOU number as string', max_length=11, verbose_name='number'),
        ),
        migrations.AlterField(
            model_name='assignee',
            name='name',
            field=models.CharField(blank=True, default='', help_text='Assignee name in Ukrainian', max_length=610, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='historicalassignee',
            name='edrpou',
            field=models.CharField(blank=True, default='', help_text='EDRPOU number as string', max_length=11, verbose_name='number'),
        ),
        migrations.AlterField(
            model_name='historicalassignee',
            name='name',
            field=models.CharField(blank=True, default='', help_text='Assignee name in Ukrainian', max_length=610, verbose_name='name'),
        ),
    ]
