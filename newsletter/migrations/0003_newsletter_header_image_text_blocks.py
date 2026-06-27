from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newsletter', '0002_add_email_campaign_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsletter',
            name='header_image_url',
            field=models.URLField(blank=True, help_text='Full-width header image URL'),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='text_blocks',
            field=models.JSONField(blank=True, default=list, help_text='Custom text blocks: [{id, content, position}]'),
        ),
    ]
