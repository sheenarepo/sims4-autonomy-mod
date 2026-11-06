"""Tiny file logger: writes SleepControl_Log.txt next to the settings file."""

import os
import time
import traceback

from sleepcontrol import settings

LOG_FILE_NAME = 'SleepControl_Log.txt'
MAX_BYTES = 256 * 1024
_once_keys = set()


def _path():
    return os.path.join(settings.find_mods_folder(), LOG_FILE_NAME)


def write(message):
    try:
        path = _path()
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + '.old')
        with open(path, 'a', encoding='utf-8') as f:
            f.write('{} {}\n'.format(time.strftime('%Y-%m-%d %H:%M:%S'), message))
    except Exception:
        pass


def exception(context):
    write('ERROR in {}:\n{}'.format(context, traceback.format_exc()))


def exception_once(key, context):
    """Log an error only the first time it happens, so a hot code path can't flood the log."""
    if key in _once_keys:
        return
    _once_keys.add(key)
    exception(context)
