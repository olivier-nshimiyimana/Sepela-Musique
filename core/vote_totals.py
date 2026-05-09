"""Combine legacy per-row votes (Vote) with approved paid bundles (VoteRequest)."""

from django.db.models import Count, Sum

from .models import Vote, VoteRequest


def legacy_vote_rows_per_song():
    rows = Vote.objects.values('songs').annotate(votes=Count('id'))
    return {str(r['songs']): r['votes'] for r in rows}


def approved_vote_request_sum_per_song():
    rows = (
        VoteRequest.objects.filter(status=VoteRequest.Status.APPROVED)
        .values('song_id')
        .annotate(votes=Sum('vote_count'))
    )
    return {r['song_id']: r['votes'] or 0 for r in rows}


def song_vote_count_maps():
    return legacy_vote_rows_per_song(), approved_vote_request_sum_per_song()


def combined_votes_for_song(song_id, legacy_map=None, request_map=None):
    """Total displayed votes for one song (email confirmations + approved paid bundles)."""
    if legacy_map is None or request_map is None:
        legacy_map, request_map = song_vote_count_maps()
    sid = int(song_id)
    return legacy_map.get(str(sid), 0) + request_map.get(sid, 0)


def total_vote_units_dashboard():
    """Approximate site-wide vote units for admin dashboard metrics."""
    legacy = Vote.objects.count()
    bundle = (
        VoteRequest.objects.filter(status=VoteRequest.Status.APPROVED).aggregate(
            t=Sum('vote_count')
        )['t']
        or 0
    )
    return legacy + bundle
