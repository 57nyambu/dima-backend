# Generated by Django 5.1.3 on 2025-04-07 13:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_alter_product_compare_price'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='compare_price',
        ),
        migrations.CreateModel(
            name='CategoryImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='categories/')),
                ('alt_text', models.CharField(blank=True, max_length=255)),
                ('is_feature', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='products.category')),
            ],
        ),
    ]
