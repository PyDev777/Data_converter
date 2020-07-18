# Generated by Django 3.0.7 on 2020-07-16 14:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_ocean', '0004_auto_20200714_0751'),
        ('business_register', '0018_auto_20200710_0851'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='companydetail',
            name='authorized_capital',
        ),
        migrations.RemoveField(
            model_name='historicalcompanydetail',
            name='authorized_capital',
        ),
        migrations.AddField(
            model_name='company',
            name='authorized_capital',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='historicalcompany',
            name='authorized_capital',
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name='bancruptcyreadjustment',
            name='op_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='company',
            name='registration_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='exchangedatacompany',
            name='end_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='exchangedatacompany',
            name='start_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='exchangedatacompany',
            name='taxpayer_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='data_ocean.TaxpayerType'),
        ),
        migrations.AlterField(
            model_name='historicalcompany',
            name='registration_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='terminationstarted',
            name='creditor_reg_end_date',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='terminationstarted',
            name='op_date',
            field=models.DateField(null=True),
        ),
    ]