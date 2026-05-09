import uuid
import logging
import base64
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.models import User

from .formatting import format_price_display
from .forms import HelpForm, PaidVoteRequestForm
from .leaderboard import top_artists_by_votes
from .models import Contact, SiteConfiguration, SiteSettings, Song, Token, Vote, VotePackage, VoteRequest
from .video_thumbnails import ensure_song_thumbnail_from_video
from .vote_totals import combined_votes_for_song, song_vote_count_maps, total_vote_units_dashboard

logger = logging.getLogger(__name__)

VOTE_REQUEST_DASHBOARD_LIMIT = 200


def _safe_dashboard_return_path(raw_path):
    allowed = {'/', reverse('core:app_administration')}
    path = (raw_path or '').strip() or reverse('core:app_administration')
    return path if path in allowed else reverse('core:app_administration')


def _parse_decimal(value):
    raw = (value or '').strip().replace(',', '.')
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _non_negative_int(value, default=0):
    try:
        n = int(value)
        return n if n >= 0 else default
    except (TypeError, ValueError):
        return default


def _payment_instructions_plain(site):
    lines = []
    if site.payment_registered_name.strip():
        lines.append('Pay to name: %s' % site.payment_registered_name.strip())
    for label, num in site.mobile_money_lines():
        lines.append('%s: %s' % (label, num))
    note = site.payment_instructions_note.strip()
    if note:
        lines.append(note)
    return '\n'.join(lines)


def _vote_requests_for_dashboard(request):
    raw = (request.GET.get('vr_status') or 'pending').strip().lower()
    if raw not in ('pending', 'approved', 'rejected', 'all'):
        raw = 'pending'
    qs = VoteRequest.objects.select_related('song', 'song__user').order_by('-created_at')
    if raw == 'pending':
        qs = qs.filter(status=VoteRequest.Status.PENDING)
    elif raw == 'approved':
        qs = qs.filter(status=VoteRequest.Status.APPROVED)
    elif raw == 'rejected':
        qs = qs.filter(status=VoteRequest.Status.REJECTED)
    return list(qs[:VOTE_REQUEST_DASHBOARD_LIMIT]), raw


def _file_to_data_url(uploaded_file, fallback_mime):
    if not uploaded_file:
        return None
    raw = uploaded_file.read()
    uploaded_file.seek(0)
    if not raw:
        return None
    mime_type = getattr(uploaded_file, 'content_type', None) or fallback_mime
    encoded = base64.b64encode(raw).decode('ascii')
    return 'data:%s;base64,%s' % (mime_type, encoded)


def _song_vote_count(song_id, legacy_map=None, req_map=None):
    return combined_votes_for_song(song_id, legacy_map, req_map)


def _home_songs_with_votes(queryset, ascending_by_votes=True):
    """Materialize queryset, attach .votes, sort by vote count (default: ascending)."""
    legacy_map, req_map = song_vote_count_maps()
    songs = list(queryset)
    for song in songs:
        song.votes = combined_votes_for_song(song.id, legacy_map, req_map)
    songs.sort(key=lambda s: s.votes, reverse=not ascending_by_votes)
    return songs



def button(request):
    status =Song.objects.filter(status=1)
    return render(request, "home.html", {'status': status})




def home(request):
    search = ''
    leaderboard = top_artists_by_votes(10)

    if request.GET.get('search_query'):
        search = request.GET.get('search_query')

    if not request.user.is_authenticated:

        songs = (
            Song.objects.filter(status=2)
            .filter(
                Q(song__isnull=False)
                | Q(thumbnail__isnull=False)
                | Q(fallback_song_data_url__isnull=False)
                | Q(fallback_thumbnail_data_url__isnull=False)
            )
            .select_related('user')
        )

        legacy_map, req_map = song_vote_count_maps()
        for song in songs:
            song.votes = combined_votes_for_song(song.id, legacy_map, req_map)
        return render(request, "home.html", {'songs': songs, 'leaderboard': leaderboard})
    if request.user.user_type == 1:
        ctx = _admin_dashboard_context(request)
        ctx['recent_songs'] = Song.objects.select_related('user').order_by('-id')[:8]
        ctx['recent_votes'] = Vote.objects.order_by('-id')[:10]
        ctx['recent_contacts'] = Contact.objects.order_by('-id')[:8]
        _enrich_admin_dashboard_lists(ctx['recent_songs'], ctx['recent_votes'])
        return render(request, 'admin_dashboard_modern.html', ctx)
    else:
        if search:
            songs = Song.objects.filter(
                Q(description__icontains=search) |
                Q(title__icontains=search) &
                Q(user=request.user.id)
            ).select_related('user')
        else:
            songs = Song.objects.all().filter(user=request.user.id).select_related('user')
        songs = _home_songs_with_votes(songs, ascending_by_votes=True)
        upload = Song.objects.filter(user=request.user.id).count()

        return render(
            request,
            "home.html",
            {'songs': songs, 'upload': upload, 'leaderboard': leaderboard},
        )

