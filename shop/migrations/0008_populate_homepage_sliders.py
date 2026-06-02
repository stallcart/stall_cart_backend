from django.db import migrations

def populate_slides(apps, schema_editor):
    HomepageBanner = apps.get_model('shop', 'HomepageBanner')
    
    DEFAULT_SLIDES = [
        {
            'title': 'Summer Elegance 2026',
            'subtitle': 'Discover premium pastel styles for men & women. Up to 50% Off.',
            'image': 'banners/slide1.png',
            'link_url': '/products/',
            'banner_type': 'main_slider',
            'order': 1,
        },
        {
            'title': 'Festive Splendor Collection',
            'subtitle': 'Radiate tradition in our mustard yellow and royal blue ethnics.',
            'image': 'banners/slide2.png',
            'link_url': '/products/',
            'banner_type': 'main_slider',
            'order': 2,
        },
        {
            'title': 'Streetwear Denim Collective',
            'subtitle': 'Explore modern raw denim fits & urban coordinates.',
            'image': 'banners/slide3.png',
            'link_url': '/products/',
            'banner_type': 'main_slider',
            'order': 3,
        },
        {
            'title': 'Elevate Your Activewear',
            'subtitle': 'Engineered performance gear & comfortable lifestyle athleisure.',
            'image': 'banners/slide4.png',
            'link_url': '/products/',
            'banner_type': 'main_slider',
            'order': 4,
        },
        {
            'title': 'Aura Luxe Accessories',
            'subtitle': 'Accentuate your look with luxury leather bags, timepieces & eyewear.',
            'image': 'banners/slide5.png',
            'link_url': '/products/',
            'banner_type': 'main_slider',
            'order': 5,
        }
    ]
    
    for slide_data in DEFAULT_SLIDES:
        HomepageBanner.objects.get_or_create(
            title=slide_data['title'],
            defaults={
                'subtitle': slide_data['subtitle'],
                'image': slide_data['image'],
                'link_url': slide_data['link_url'],
                'banner_type': slide_data['banner_type'],
                'order': slide_data['order'],
                'is_active': True
            }
        )

def remove_slides(apps, schema_editor):
    HomepageBanner = apps.get_model('shop', 'HomepageBanner')
    HomepageBanner.objects.filter(image__in=[
        'banners/slide1.png',
        'banners/slide2.png',
        'banners/slide3.png',
        'banners/slide4.png',
        'banners/slide5.png'
    ]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0007_announcementbanner_delete_launchsalebanner'),
    ]

    operations = [
        migrations.RunPython(populate_slides, remove_slides),
    ]
