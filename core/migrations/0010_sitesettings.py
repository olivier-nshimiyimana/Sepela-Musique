from django.db import migrations, models


def seed_site_settings(apps, schema_editor):
    SiteSettings = apps.get_model('core', 'SiteSettings')
    SiteSettings.objects.get_or_create(
        pk=1,
        defaults={
            'site_title': 'Sepela Musique',
            'contact_email': 'info@sepelamusique.com',
            'contact_phone': '+243 99899328',
            'contact_address': 'RD Congo, Kinshasa, Ndjili',
            'vote_from_email': 'info@sepelamusique.com',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_contact'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_title', models.CharField(default='Sepela Musique', help_text='Brand name used in vote confirmation email subject.', max_length=120)),
                ('contact_email', models.EmailField(help_text='Public email (contact page, mailto links).', max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=64)),
                ('contact_address', models.TextField(blank=True, help_text='Address / location shown on the contact page.')),
                ('vote_from_email', models.EmailField(help_text='From address on vote emails (should match your SMTP account).', max_length=254)),
            ],
            options={
                'verbose_name': 'Site settings',
                'verbose_name_plural': 'Site settings',
            },
        ),
        migrations.RunPython(seed_site_settings, migrations.RunPython.noop),
    ]
