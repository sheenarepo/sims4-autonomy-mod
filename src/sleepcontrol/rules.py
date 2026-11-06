"""Pure decision logic for Sleep Control.

Nothing in this file imports game modules, so it can be unit tested
outside The Sims 4.
"""

SLEEP = 'sleep'
NAP = 'nap'
KINDS = (SLEEP, NAP)

MINUTES_PER_DAY = 24 * 60


def parse_time(text):
    """Turn '22', '22:30', '7', '07:05' or '22.30' into minutes after midnight.

    Returns None when the text is not a valid time. '24:00' is accepted
    and treated as midnight (0).
    """
    if text is None:
        return None
    text = str(text).strip().replace('.', ':').replace('h', ':')
    if not text:
        return None
    parts = text.split(':')
    if len(parts) > 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) == 2 and parts[1] != '' else 0
    except ValueError:
        return None
    if hour == 24 and minute == 0:
        return 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def format_time(minutes):
    minutes = int(minutes) % MINUTES_PER_DAY
    return '{:02d}:{:02d}'.format(minutes // 60, minutes % 60)


def in_window(now_minutes, start_minutes, end_minutes):
    """True when now is inside [start, end).

    Windows may cross midnight (22:00 -> 06:00). A window whose start equals
    its end means "all day".
    """
    now = now_minutes % MINUTES_PER_DAY
    start = start_minutes % MINUTES_PER_DAY
    end = end_minutes % MINUTES_PER_DAY
    if start == end:
        return True
    if start < end:
        return start <= now < end
    return now >= start or now < end


def energy_percent(value, min_value, max_value):
    """Convert a raw energy commodity value (the game uses -100..100) to 0..100."""
    span = float(max_value) - float(min_value)
    if span <= 0:
        return None
    pct = (float(value) - float(min_value)) / span * 100.0
    return max(0.0, min(100.0, pct))


def clamp_threshold(value):
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if value < 1 or value > 100:
        return None
    return value


def check(kind, now_minutes, energy_pct, kind_settings):
    """Decide whether an autonomous sleep or nap may start.

    kind_settings is the 'sleep' or 'nap' block of the settings:
        {'window_start': '22:00', 'window_end': '06:00', 'energy_threshold': 30}

    energy_pct may be None when the Sim has no readable energy need; in that
    case only the time window applies.

    Returns (allowed, reason).
    """
    start = parse_time(kind_settings.get('window_start'))
    end = parse_time(kind_settings.get('window_end'))
    if start is not None and end is not None:
        if not in_window(now_minutes, start, end):
            return False, 'SleepControl: outside {} window {}-{}'.format(
                kind, format_time(start), format_time(end))
    threshold = clamp_threshold(kind_settings.get('energy_threshold'))
    if threshold is not None and energy_pct is not None:
        if energy_pct > threshold:
            return False, 'SleepControl: energy {:.0f}% above {} threshold {}%'.format(
                energy_pct, kind, threshold)
    return True, ''
