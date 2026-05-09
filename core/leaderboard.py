from collections import defaultdict

from django.db.models import Sum
from django.db.utils import OperationalError, ProgrammingError

from accounts.models import User

from .models import Song, VoteRequest


def top_artists_by_votes(limit=10, published_status='2'):
    """
    Rank artists by votes on published songs using Sum(vote_count) on approved
    VoteRequest rows only (not legacy Vote row counts).
    """
    try:
        bundle_rows = (
            VoteRequest.objects.filter(status=VoteRequest.Status.APPROVED)
            .values('song_id')
            .annotate(votes=Sum('vote_count'))
        )
        bundle_map = {r['song_id']: r['votes'] or 0 for r in bundle_rows}
    except (OperationalError, ProgrammingError):
        # On first deploy (before migrations), avoid crashing homepage health checks.
        return []

    artist_totals = defaultdict(int)
    for song in Song.objects.filter(status=published_status).only('id', 'user_id'):
        sid = song.id
        artist_totals[song.user_id] += bundle_map.get(sid, 0)

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
