# Generated by Django 3.0.4 on 2020-04-11 18:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('playcricket', '0001_initial'),
        ('pcsp_bbb', '0005_auto_20200411_1919'),
    ]

    operations = [
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_pcsp', models.BooleanField()),
                ('is_live', models.BooleanField()),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match', to='playcricket.Match')),
            ],
        ),
    ]
