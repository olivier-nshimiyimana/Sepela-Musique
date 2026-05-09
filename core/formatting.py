"""Display helpers (money, etc.)."""
from decimal import Decimal, InvalidOperation


def format_price_display(value):
    """
    Render a numeric amount without redundant trailing zeros (e.g. 5000 instead of 5000.00).
    """
    if value is None or value == '':
        return ''
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    s = format(d, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def format_compact_int(value):
    """
    Short display for large integers on cards (e.g. 1500 → 1.5K, 2_000_000 → 2M).
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)

    sign = '-' if n < 0 else ''
    n = abs(n)
    if n < 1000:
        return sign + str(n)
    if n < 1_000_000:
        if n % 1000 == 0:
            return sign + '%dK' % (n // 1000)
        x = n / 1000.0
        return sign + ('%.1fK' % x).replace('.0K', 'K')
    if n % 1_000_000 == 0:
        return sign + '%dM' % (n // 1_000_000)
    x = n / 1_000_000.0
    return sign + ('%.1fM' % x).replace('.0M', 'M')
