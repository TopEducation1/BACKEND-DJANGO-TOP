# Generated by Django 5.1.5 on 2025-01-29 17:09

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('topeducation', '0010_certificaciones_fecha_creado'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificaciones',
            name='fecha_creado_cert',
            field=models.DateField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='certificaciones',
            name='video_certificacion',
            field=models.CharField(default='None', max_length=1000, null=True),
        ),
    ]
