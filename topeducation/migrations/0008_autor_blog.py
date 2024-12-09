# Generated by Django 5.1.2 on 2024-12-09 19:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('topeducation', '0007_certificaciones_imagen_final_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Autor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_autor', models.CharField(max_length=250)),
            ],
        ),
        migrations.CreateModel(
            name='Blog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo_blog', models.CharField(default='titulo', max_length=300)),
                ('contenido_blog', models.TextField(blank=True, null=True)),
                ('url_imagen_blog', models.TextField(blank=True, null=True)),
                ('fecha_blog_redacccion', models.DateField(auto_now_add=True)),
                ('autor_blog', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='topeducation.autor')),
            ],
            options={
                'verbose_name': 'Blog',
                'verbose_name_plural': 'Blogs',
                'ordering': ['-fecha_blog_redacccion'],
            },
        ),
    ]
