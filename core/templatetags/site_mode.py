"""
Optional helpers when you prefer a tag over repeated {% if SITE_MODE == 'MISS_KATANGA %}.

Usage:
  {% load site_mode %}
  {% site_word 'artist' %}   → Candidate or Artist (by mode + LANGUAGE_CODE)
"""
from django import template

register = template.Library()

# (logical_key, mode_value) -> {lang: label}
_LEX = {
    ("artist", "MISS_KATANGA"): {"fr": "Candidate", "en": "Candidate"},
    ("artist", "ART_COMPETITION"): {"fr": "Artiste", "en": "Artist"},
    ("song", "MISS_KATANGA"): {"fr": "Candidate", "en": "Contestant"},
    ("song", "ART_COMPETITION"): {"fr": "Morceau", "en": "Song"},
    ("music_media", "MISS_KATANGA"): {"fr": "Photo / video de la candidate", "en": "Contestant photo / video"},
    ("music_media", "ART_COMPETITION"): {"fr": "Musique / video", "en": "Music / video"},
}


@register.simple_tag(takes_context=True)
def site_word(context, key):
    lang = (context.get("LANGUAGE_CODE") or "fr").split("-")[0].lower()
    mode = context.get("SITE_MODE") or "ART_COMPETITION"
    row = _LEX.get((key, mode)) or _LEX.get((key, "ART_COMPETITION"))
    if not row:
        return key
    return row.get(lang) or row.get("fr") or key
