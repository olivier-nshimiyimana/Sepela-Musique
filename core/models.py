import uuid

from django.db import models
from time import strftime, gmtime
from utils.song_utils import generate_file_name
from accounts.models import User

from .formatting import format_price_display






def song_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'songs/{0}/{1}'.format(strftime('%Y/%m/%d'), generate_file_name() + '.' + filename.split('.')[-1])

class Song(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name="Song name")
    description = models.TextField()
    song = models.FileField(upload_to=song_directory_path, max_length=500, blank=True, null=True)
    thumbnail = models.ImageField(upload_to='songs/thumbnails/', max_length=500, blank=True, null=True)
    fallback_song_data_url = models.TextField(blank=True, null=True)
    fallback_thumbnail_data_url = models.TextField(blank=True, null=True)
    # vote = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    status = models.TextField(default=0)

    
    def __str__(self):
        return self.title

    @property
    def has_vote_media(self):
        return bool(self.song_display_url or self.thumbnail_display_url)

    @property
    def song_display_url(self):
        if self.fallback_song_data_url:
            return self.fallback_song_data_url
        if self.song:
            try:
                return self.song.url
            except ValueError:
                return ''
        return ''

    @property
    def thumbnail_display_url(self):
        if self.fallback_thumbnail_data_url:
            return self.fallback_thumbnail_data_url
        if self.thumbnail:
            try:
                return self.thumbnail.url
            except ValueError:
                return ''
        return ''
    

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


class VotePackage(models.Model):
    """Configurable vote bundles (votes + price), edited under Administration."""

    title = models.CharField(max_length=120)
    vote_count = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='CDF')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('sort_order', 'id')

    def __str__(self):
        return '%s — %s votes · %s %s' % (
            self.title,
            self.vote_count,
            format_price_display(self.price),
            self.currency,
        )


class VoteRequest(models.Model):
    """Paid vote packages: pending admin confirmation, then counted via approved vote_count totals."""

    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    email = models.EmailField()
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='vote_requests')
    vote_package = models.ForeignKey(
        VotePackage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='requests',
    )
    package = models.CharField(max_length=120, help_text="Snapshot label (from VotePackage.title)")
    vote_count = models.PositiveIntegerField()
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=8, blank=True)
    payment_method = models.CharField(
        max_length=24,
        blank=True,
        help_text="Which mobile-money line the buyer used (airtel_money, afrimoney, mpesa).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    payment_proof = models.ImageField(
        upload_to='vote_payment_proofs/%Y/%m/',
        max_length=500,
        blank=True,
        null=True,
        help_text='Buyer screenshot / receipt (required on new requests via website form).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return '%s — %s (%s)' % (self.email, self.package, self.get_status_display())

    def payment_method_label(self):
        return SiteSettings.payment_method_label_for_key(self.payment_method)

    def payment_method_number(self):
        for row in SiteSettings.get_solo().mobile_payment_options():
            if row['key'] == self.payment_method:
                return row['number']
        return ''


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
    whatsapp_payments_phone = models.CharField(
        max_length=32,
        blank=True,
        help_text='WhatsApp for payment screenshots / confirmation (country code + number). Used for wa.me links.',
    )
    payment_registered_name = models.CharField(
        max_length=120,
        blank=True,
        help_text='Name shown on mobile money account (pay to this name).',
    )
    airtel_money_number = models.CharField(max_length=64, blank=True)
    afrimoney_number = models.CharField(max_length=64, blank=True)
    mpesa_number = models.CharField(max_length=64, blank=True)
    payment_instructions_note = models.TextField(
        blank=True,
        help_text='Optional extra lines shown to buyers (e.g. business hours, fees).',
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
                'contact_phone': '',
                'contact_address': 'RD Congo, Kinshasa, Ndjili',
                'vote_from_email': 'info@sepelamusique.com',
                'whatsapp_payments_phone': '',
                'payment_registered_name': '',
                'airtel_money_number': '',
                'afrimoney_number': '',
                'mpesa_number': '',
                'payment_instructions_note': '',
            },
        )
        return obj

    def mobile_money_lines(self):
        """Pairs (label, number) for templates and emails."""
        return [(row['label'], row['number']) for row in self.mobile_payment_options()]

    def mobile_payment_options(self):
        """Rows for checkout: key, label, number (only configured lines)."""
        spec = (
            ('airtel_money', 'Airtel Money', self.airtel_money_number),
            ('afrimoney', 'Afrimoney', self.afrimoney_number),
            ('mpesa', 'M-Pesa', self.mpesa_number),
        )
        out = []
        for key, label, raw in spec:
            if raw and raw.strip():
                out.append({'key': key, 'label': label, 'number': raw.strip()})
        return out

    @staticmethod
    def payment_method_label_for_key(key):
        if not key:
            return ''
        for row in SiteSettings.get_solo().mobile_payment_options():
            if row['key'] == key:
                return row['label']
        return key

    def whatsapp_payment_digits(self):
        """Digits only for wa.me — uses the dedicated WhatsApp field only (not contact phone)."""
        raw = (self.whatsapp_payments_phone or '').strip()
        if not raw:
            return ''
        return ''.join(c for c in raw if c.isdigit())

    def __str__(self):
        return 'Site settings'


class SiteConfiguration(models.Model):
    """Singleton (pk=1): global experience mode (music competition vs pageant-style copy)."""

    class Mode(models.TextChoices):
        MISS_KATANGA = 'MISS_KATANGA', 'Miss Katanga'
        ART_COMPETITION = 'ART_COMPETITION', 'Art competition'

    mode = models.CharField(
        max_length=32,
        choices=Mode.choices,
        default=Mode.ART_COMPETITION,
        help_text='Switches public wording (Artist vs Candidate, song vs contestant, etc.).',
    )

    class Meta:
        verbose_name = 'Site configuration'
        verbose_name_plural = 'Site configuration'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'mode': cls.Mode.ART_COMPETITION})
        return obj

    def __str__(self):
        return 'Site configuration'
