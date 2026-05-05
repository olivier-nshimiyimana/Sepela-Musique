from django.db import models
from time import strftime, gmtime
from utils.song_utils import generate_file_name
from accounts.models import User






def song_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'songs/{0}/{1}'.format(strftime('%Y/%m/%d'), generate_file_name() + '.' + filename.split('.')[-1])

class Song(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name="Song name")
    description = models.TextField()
    song = models.FileField(upload_to=song_directory_path, max_length=500, blank=True, null=True)
    thumbnail = models.ImageField(upload_to='songs/thumbnails/', max_length=500, blank=True, null=True)
    # vote = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    status = models.TextField(default=0)

    
    def __str__(self):
        return self.title

    @property
    def has_vote_media(self):
        return bool(self.song or self.thumbnail)
    

class Vote(models.Model):
    songs = models.TextField()
    voter_Email = models.EmailField(max_length=254)
 
    @property
    def count_votes(self):
        from django.db.models import Count
        votes = Vote.objects.filter(songs=self.songs).values('songs').annotate(votes=Count('songs'))
        if votes:
            return votes[0]['votes']
        else:
            return 0
    
    def __str__(self):
        return self.voter_Email
        
class Token(models.Model):
    user_token = models.TextField()
    song_id = models.TextField()
    user_Email = models.TextField()
    # vote = models.IntegerField(default=0)


class Contact(models.Model):
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()

    def __str__(self):
        return self.email


class SiteSettings(models.Model):
    """Singleton (pk=1): public contact info and outbound vote email — edit in Django admin."""

    site_title = models.CharField(
        max_length=120,
        default='Sepela Musique',
        help_text='Brand name used in vote confirmation email subject.',
    )
    contact_email = models.EmailField(
        help_text='Public email (contact page, mailto links).',
    )
    contact_phone = models.CharField(max_length=64, blank=True)
    contact_address = models.TextField(
        blank=True,
        help_text='Address / location shown on the contact page.',
    )
    vote_from_email = models.EmailField(
        help_text='From address on vote emails (should match your SMTP account).',
    )

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'site_title': 'Sepela Musique',
                'contact_email': 'info@sepelamusique.com',
                'contact_phone': '+243 99899328',
                'contact_address': 'RD Congo, Kinshasa, Ndjili',
                'vote_from_email': 'info@sepelamusique.com',
            },
        )
        return obj

    def __str__(self):
        return 'Site settings'
