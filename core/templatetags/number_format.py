from django import template

from ..formatting import format_compact_int

register = template.Library()


@register.filter(name='compact_count')
def compact_count(value):
    return format_compact_int(value)
