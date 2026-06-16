from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0013_banner'),
    ]

    operations = [
        migrations.AddField(
            model_name='banner',
            name='mobile_image',
            field=models.ImageField(blank=True, null=True, upload_to='banners/mobile/'),
        ),
        migrations.AddField(
            model_name='banner',
            name='mobile_image_url',
            field=models.URLField(blank=True, help_text='External image or hosted GIF URL (mobile)'),
        ),
    ]