def _song_awaits_publish_or_reject(song):
    """Statuses waiting on Publish song room (pending / accepted, not yet live or rejected)."""
    return str(song.status) in ('0', '1')


@login_required
def song_view(request):
    if request.user.user_type != 1:
        messages.error(request, 'Only administration users can access this page.')
        return redirect(reverse('core:home'))

    search = (request.GET.get('search_query') or '').strip()
    songs = (
        Song.objects.select_related('user')
        .filter(status__in=['0', '1'])
        .order_by('-id')
    )
    if search:
        songs = songs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search),
        )
    songs = list(songs[:400])
    legacy_map, req_map = song_vote_count_maps()
    for song in songs:
        song.votes = combined_votes_for_song(song.id, legacy_map, req_map)

    return render(
        request,
        'publish_list_details.html',
        {'songs': songs, 'search_query': search},
    )


def _moderation_redirect(request):
    """POST `next=dashboard` → administration; else publish song page."""
    if request.POST.get('next') == 'dashboard':
        return redirect(reverse('core:app_administration'))
    return redirect(reverse('core:song_view'))


@login_required
def hide_song(request, id):
    """Admin: remove track from public catalogue (status 4)."""
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    if request.method != 'POST':
        return redirect(reverse('core:song_view'))
    song = get_object_or_404(Song, pk=id)
    song.status = '4'
    song.save(update_fields=['status'])
    messages.success(request, 'Track hidden from the public catalogue.')
    return _moderation_redirect(request)


@login_required
def unhide_song(request, id):
    """Admin: restore hidden track to published (status 2)."""
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    if request.method != 'POST':
        return redirect(reverse('core:song_view'))
    song = get_object_or_404(Song, pk=id)
    if song.status == '4':
        song.status = '2'
        song.save(update_fields=['status'])
        messages.success(request, 'Track is visible on the catalogue again.')
    else:
        messages.info(request, 'Track was not hidden; status unchanged.')
    return _moderation_redirect(request)


@login_required
def reset_song_votes(request, id):
    """Admin: delete all Vote rows for this song (requires POST + confirm_reset=yes)."""
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    if request.method != 'POST':
        return redirect(reverse('core:song_view'))
    if request.POST.get('confirm_reset') != 'yes':
        messages.error(request, 'Reset was not confirmed.')
        return _moderation_redirect(request)
    song = get_object_or_404(Song, pk=id)
    deleted, _ = Vote.objects.filter(songs=str(song.id)).delete()
    messages.success(request, 'Removed %s vote(s) for "%s".' % (deleted, song.title))
    return _moderation_redirect(request)


@login_required
def catalog_publish_song(request, id):
    """Admin (publish song page): set status to published (2)."""
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    if request.method != 'POST':
        return redirect(reverse('core:song_view'))
    song = get_object_or_404(Song, pk=id)
    if not _song_awaits_publish_or_reject(song):
        messages.info(request, 'That track is no longer in the moderation queue.')
        return redirect(reverse('core:song_view'))
    song.status = '2'
    song.save(update_fields=['status'])
    messages.success(request, 'Published: "%s".' % song.title)
    return redirect(reverse('core:song_view'))


@login_required
def catalog_reject_song(request, id):
    """Admin (publish song page): set status to rejected (3)."""
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    if request.method != 'POST':
        return redirect(reverse('core:song_view'))
    song = get_object_or_404(Song, pk=id)
    if not _song_awaits_publish_or_reject(song):
        messages.info(request, 'That track is no longer in the moderation queue.')
        return redirect(reverse('core:song_view'))
    song.status = '3'
    song.save(update_fields=['status'])
    messages.success(request, 'Rejected: "%s".' % song.title)
    return redirect(reverse('core:song_view'))


