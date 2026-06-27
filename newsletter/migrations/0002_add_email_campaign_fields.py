from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newsletter', '0001_initial'),
        ('content', '0012_merge_20260610_0905'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsletter',
            name='email_type',
            field=models.CharField(
                choices=[('newsletter', 'Newsletter'), ('direct', 'Direct Email')],
                default='newsletter',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='recipients_type',
            field=models.CharField(
                choices=[('subscribers', 'Subscribers'), ('all_users', 'All Users'), ('custom', 'Custom')],
                default='subscribers',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='custom_recipients',
            field=models.TextField(blank=True, help_text='Comma-separated email addresses'),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='greeting_text',
            field=models.CharField(blank=True, help_text="Optional greeting e.g. 'Dear Reader,'", max_length=255),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='template_style',
            field=models.CharField(
                choices=[('classic', 'Classic'), ('modern', 'Modern'), ('minimal', 'Minimal')],
                default='classic',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='accent_color',
            field=models.CharField(default='#c0392b', help_text='Hex color for branding', max_length=7),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='article_order',
            field=models.JSONField(blank=True, default=list, help_text='Ordered list of article IDs'),
        ),
        migrations.AlterField(
            model_name='newsletter',
            name='content_html',
            field=models.TextField(blank=True, help_text='HTML email content (used for direct emails)'),
        ),
        migrations.AlterField(
            model_name='newsletter',
            name='content_text',
            field=models.TextField(blank=True, help_text='Plain text fallback'),
        ),
        migrations.AddField(
            model_name='newsletter',
            name='articles',
            field=models.ManyToManyField(
                blank=True,
                help_text='Articles to feature in newsletter campaigns',
                related_name='newsletters',
                to='content.article',
            ),
        ),
    ]
