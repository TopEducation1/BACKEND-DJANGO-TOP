# Generated by Django 5.1.2 on 2024-12-09 19:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('topeducation', '0008_autor_blog'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='autor',
            table='autor',
        ),
        migrations.AlterModelTable(
            name='blog',
            table='blog',
        ),
    ]