def _enrich_admin_dashboard_lists(recent_songs, recent_votes):
    legacy_map, req_map = song_vote_count_maps()
    for song in recent_songs:
        song.votes = combined_votes_for_song(song.id, legacy_map, req_map)
    song_title_map = {str(s.id): s.title for s in Song.objects.only('id', 'title')}
    for vote in recent_votes:
        vote.song_title = song_title_map.get(str(vote.songs), 'Unknown song')


def _admin_dashboard_context(request):
    uploads = User.objects.filter(user_type=2).count()
    total_songs = Song.objects.count()
    total_votes = total_vote_units_dashboard()
    total_contacts = Contact.objects.count()
    recent_songs = Song.objects.select_related('user').order_by('-id')[:12]
    recent_votes = Vote.objects.order_by('-id')[:12]
    recent_contacts = Contact.objects.order_by('-id')[:8]
    site_settings = SiteSettings.get_solo()
    site_configuration = SiteConfiguration.get_solo()
    vote_requests, vote_request_status_filter = _vote_requests_for_dashboard(request)

    _enrich_admin_dashboard_lists(recent_songs, recent_votes)

    return {
        'uploads': uploads,
        'total_songs': total_songs,
        'total_votes': total_votes,
        'total_contacts': total_contacts,
        'recent_songs': recent_songs,
        'recent_votes': recent_votes,
        'recent_contacts': recent_contacts,
        'site_settings': site_settings,
        'site_configuration': site_configuration,
        'vote_requests': vote_requests,
        'vote_request_status_filter': vote_request_status_filter,
        'vote_requests_actionable': vote_request_status_filter in ('pending', 'all'),
        'vote_packages': VotePackage.objects.order_by('sort_order', 'id'),
    }


