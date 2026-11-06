"""The in-game settings menu, laid out like MCCC: a list of settings, each
opening a small menu with "Change" and "Reset to default (value)".
"""

from sleepcontrol import dialogs, nudge, rules, settings
from sleepcontrol.settings import SETTINGS

TITLE = 'Sleep Control'

LABELS = {
    rules.SLEEP: 'Sleep',
    rules.NAP: 'Nap',
}

FIELD_LABELS = {
    'window_start': 'window start',
    'window_end': 'window end',
    'energy_threshold': 'energy threshold',
}


_anchor_id = None


def set_anchor(obj_id):
    """Remember the object the menu was opened from (the slider appears beside it)."""
    global _anchor_id
    _anchor_id = obj_id


def _changed():
    nudge.refresh()


def _value_text(key, value):
    if key == 'energy_threshold':
        return '{}%'.format(value)
    return str(value)


def show_main_menu():
    data = SETTINGS.data
    rows = [(
        'Mod enabled: {}'.format('On' if data['enabled'] else 'Off'),
        'Turn all Sleep Control rules on or off.',
        ('toggle_enabled', None, None),
    )]
    for kind in rules.KINDS:
        block = data[kind]
        rows.append((
            '{} window: {} - {}'.format(LABELS[kind], block['window_start'], block['window_end']),
            'Sims only choose to {} on their own between these times.'.format(kind),
            ('window', kind, None),
        ))
        rows.append((
            '{} energy threshold: {}%'.format(LABELS[kind], block['energy_threshold']),
            'Sims only choose to {} on their own when energy is at or below this.'.format(kind),
            ('setting', kind, 'energy_threshold'),
            dialogs.bar_icon(block['energy_threshold']),
        ))
    rows.append(('Reset everything to defaults', 'Put every setting back to its default.',
                 ('reset_all', None, None)))
    dialogs.show_list(TITLE, 'Choose a setting to change.', rows, _on_main_choice)


def _on_main_choice(choice):
    action, kind, key = choice
    if action == 'toggle_enabled':
        SETTINGS.enabled = not SETTINGS.enabled
        _changed()
        show_main_menu()
    elif action == 'window':
        _show_window_menu(kind)
    elif action == 'setting' and key == 'energy_threshold':
        _ask_value(kind, key, back=show_main_menu)
    elif action == 'setting':
        _show_setting_menu(kind, key, back=show_main_menu)
    elif action == 'reset_all':
        SETTINGS.reset_all()
        _changed()
        dialogs.notify(TITLE, 'All settings reset to defaults.')
        show_main_menu()


def _show_window_menu(kind):
    block = SETTINGS.data[kind]
    rows = [
        ('Start: {}'.format(block['window_start']), 'When the {} window opens.'.format(kind),
         'window_start'),
        ('End: {}'.format(block['window_end']), 'When the {} window closes.'.format(kind),
         'window_end'),
        ('Back', '', 'back'),
    ]

    def _choose(key):
        if key == 'back':
            show_main_menu()
        else:
            _show_setting_menu(kind, key, back=lambda: _show_window_menu(kind))

    dialogs.show_list('{} window'.format(LABELS[kind]),
                      'Use 24-hour time. Sims who are already asleep when the window '
                      'closes keep sleeping.', rows, _choose)


def _show_setting_menu(kind, key, back):
    current = SETTINGS.get(kind, key)
    default = settings.DEFAULTS[kind][key]
    title = '{} {}'.format(LABELS[kind], FIELD_LABELS[key])
    rows = [
        ('Change (now {})'.format(_value_text(key, current)), '', 'change'),
        ('Reset to default ({})'.format(_value_text(key, default)), '', 'reset'),
        ('Back', '', 'back'),
    ]

    def _choose(option):
        if option == 'change':
            _ask_value(kind, key, back)
        elif option == 'reset':
            SETTINGS.reset(kind, key)
            _changed()
            back()
        else:
            back()

    dialogs.show_list(title, '', rows, _choose)


def _ask_value(kind, key, back):
    title = '{} {}'.format(LABELS[kind], FIELD_LABELS[key])
    default = settings.DEFAULTS[kind][key]
    current = SETTINGS.get(kind, key)
    if key == 'energy_threshold':
        prompt = 'Enter a number from 1 to 100 (default {}).'.format(default)
    else:
        prompt = 'Enter a time in 24-hour format, like 22:00 (default {}).'.format(default)

    def _submit(text):
        if key == 'energy_threshold':
            value = rules.clamp_threshold(text)
            if value is None:
                dialogs.notify(TITLE, '"{}" is not a number from 1 to 100.'.format(text))
                return _ask_value(kind, key, back)
        else:
            minutes = rules.parse_time(text)
            if minutes is None:
                dialogs.notify(TITLE, '"{}" is not a time like 22:00.'.format(text))
                return _ask_value(kind, key, back)
            value = rules.format_time(minutes)
        SETTINGS.set(kind, key, value)
        _changed()
        back()

    dialogs.ask_text(title, prompt, current, _submit)
