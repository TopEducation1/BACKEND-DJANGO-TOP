# Generated by Django 5.1.2 on 2024-10-21 21:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('topeducation', '0005_remove_certification_certification_img_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='universities',
            name='university_url_img',
        ),
    ]
