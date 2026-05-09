from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Contact, SiteSettings, Song, VotePackage, VoteRequest


class SongUploadForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = ("title", "description", "song")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(SongUploadForm, self).__init__(*args, **kwargs)

    def clean_user(self):
        return self.user


_MAX_PAYMENT_PROOF_BYTES = 6 * 1024 * 1024
_ALLOWED_PROOF_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp'})


class PaidVoteRequestForm(forms.ModelForm):
    """Paid vote: email, song, package, payment channel, proof image — then WhatsApp."""

    class Meta:
        model = VoteRequest
        fields = ('email', 'song', 'vote_package', 'payment_proof')
        widgets = {
            'email': forms.EmailInput(
                attrs={
                    'class': 'tw-w-full tw-rounded-xl tw-border tw-border-white/15 tw-bg-black/30 tw-px-4 tw-py-3 tw-text-sm tw-text-white',
                    'autocomplete': 'email',
                    'required': True,
                }
            ),
            'song': forms.Select(
                attrs={
                    'class': 'tw-w-full tw-rounded-xl tw-border tw-border-white/15 tw-bg-black/30 tw-px-4 tw-py-3 tw-text-sm tw-text-white',
                }
            ),
            'vote_package': forms.Select(
                attrs={
                    'class': 'tw-w-full tw-rounded-xl tw-border tw-border-white/15 tw-bg-black/30 tw-px-4 tw-py-3 tw-text-sm tw-text-white',
                    'id': 'id_vote_package',
                }
            ),
            'payment_proof': forms.ClearableFileInput(
                attrs={
                    'class': 'tw-block tw-w-full tw-text-sm tw-text-white/80 file:tw-mr-4 file:tw-rounded-lg file:tw-border-0 file:tw-bg-violet-600 file:tw-px-4 file:tw-py-2 file:tw-font-semibold file:tw-text-white hover:file:tw-brightness-110',
                    'accept': 'image/jpeg,image/png,image/webp',
                }
            ),
        }

    def __init__(self, *args, fixed_song_pk=None, **kwargs):
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fixed_song_pk = fixed_song_pk
        published = Song.objects.filter(status='2').select_related('user').order_by('title')
        self.fields['song'].queryset = published
        if fixed_song_pk:
            song = Song.objects.filter(pk=fixed_song_pk, status='2').first()
            if song:
                self.fields['song'].queryset = Song.objects.filter(pk=song.pk)
                self.fields['song'].initial = song.pk
                self.fields['song'].widget = forms.HiddenInput()

        qs = VotePackage.objects.filter(is_active=True).order_by('sort_order', 'id')
        self.fields['vote_package'].queryset = qs
        self.fields['vote_package'].empty_label = 'Choose a package…'
        self.fields['vote_package'].label = 'Vote package'

        self.fields['payment_proof'].required = True
        self.fields['payment_proof'].label = 'Payment proof (screenshot)'

    def clean(self):
        cleaned_data = super().clean()
        rows = SiteSettings.get_solo().mobile_payment_options()
        key = (self.data.get('payment_method') or '').strip()
        if rows:
            if not key:
                raise forms.ValidationError(_('Choose which number you paid to.'))
            valid = {r['key'] for r in rows}
            if key not in valid:
                raise forms.ValidationError(_('Invalid payment option.'))
            cleaned_data['payment_method'] = key
        else:
            cleaned_data['payment_method'] = ''
        return cleaned_data

    def clean_vote_package(self):
        pkg = self.cleaned_data.get('vote_package')
        if not pkg:
            raise forms.ValidationError(_('Choose a vote package.'))
        if not pkg.is_active:
            raise forms.ValidationError(_('This package is no longer available.'))
        return pkg

    def clean_payment_proof(self):
        f = self.cleaned_data.get('payment_proof')
        if not f:
            raise ValidationError(_('Upload a screenshot of your payment before continuing.'))
        if f.size > _MAX_PAYMENT_PROOF_BYTES:
            raise ValidationError(_('Image must be at most 6 MB.'))
        ct = getattr(f, 'content_type', None) or ''
        if ct and ct not in _ALLOWED_PROOF_TYPES:
            raise ValidationError(_('Use a JPG, PNG, or WebP image.'))
        return f

    def save(self, commit=True):
        instance = super().save(commit=False)
        pkg = self.cleaned_data['vote_package']
        instance.package = pkg.title
        instance.vote_count = pkg.vote_count
        instance.price_amount = pkg.price
        instance.currency_code = pkg.currency
        instance.vote_package = pkg
        instance.payment_method = (self.cleaned_data.get('payment_method') or '').strip()
        if commit:
            instance.save()
        return instance


class HelpForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = '__all__'

        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Enter your email'}),
            'subject': forms.TextInput(attrs={'placeholder': 'Enter your Subject'}),
            'message': forms.Textarea(attrs={'placeholder': 'Enter your Message'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
