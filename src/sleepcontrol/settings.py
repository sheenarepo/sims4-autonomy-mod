"""Loading, saving and validating Sleep Control settings.

Settings are global (shared by every save) and live in a JSON file next to
the mod in the Mods folder. Changes made in the in-game menu take effect
immediately; no restart needed.
"""

import copy
import json
import os

from sleepcontrol import rules

SETTINGS_FILE_NAME = 'SleepControl_Settings.json'
SETTINGS_VERSION = 1

# Threshold default matches the game: the energy need only starts asking for
# sleep at -25 on its -100..100 scale (37.5%), so 38% changes nothing by itself.
DEFAULTS = {
    'version': SETTINGS_VERSION,
    'enabled': True,
    rules.SLEEP: {
        'window_start': '22:00',
        'window_end': '06:00',
        'energy_threshold': 38,
    },
    rules.NAP: {
        'window_start': '15:00',
        'window_end': '16:00',
        'energy_threshold': 38,
    },
}


def find_mods_folder(start_path=None):
    """Find the Mods folder from wherever this script is loaded.

    Inside a .ts4script archive __file__ looks like
    .../Mods/SleepControl.ts4script/sleepcontrol/settings.pyc, and for loose
    development scripts it is .../Mods/SleepControl/Scripts/sleepcontrol/settings.py.
    """
    path = os.path.abspath(start_path or __file__)
    probe = path
    while True:
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        if probe.lower().endswith('.ts4script'):
            return parent
        if os.path.basename(parent).lower() == 'mods':
            return parent
        probe = parent
    # Last resort: two levels above this package.
    return os.path.dirname(os.path.dirname(os.path.dirname(path)))


def settings_path():
    return os.path.join(find_mods_folder(), SETTINGS_FILE_NAME)


def _valid_kind_block(block, default_block):
    result = copy.deepcopy(default_block)
    if not isinstance(block, dict):
        return result
    for key in ('window_start', 'window_end'):
        minutes = rules.parse_time(block.get(key))
        if minutes is not None:
            result[key] = rules.format_time(minutes)
    threshold = rules.clamp_threshold(block.get('energy_threshold'))
    if threshold is not None:
        result['energy_threshold'] = threshold
    return result


def validate(raw):
    """Return a clean settings dict, filling anything missing or invalid with defaults."""
    clean = copy.deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        return clean
    if isinstance(raw.get('enabled'), bool):
        clean['enabled'] = raw['enabled']
    for kind in rules.KINDS:
        clean[kind] = _valid_kind_block(raw.get(kind), DEFAULTS[kind])
    return clean


class Settings:
    def __init__(self, path=None):
        self._path = path
        self.data = copy.deepcopy(DEFAULTS)
        self.last_error = None

    @property
    def path(self):
        return self._path or settings_path()

    def load(self):
        self.last_error = None
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                self.data = validate(json.load(f))
        except FileNotFoundError:
            self.data = copy.deepcopy(DEFAULTS)
            self.save()
        except Exception as exc:  # corrupt file: fall back to defaults, keep a backup
            self.last_error = exc
            try:
                os.replace(self.path, self.path + '.broken')
            except Exception:
                pass
            self.data = copy.deepcopy(DEFAULTS)
            self.save()
        return self.data

    def save(self):
        tmp = self.path + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
            return True
        except Exception as exc:
            self.last_error = exc
            return False

    # Convenience accessors used by the menu
    def get(self, kind, key):
        return self.data[kind][key]

    def set(self, kind, key, value):
        block = dict(self.data[kind])
        block[key] = value
        self.data[kind] = _valid_kind_block(block, self.data[kind])
        return self.save()

    def reset(self, kind, key):
        return self.set(kind, key, DEFAULTS[kind][key])

    def reset_all(self):
        self.data = copy.deepcopy(DEFAULTS)
        return self.save()

    @property
    def enabled(self):
        return self.data['enabled']

    @enabled.setter
    def enabled(self, value):
        self.data['enabled'] = bool(value)
        self.save()


SETTINGS = Settings()
