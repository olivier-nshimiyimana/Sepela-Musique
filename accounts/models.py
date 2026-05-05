import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


def _artist_promo_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    return 'artist_promo/images/%s.%s' % (uuid.uuid4().hex, ext)


def _artist_promo_video_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'mp4'
    return 'artist_promo/videos/%s.%s' % (uuid.uuid4().hex, ext)


class User(AbstractUser):
    username = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    avatar = models.ImageField('profile picture', upload_to='static/images/user/', null=True, blank=True)
    email = models.EmailField(unique=True, blank=False,
                              error_messages={
                                  'unique': "A user with that email already exists.",
                              })
    user_type = models.IntegerField(default=2)
    artist_promo_image = models.ImageField(
        upload_to=_artist_promo_image_path,
        blank=True,
        null=True,
        max_length=500,
        help_text='Leaderboard thumbnail (use image OR short promo video, not both).',
    )
    artist_promo_video = models.FileField(
        upload_to=_artist_promo_video_path,
        blank=True,
        null=True,
        max_length=500,
        help_text='Short promo clip for leaderboard (use video OR thumbnail image, not both).',
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __unicode__(self):
        return self.email


class Profile(models.Model):
  user = models.OneToOneField(User, on_delete=models.CASCADE)
  forget_password_token = models.CharField(max_length=100)
  created_at = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return self.user.email