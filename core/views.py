import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User

from .forms import HelpForm
from .leaderboard import top_artists_by_votes
from .models import Contact, SiteSettings, Song, Token, Vote
from .video_thumbnails import ensure_song_thumbnail_from_video


def _song_vote_count(song_id):
    return Vote.objects.filter(songs=str(song_id)).count()


def _home_songs_with_votes(queryset, ascending_by_votes=True):
    """Materialize queryset, attach .votes, sort by vote count (default: ascending)."""
    songs = list(queryset)
    for song in songs:
        song.votes = _song_vote_count(song.id)
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
            .filter(Q(song__isnull=False) | Q(thumbnail__isnull=False))
            .select_related('user')
        )

        for song in songs:
            votes = Vote.objects.filter(songs=song.id)
            if votes.exists():
                song.votes = votes.first().count_votes
            else:
                song.votes = 0
        return render(request, "home.html", {'songs': songs, 'leaderboard': leaderboard})
    if request.user.user_type == 1:
        uploads = User.objects.filter(user_type=2).count()
        total_songs = Song.objects.count()
        total_votes = Vote.objects.count()
        total_contacts = Contact.objects.count()
        recent_songs = Song.objects.select_related('user').order_by('-id')[:8]
        recent_votes = Vote.objects.order_by('-id')[:10]
        recent_contacts = Contact.objects.order_by('-id')[:8]
        site_settings = SiteSettings.get_solo()
        _enrich_admin_dashboard_lists(recent_songs, recent_votes)
        return render(
            request,
            "admin_dashboard_modern.html",
            {
                'uploads': uploads,
                'total_songs': total_songs,
                'total_votes': total_votes,
                'total_contacts': total_contacts,
                'recent_songs': recent_songs,
                'recent_votes': recent_votes,
                'recent_contacts': recent_contacts,
                'site_settings': site_settings,
            },
        )
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
    vote_counts = {row['songs']: row['cnt'] for row in Vote.objects.values('songs').annotate(cnt=Count('id'))}
    for song in songs:
        song.votes = vote_counts.get(str(song.id), 0)

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
    song_vote_counts = {row['songs']: row['cnt'] for row in Vote.objects.values('songs').annotate(cnt=Count('id'))}
    for song in recent_songs:
        song.votes = song_vote_counts.get(str(song.id), 0)
    song_title_map = {str(s.id): s.title for s in Song.objects.only('id', 'title')}
    for vote in recent_votes:
        vote.song_title = song_title_map.get(str(vote.songs), 'Unknown song')


def _admin_dashboard_context():
    uploads = User.objects.filter(user_type=2).count()
    total_songs = Song.objects.count()
    total_votes = Vote.objects.count()
    total_contacts = Contact.objects.count()
    recent_songs = Song.objects.select_related('user').order_by('-id')[:12]
    recent_votes = Vote.objects.order_by('-id')[:12]
    recent_contacts = Contact.objects.order_by('-id')[:8]
    site_settings = SiteSettings.get_solo()

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
    }


@login_required
def app_administration(request):
    if request.user.user_type != 1:
        messages.error(request, 'Only administration users can access this page.')
        return redirect(reverse('core:home'))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_site_settings':
            site = SiteSettings.get_solo()
            site.site_title = request.POST.get('site_title', site.site_title).strip() or site.site_title
            site.contact_email = request.POST.get('contact_email', site.contact_email).strip() or site.contact_email
            site.contact_phone = request.POST.get('contact_phone', '').strip()
            site.contact_address = request.POST.get('contact_address', '').strip()
            site.vote_from_email = request.POST.get('vote_from_email', site.vote_from_email).strip() or site.vote_from_email
            site.save()
            messages.success(request, 'Site settings updated.')
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

    return render(request, "admin_dashboard_modern.html", _admin_dashboard_context())


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
    return render(request, 'admin_song_votes.html', {'song': song, 'votes': votes})

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
        )

        song.save()
        if song.song and not song.thumbnail:
            ensure_song_thumbnail_from_video(song)
        print('song inserted')
        return redirect('/')
        
    else:
        return render(request, 'songs/create.html')
    

        
@login_required
def update_song(request, id):
  song = get_object_or_404(Song, id=id, user=request.user)
  if _song_vote_count(song.id) > 0:
      messages.error(request, 'This song already has votes and can no longer be edited.')
      return redirect('/')
  return render(request, 'updatesong.html', {'song': song})


@login_required
def updaterecord(request, id):
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
    if thumbnail:
        song.thumbnail = thumbnail
    song.save()
    if song.song and not song.thumbnail:
        ensure_song_thumbnail_from_video(song)
    print('song updated')
    messages.success(request, 'Song updated successfully.')
    return redirect('/')




@login_required
def delete_song(request, id):
  song = get_object_or_404(Song, id=id, user=request.user)
  song.delete()
  return redirect('/')

def vote_view(request, id):
    return render(request, 'voteEmail.html', {'id': id})

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
    from_email = site.vote_from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    try:
        send_mail(subject, text, from_email, [email], fail_silently=False)
        messages.success(request, 'Check the email to confirm your vote.')
    except Exception:
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
    




 