@login_required
def app_administration(request):
    if request.user.user_type != 1:
        messages.error(request, 'Only administration users can access this page.')
        return redirect(reverse('core:home'))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_site_configuration':
            cfg = SiteConfiguration.get_solo()
            raw = (request.POST.get('site_mode') or '').strip()
            valid = {m.value for m in SiteConfiguration.Mode}
            if raw not in valid:
                messages.error(request, 'Invalid site mode.')
            else:
                cfg.mode = raw
                cfg.save(update_fields=['mode'])
                messages.success(request, 'Site mode updated.')
            return redirect(reverse('core:app_administration'))

        if action == 'save_site_settings':
            site = SiteSettings.get_solo()
            site.site_title = request.POST.get('site_title', site.site_title).strip() or site.site_title
            site.contact_email = request.POST.get('contact_email', site.contact_email).strip() or site.contact_email
            site.contact_phone = request.POST.get('contact_phone', '').strip()
            site.contact_address = request.POST.get('contact_address', '').strip()
            site.vote_from_email = request.POST.get('vote_from_email', site.vote_from_email).strip() or site.vote_from_email
            site.whatsapp_payments_phone = request.POST.get('whatsapp_payments_phone', '').strip()
            site.payment_registered_name = request.POST.get('payment_registered_name', '').strip()
            site.airtel_money_number = request.POST.get('airtel_money_number', '').strip()
            site.afrimoney_number = request.POST.get('afrimoney_number', '').strip()
            site.mpesa_number = request.POST.get('mpesa_number', '').strip()
            site.payment_instructions_note = request.POST.get('payment_instructions_note', '').strip()
            site.save()
            messages.success(request, 'Site settings updated.')
            return redirect(reverse('core:app_administration'))

        if action == 'add_vote_package':
            title = request.POST.get('vp_title', '').strip()
            price = _parse_decimal(request.POST.get('vp_price'))
            votes = _non_negative_int(request.POST.get('vp_vote_count'), 0)
            currency = (request.POST.get('vp_currency') or 'CDF').strip()[:8] or 'CDF'
            sort_order = _non_negative_int(request.POST.get('vp_sort_order'), 0)
            is_active = request.POST.get('vp_is_active') == '1'
            if not title or price is None or price <= 0 or votes < 1:
                messages.error(request, 'Add a title, a positive price, and at least one vote.')
            else:
                VotePackage.objects.create(
                    title=title,
                    vote_count=votes,
                    price=price,
                    currency=currency,
                    sort_order=sort_order,
                    is_active=is_active,
                )
                messages.success(request, 'Vote package added.')
            return redirect(reverse('core:app_administration'))

        if action == 'update_vote_package':
            pk = request.POST.get('package_id')
            vp = VotePackage.objects.filter(pk=pk).first() if str(pk).isdigit() else None
            if not vp:
                messages.error(request, 'Package not found.')
            else:
                title = request.POST.get('vp_title', '').strip()
                price = _parse_decimal(request.POST.get('vp_price'))
                votes = _non_negative_int(request.POST.get('vp_vote_count'), 0)
                currency = (request.POST.get('vp_currency') or vp.currency).strip()[:8] or 'CDF'
                sort_order = _non_negative_int(request.POST.get('vp_sort_order'), vp.sort_order)
                is_active = request.POST.get('vp_is_active') == '1'
                if not title or price is None or price <= 0 or votes < 1:
                    messages.error(request, 'Invalid package fields.')
                else:
                    vp.title = title
                    vp.vote_count = votes
                    vp.price = price
                    vp.currency = currency
                    vp.sort_order = sort_order
                    vp.is_active = is_active
                    vp.save()
                    messages.success(request, 'Vote package updated.')
            return redirect(reverse('core:app_administration'))

        if action == 'delete_vote_package':
            pk = request.POST.get('package_id')
            vp = VotePackage.objects.filter(pk=pk).first() if str(pk).isdigit() else None
            if vp:
                vp.delete()
                messages.success(request, 'Vote package removed.')
            else:
                messages.error(request, 'Package not found.')
            return redirect(reverse('core:app_administration'))

        if action in ('publish_song', 'reject_song'):
            song_id = request.POST.get('song_id')
            song = Song.objects.filter(id=song_id).first()
            if not song:
                messages.error(request, 'Song not found.')
                return redirect(reverse('core:app_administration'))

            song.status = '2' if action == 'publish_song' else '3'
            song.save(update_fields=['status'])
            messages.success(request, 'Song updated.')
            return redirect(reverse('core:app_administration'))

        if action in ('approve_vote_requests', 'reject_vote_requests'):
            return_path = _safe_dashboard_return_path(request.POST.get('return_path'))
            vr_tab = (request.POST.get('return_vr_status') or 'pending').strip().lower()
            if vr_tab not in ('pending', 'approved', 'rejected', 'all'):
                vr_tab = 'pending'
            id_list = []
            for raw in request.POST.getlist('vote_request_id'):
                if str(raw).isdigit():
                    id_list.append(int(raw))
            if not id_list:
                messages.error(request, 'No vote package requests selected.')
                return redirect('%s?%s' % (return_path, urlencode({'vr_status': vr_tab})))

            base_qs = VoteRequest.objects.filter(pk__in=id_list, status=VoteRequest.Status.PENDING)
            if action == 'approve_vote_requests':
                n = base_qs.update(status=VoteRequest.Status.APPROVED)
                messages.success(request, '%s package request(s) approved.' % n)
            else:
                n = base_qs.update(status=VoteRequest.Status.REJECTED)
                messages.success(request, '%s package request(s) rejected.' % n)
            return redirect('%s?%s' % (return_path, urlencode({'vr_status': vr_tab})))

    return render(request, "admin_dashboard_modern.html", _admin_dashboard_context(request))


@login_required
def send_test_email(request):
    if request.user.user_type != 1:
        messages.error(request, 'Only administration users can access this page.')
        return redirect(reverse('core:home'))

    recipient = (request.POST.get('email') or request.GET.get('email') or request.user.email or '').strip()
    if not recipient:
        messages.error(request, 'Provide an email address using ?email=you@example.com.')
        return redirect(reverse('core:app_administration'))

    site = SiteSettings.get_solo()
    subject = '[%s] Brevo test email' % site.site_title
    body = (
        'Hello,\n\n'
        'This is a test email from Sepela Musique.\n'
        'If you received this, email delivery is working.\n'
    )
    from_email = site.vote_from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None)

    try:
        send_mail(subject, body, from_email, [recipient], fail_silently=False)
        messages.success(request, 'Test email sent to %s.' % recipient)
    except Exception:
        logger.exception('Test email send failed')
        messages.error(request, 'Test email failed. Check server logs for Brevo error details.')
    return redirect(reverse('core:app_administration'))


