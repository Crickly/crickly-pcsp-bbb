# Generated by Django 3.0.4 on 2020-04-11 20:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pcsp_bbb', '0008_auto_20200411_2019'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='error_text',
            field=models.TextField(default=''),
        ),
    ]