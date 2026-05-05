from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_profile_id_alter_user_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='artist_promo_image',
            field=models.ImageField(blank=True, null=True, upload_to='artist_promo/images/', max_length=500),
        ),
        migrations.AddField(
            model_name='user',
            name='artist_promo_video',
            field=models.FileField(blank=True, null=True, upload_to='artist_promo/videos/', max_length=500),
        ),
    ]