@login_required
def admin_song_votes(request, id):
    if request.user.user_type != 1:
        messages.error(request, 'Only administration users can access this page.')
        return redirect(reverse('core:home'))

    song = get_object_or_404(Song, pk=id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_votes':
            try:
                amount = int(request.POST.get('vote_amount', '0'))
            except ValueError:
                amount = 0

            if amount <= 0:
                messages.error(request, 'Enter a valid number of votes to add.')
                return redirect(reverse('core:admin_song_votes', args=[song.id]))
            if amount > 5000:
                messages.error(request, 'Please add at most 5000 votes at a time.')
                return redirect(reverse('core:admin_song_votes', args=[song.id]))

            for _ in range(amount):
                Vote.objects.create(
                    songs=str(song.id),
                    voter_Email='admin+%s@local.vote' % uuid.uuid4().hex[:12],
                )
            messages.success(request, '%s votes added.' % amount)
            return redirect(reverse('core:admin_song_votes', args=[song.id]))

        vote_id = request.POST.get('vote_id')
        vote = Vote.objects.filter(pk=vote_id).first()
        if not vote or str(vote.songs) != str(song.id):
            messages.error(request, 'Vote not found for this song.')
            return redirect(reverse('core:admin_song_votes', args=[song.id]))

        if action == 'update_vote':
            email = (request.POST.get('voter_email') or '').strip()
            if email:
                vote.voter_Email = email
                vote.save(update_fields=['voter_Email'])
                messages.success(request, 'Voter email updated.')
            else:
                messages.error(request, 'Email is required.')
        elif action == 'delete_vote':
            vote.delete()
            messages.success(request, 'Vote removed.')

        return redirect(reverse('core:admin_song_votes', args=[song.id]))

    votes = Vote.objects.filter(songs=str(song.id)).order_by('-id')
    legacy_map, req_map = song_vote_count_maps()
    combined_vote_total = combined_votes_for_song(song.id, legacy_map, req_map)
    return render(
        request,
        'admin_song_votes.html',
        {'song': song, 'votes': votes, 'combined_vote_total': combined_vote_total},
    )

def about(request):
    if request.method == 'POST':
        form = HelpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your message sent successfully')
            return redirect('/')
    else:
        form = HelpForm()

    return render(request, 'songs/aboutus.html', {'form': form})


@login_required
def artist_promo(request):
    """Artist-only: upload leaderboard thumbnail OR short promo video (mutually exclusive)."""
    user = request.user
    if user.user_type == 1:
        messages.warning(request, 'Promo media is for artist accounts.')
        return redirect(reverse('core:home'))

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'clear':
            if user.artist_promo_image:
                user.artist_promo_image.delete(save=False)
                user.artist_promo_image = None
            if user.artist_promo_video:
                user.artist_promo_video.delete(save=False)
                user.artist_promo_video = None
            user.save()
            messages.success(request, 'Promo media removed.')
            return redirect(reverse('core:artist_promo'))

        kind = request.POST.get('promo_kind')
        img = request.FILES.get('promo_image')
        vid = request.FILES.get('promo_video')

        if kind == 'image':
            if not img:
                messages.error(request, 'Choose an image file for your thumbnail.')
                return redirect(reverse('core:artist_promo'))
            if user.artist_promo_video:
                user.artist_promo_video.delete(save=False)
                user.artist_promo_video = None
            if user.artist_promo_image:
                user.artist_promo_image.delete(save=False)
            user.artist_promo_image = img
            user.save()
            messages.success(request, 'Thumbnail saved — it will appear on the leaderboard.')
            return redirect(reverse('core:artist_promo'))

        if kind == 'video':
            if not vid:
                messages.error(request, 'Choose a video file for your promo clip.')
                return redirect(reverse('core:artist_promo'))
            ext_ok = vid.name.lower().endswith(('.mp4', '.webm', '.mov', '.m4v'))
            if not ext_ok:
                messages.error(request, 'Please upload MP4, WebM, MOV, or M4V.')
                return redirect(reverse('core:artist_promo'))
            if user.artist_promo_image:
                user.artist_promo_image.delete(save=False)
                user.artist_promo_image = None
            if user.artist_promo_video:
                user.artist_promo_video.delete(save=False)
            user.artist_promo_video = vid
            user.save()
            messages.success(request, 'Promo video saved — it will appear on the leaderboard.')
            return redirect(reverse('core:artist_promo'))

        messages.error(request, 'Select thumbnail or video and attach the matching file.')
        return redirect(reverse('core:artist_promo'))

    return render(request, 'songs/artist_promo.html')


@login_required
def songUpload(request):
    if request.user.user_type == 1:
        messages.warning(request, 'Administrator accounts cannot upload tracks.')
        return redirect(reverse('core:home'))

    if request.method == 'POST':
        song_title = request.POST['song_title']
        description = request.POST['description']
        song_file = request.FILES.get('song_file')
        thumbnail = request.FILES.get('thumbnail')
        user = request.user
        if not song_file and not thumbnail:
            messages.error(request, 'Upload a video or a thumbnail so the song can be voted.')
            return render(request, 'songs/create.html')

        song = Song.objects.create(
            user=user,
            title=song_title,
            description=description,
            song=song_file,
            thumbnail=thumbnail,
            fallback_song_data_url=_file_to_data_url(song_file, 'video/mp4'),
            fallback_thumbnail_data_url=_file_to_data_url(thumbnail, 'image/jpeg'),
        )

        song.save()
        if song.song and not song.thumbnail:
            ensure_song_thumbnail_from_video(song)
        return redirect('/')
        
    else:
        return render(request, 'songs/create.html')
    

        
@login_required
def update_song(request, id):
  if request.user.user_type == 1:
      messages.warning(request, 'Administrator accounts cannot edit artist uploads.')
      return redirect(reverse('core:home'))
  song = get_object_or_404(Song, id=id, user=request.user)
  if _song_vote_count(song.id) > 0:
      messages.error(request, 'This song already has votes and can no longer be edited.')
      return redirect('/')
  return render(request, 'updatesong.html', {'song': song})


@login_required
def updaterecord(request, id):
    if request.user.user_type == 1:
        messages.warning(request, 'Administrator accounts cannot edit artist uploads.')
        return redirect(reverse('core:home'))
    song = get_object_or_404(Song, id=id, user=request.user)
    if _song_vote_count(song.id) > 0:
        messages.error(request, 'This song already has votes and can no longer be edited.')
        return redirect('/')

    song_title = request.POST['song_title']
    description = request.POST['description']
    song_file = request.FILES.get('song_file')
    thumbnail = request.FILES.get('thumbnail')

    # Keep existing files if none are uploaded; require at least one media.
    next_song_file = song_file if song_file else song.song
    next_thumbnail = thumbnail if thumbnail else song.thumbnail
    if not next_song_file and not next_thumbnail:
        messages.error(request, 'Upload a video or a thumbnail so the song can be voted.')
        return render(request, 'updatesong.html', {'song': song})

    song.title = song_title
    song.description = description
    if song_file:
        song.song = song_file
        song.fallback_song_data_url = _file_to_data_url(song_file, 'video/mp4')
    if thumbnail:
        song.thumbnail = thumbnail
        song.fallback_thumbnail_data_url = _file_to_data_url(thumbnail, 'image/jpeg')
    song.save()
    if song.song and not song.thumbnail:
        ensure_song_thumbnail_from_video(song)
    messages.success(request, 'Song updated successfully.')
    return redirect('/')




@login_required
def delete_song(request, id):
  if request.user.user_type == 1:
      messages.warning(request, 'Administrator accounts cannot delete tracks from this flow.')
      return redirect(reverse('core:home'))
  song = get_object_or_404(Song, id=id, user=request.user)
  song.delete()
  return redirect('/')

def vote_view(request, id):
    return redirect('%s?%s' % (reverse('core:paid_vote_request'), urlencode({'song': id})))


@require_http_methods(['GET', 'POST'])
def paid_vote_request_view(request):
    """Save a pending paid vote package (with payment proof), email the buyer, then show WhatsApp."""
    if request.user.is_authenticated and getattr(request.user, 'user_type', None) == 1:
        messages.info(
            request,
            'Voting checkout is for listeners and artists. Use the administration dashboard for moderation.',
        )
        return redirect(reverse('core:app_administration'))

    site = SiteSettings.get_solo()
    active_packages = VotePackage.objects.filter(is_active=True).order_by('sort_order', 'id')
    get_song = (request.GET.get('song') or '').strip()
    locked_pk = None
    if get_song.isdigit() and Song.objects.filter(pk=int(get_song), status='2').exists():
        locked_pk = int(get_song)

    locked_song = Song.objects.filter(pk=locked_pk, status='2').select_related('user').first() if locked_pk else None

    initial = {}
    if locked_pk:
        initial['song'] = locked_pk

    if request.method == 'POST':
        form = PaidVoteRequestForm(request.POST, request.FILES, fixed_song_pk=locked_pk)
        if form.is_valid():
            vote_request = form.save(commit=False)
            vote_request.status = VoteRequest.Status.PENDING
            vote_request.save()

            digits = ''.join(c for c in getattr(settings, 'WHATSAPP_PAYMENTS_PHONE', '').strip() if c.isdigit())
            if not digits:
                digits = site.whatsapp_payment_digits()

            amt = vote_request.price_amount
            amt_disp = format_price_display(amt) if amt is not None else ''
            cur = (vote_request.currency_code or '').strip()
            if amt is not None:
                amount_bits = ('%s %s for ' % (amt_disp, cur)) if cur else ('%s for ' % amt_disp)
            else:
                amount_bits = ''
            ch = ''
            if vote_request.payment_method:
                ch = ' Paid via %s (%s).' % (
                    vote_request.payment_method_label(),
                    vote_request.payment_method_number(),
                )
            whatsapp_text = (
                'Hi, I am %(email)s. I paid %(amount_bits)s%(package)s (%(votes)s votes) '
                'for "%(title)s". Ref: %(ref)s.%(ch)s I uploaded proof on the site — confirming here.'
            ) % {
                'email': vote_request.email,
                'amount_bits': amount_bits,
                'package': vote_request.package,
                'votes': vote_request.vote_count,
                'title': vote_request.song.title,
                'ref': str(vote_request.transaction_id),
                'ch': ch,
            }
            whatsapp_url = ''
            if digits:
                whatsapp_url = 'https://wa.me/%s?text=%s' % (digits, quote(whatsapp_text))

            pay_plain = _payment_instructions_plain(site)

            subject = '[%s] Vote package request received' % site.site_title
            amount_line = ''
            if amt is not None:
                amount_line = (
                    'Amount due: %s %s\n' % (amt_disp, cur) if cur else 'Amount due: %s\n' % amt_disp
                )
            pay_line = ''
            if vote_request.payment_method:
                pay_line = 'Paid with: %s (%s)\n' % (
                    vote_request.payment_method_label(),
                    vote_request.payment_method_number(),
                )
            body = (
                'Hello,\n\n'
                'We received your vote package request.\n\n'
                'Song: %(song)s\n'
                'Package: %(package)s\n'
                'Votes: %(votes)s\n'
                '%(amount_line)s'
                '%(pay_line)s'
                'Reference: %(ref)s\n\n'
                '--- How to pay ---\n'
                '%(pay)s\n\n'
                '%(wa)s\n\n'
                'Thank you,\n'
                '%(brand)s\n'
            ) % {
                'song': vote_request.song.title,
                'package': vote_request.package,
                'votes': vote_request.vote_count,
                'amount_line': amount_line,
                'pay_line': pay_line,
                'ref': str(vote_request.transaction_id),
                'pay': pay_plain or '(Configure payment numbers under Administration → Site settings.)',
                'wa': ('Optional WhatsApp follow-up: %s' % whatsapp_url)
                if whatsapp_url
                else ('Configure WhatsApp under Administration → Site settings.'),
                'brand': site.site_title,
            }
            body += '\nPayment proof image was attached with this request on the website.\n'
            from_email = site.vote_from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
            try:
                send_mail(subject, body, from_email, [vote_request.email], fail_silently=False)
            except Exception:
                logger.exception('Paid vote request acknowledgement email failed')

            return render(
                request,
                'pending_vote_whatsapp.html',
                {
                    'vote_request': vote_request,
                    'whatsapp_url': whatsapp_url,
                    'site': site,
                    'whatsapp_configured': bool(digits),
                },
            )
    else:
        form = PaidVoteRequestForm(initial=initial, fixed_song_pk=locked_pk)

    return render(
        request,
        'vote_package_request.html',
        {
            'form': form,
            'site': site,
            'vote_packages': active_packages,
            'has_vote_packages': active_packages.exists(),
            'locked_song': locked_song,
        },
    )

@login_required
def accept_video(request, id):
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    publish = Song.objects.get(id=id)
    if request.method == "POST" and publish.status == 1:
        publish.status = 0
        publish.save()
    else:
        publish.status = 1
        publish.save()

    return redirect(reverse('core:song_view'))


@login_required
def publish_video(request, id):
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    publish = Song.objects.get(id=id)
    if request.method == "POST" and publish.status == 2:
        publish.status = 1
        publish.save()
    else:
        publish.status = 2
        publish.save()

    return redirect(reverse('core:song_view'))


@login_required
def reject_video(request, id):
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    publish = Song.objects.get(id=id)
    if request.method == "POST" and publish.status == 3:
        publish.status = 2
        publish.save()
    else:
        publish.status = 3
        publish.save()

    return redirect(reverse('core:song_view'))


def confirm_vote(request, token=0):
    """Confirm vote from email link. Redirects home so messages render on base.html."""
    if request.method != 'GET' or not token or token == '0':
        messages.error(request, 'Invalid confirmation link.')
        return redirect(reverse('core:home'))

    try:
        token_obj = Token.objects.get(user_token=str(token))
    except Token.DoesNotExist:
        messages.error(request, 'Invalid or expired confirmation link.')
        return redirect(reverse('core:home'))

    email = token_obj.user_Email
    song = token_obj.song_id

    if Vote.objects.filter(voter_Email=email).exists():
        messages.warning(request, 'You have already voted.')
        return redirect(reverse('core:home'))

    Vote.objects.create(songs=song, voter_Email=email)
    messages.success(request, 'Your vote has been confirmed.')
    return redirect(reverse('core:home'))

def vote(request):
    if request.method != 'POST':
        return redirect(reverse('core:home'))

    song_id = request.POST['song_id']
    email = request.POST['email']
    site = SiteSettings.get_solo()

    if Vote.objects.filter(voter_Email=email).exists():
        return render(request, 'voteEmail.html', {'error_message': 'You have already voted for this song', 'id': song_id})

    generated_token = uuid.uuid4()
    Token.objects.create(user_token=str(generated_token), user_Email=email, song_id=song_id)

    vote_link = request.build_absolute_uri(reverse('core:confirm_vote', args=[str(generated_token)]))
    subject = site.site_title
    text = (
        "Hello,\n\n"
        "You requested to vote on Sepela Musique.\n"
        "Please confirm your vote using this link:\n\n"
        "{}\n\n"
        "If you did not request this vote, you can ignore this email."
    ).format(vote_link)
    html_message = (
        "<p>Hello,</p>"
        "<p>You requested to vote on Sepela Musique.</p>"
        "<p>Please confirm your vote by clicking the button below:</p>"
        "<p><a href=\"{link}\" "
        "style=\"display:inline-block;padding:10px 16px;background:#2b6cb0;color:#ffffff;"
        "text-decoration:none;border-radius:6px;\">Confirm vote</a></p>"
        "<p>If the button does not work, use this link:</p>"
        "<p><a href=\"{link}\">{link}</a></p>"
        "<p>If you did not request this vote, you can ignore this email.</p>"
    ).format(link=vote_link)
    from_email = site.vote_from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    try:
        send_mail(
            subject,
            text,
            from_email,
            [email],
            fail_silently=False,
            html_message=html_message,
        )
        messages.success(request, 'Check the email to confirm your vote.')
    except Exception:
        logger.exception("Vote confirmation email send failed")
        messages.error(
            request,
            'Could not send confirmation email. Check EMAIL_* settings and try again.',
        )
    return redirect('/')
def contact(request):
    if request.method == 'POST':
        email = request.POST['email']
        subject = request.POST['subject']
        message = request.POST['message']
        contact = Contact.objects.create(email=email, subject=subject, message=message)
        contact.save()

        site = SiteSettings.get_solo()
        from_email = site.contact_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        ack_subject = "{} - Contact received".format(site.site_title)
        ack_text = (
            "Hello,\n\n"
            "We received your message on {}.\n\n"
            "Subject: {}\n"
            "Message:\n{}\n\n"
            "Thank you."
        ).format(site.site_title, subject, message)
        try:
            send_mail(ack_subject, ack_text, from_email, [email], fail_silently=False)
        except Exception:
            pass

        return redirect('/')
        
    else:
        return render(request, 'songs/aboutus.html', {'form': HelpForm()})
    




 

