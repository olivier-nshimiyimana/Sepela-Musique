from django import template

from ..formatting import format_price_display

register = template.Library()


@register.filter(name='price_plain')
def price_plain(value):
    return format_price_display(value)
