from django.contrib import admin
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Song, Vote, Token, Contact, SiteSettings


admin.site.unregister(Group)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'contact_email', 'contact_phone', 'contact_address', 'vote_from_email')
    fields = ('site_title', 'contact_email', 'contact_phone', 'contact_address', 'vote_from_email')

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Always send admins directly to the singleton settings record.
        obj = SiteSettings.get_solo()
        url = reverse('admin:core_sitesettings_change', args=[obj.pk])
        return HttpResponseRedirect(url)


class SongAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'description', 'song', 'thumbnail', 'date', 'status')


admin.site.register(Song, SongAdmin)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'song_title', 'songs', 'voter_Email')
    list_display_links = ('id', 'song_title')
    list_editable = ('songs', 'voter_Email')
    search_fields = ('voter_Email', 'songs')
    ordering = ('-id',)
    fields = ('songs', 'voter_Email')
    readonly_fields = ()

    @staticmethod
    def _song_for_vote(obj):
        try:
            pk = int(obj.songs)
        except (TypeError, ValueError):
            return None
        return Song.objects.filter(pk=pk).first()

    def song_title(self, obj):
        song = self._song_for_vote(obj)
        if song:
            return song.title
        return '—'

    song_title.short_description = 'Song'


class TokenAdmin(admin.ModelAdmin):
    list_display = ('user_token', 'song_id', 'user_Email')


admin.site.register(Token, TokenAdmin)


class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'subject', 'message')


admin.site.register(Contact, ContactAdmin)
