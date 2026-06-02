# Generated dynamically to pre-populate default categories
from django.db import migrations

def populate_categories(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    
    categories = [
        {'name': 'Cloth', 'slug': 'cloth', 'description': 'Fashion, apparel, and clothing products'},
        {'name': 'Furniture', 'slug': 'furniture', 'description': 'Premium home furniture, decor, and fittings'},
        {'name': 'Jewellery', 'slug': 'jewellery', 'description': 'Exquisite and premium jewelry items'}
    ]
    
    for cat_data in categories:
        Category.objects.get_or_create(
            name=cat_data['name'],
            defaults={
                'slug': cat_data['slug'],
                'description': cat_data['description'],
                'commision_percentage': 0.0,
                'is_active': True
            }
        )

def remove_categories(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    Category.objects.filter(slug__in=['furniture', 'jewellery']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('items', '0011_alter_product_gender'),
    ]

    operations = [
        migrations.RunPython(populate_categories, remove_categories),
    ]
