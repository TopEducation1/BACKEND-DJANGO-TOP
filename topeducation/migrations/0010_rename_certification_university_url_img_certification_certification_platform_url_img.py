# Generated by Django 5.1.2 on 2024-10-22 15:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('topeducation', '0009_certification_certification_university_url_img'),
    ]

    operations = [
        migrations.RenameField(
            model_name='certification',
            old_name='certification_university_url_img',
            new_name='certification_platform_url_img',
        ),
    ]
