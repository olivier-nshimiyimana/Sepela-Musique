from collections import defaultdict

from django.db.models import Count
from django.db.utils import OperationalError, ProgrammingError

from accounts.models import User

from .models import Song, Vote


def top_artists_by_votes(limit=10, published_status='2'):
    """
    Rank artists by total confirmed votes on published songs.
    Vote.songs stores song id as text; only votes tied to published songs count.
    """
    try:
        rows = Vote.objects.values('songs').annotate(votes=Count('id'))
        song_votes = {str(r['songs']): r['votes'] for r in rows}
    except (OperationalError, ProgrammingError):
        # On first deploy (before migrations), avoid crashing homepage health checks.
        return []

    artist_totals = defaultdict(int)
    for song in Song.objects.filter(status=published_status).only('id', 'user_id'):
        artist_totals[song.user_id] += song_votes.get(str(song.id), 0)

    if not artist_totals:
        return []

    ordered_ids = sorted(artist_totals.keys(), key=lambda uid: artist_totals[uid], reverse=True)[:limit]
    users = {u.id: u for u in User.objects.filter(pk__in=ordered_ids)}
    out = []
    for rank, uid in enumerate(ordered_ids, start=1):
        artist = users.get(uid)
        if artist:
            out.append({'rank': rank, 'artist': artist, 'vote_count': artist_totals[uid]})
    return out
