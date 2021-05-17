# Generated by Django 3.0.7 on 2021-05-13 14:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business_register', '0099_auto_20210512_0708'),
    ]

    operations = [
        migrations.AddField(
            model_name='fop',
            name='registration_date_second',
            field=models.DateField(blank=True, null=True, verbose_name='registration date second'),
        ),
        migrations.AddField(
            model_name='fop',
            name='registration_number',
            field=models.CharField(blank=True, max_length=17, null=True, verbose_name='registration number'),
        ),
        migrations.AddField(
            model_name='historicalfop',
            name='registration_date_second',
            field=models.DateField(blank=True, null=True, verbose_name='registration date second'),
        ),
        migrations.AddField(
            model_name='historicalfop',
            name='registration_number',
            field=models.CharField(blank=True, max_length=17, null=True, verbose_name='registration number'),
        ),
    ]