# Generated by Django 5.1.2 on 2024-10-10 20:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('topeducation', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Companies',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=500)),
            ],
            options={
                'db_table': 'Empresas',
            },
        ),
        migrations.CreateModel(
            name='Regions',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region_name', models.CharField(max_length=500)),
            ],
            options={
                'db_table': 'Regiones',
            },
        ),
        migrations.CreateModel(
            name='Topics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic_name', models.CharField(max_length=250)),
            ],
            options={
                'db_table': 'Temas',
            },
        ),
        migrations.RenameModel(
            old_name='Category',
            new_name='Skills',
        ),
        migrations.RenameField(
            model_name='skills',
            old_name='category_name',
            new_name='hability_name',
        ),
        migrations.AlterModelTable(
            name='skills',
            table='Habilidades',
        ),
        migrations.CreateModel(
            name='Universities',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('university_name', models.CharField(max_length=500)),
                ('university_region', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='Universidades', to='topeducation.regions')),
            ],
            options={
                'db_table': 'Universidades',
            },
        ),
    ]
