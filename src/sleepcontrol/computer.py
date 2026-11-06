"""Adds the 'Sleep Control' interaction to every computer object.

The interaction itself is defined in SleepControl.package (built by
tools/build.py). Its tuning ID is derived from the same name in both places,
so they always match.

A "computer" is any object that offers the game's own Browse Web interaction
(this covers desktops and laptops from every pack), plus objects whose tuning
name says computer or laptop.
"""

from sleepcontrol import log

MENU_INTERACTION_NAME = 'SleepControl:Computer_OpenSettings'
COMPUTER_MARKER_AFFORDANCE = 'computer_Browse_Web'

# Note: never exclude 'desk' - it would also match desktop computers
# (object_computerDesktopMED_01).
_EXCLUDE_WORDS = ('chair', 'table', 'stool', 'shelf', 'rug', 'poster', 'painting')
_computer_types = set()


def fnv64(text):
    h = 0xCBF29CE484222325
    for byte in text.lower().encode('utf-8'):
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        h ^= byte
    return h


def tuning_id(name):
    return fnv64(name) | 0x8000000000000000


MENU_INTERACTION_ID = tuning_id(MENU_INTERACTION_NAME)


def _name_says_computer(object_tuning):
    name = object_tuning.__name__.lower()
    if not name.startswith('object_'):
        return False
    return ('computer' in name or 'laptop' in name) and not any(word in name for word in _EXCLUDE_WORDS)


def is_computer(object_tuning):
    return object_tuning in _computer_types or _name_says_computer(object_tuning)


def _on_objects_loaded(manager):
    try:
        import services
        import sims4.resources
        interactions = services.get_instance_manager(sims4.resources.Types.INTERACTION)
        affordance = interactions.get(MENU_INTERACTION_ID)
        if affordance is None:
            log.write('Computer menu interaction not found: is SleepControl.package in Mods?')
            return
        marker = None
        for candidate in interactions.types.values():
            if candidate.__name__ == COMPUTER_MARKER_AFFORDANCE:
                marker = candidate
                break
        added = []
        for object_tuning in manager.types.values():
            current = getattr(object_tuning, '_super_affordances', None)
            if current is None:
                continue
            if not ((marker is not None and marker in current) or _name_says_computer(object_tuning)):
                continue
            _computer_types.add(object_tuning)
            if affordance in current:
                continue
            object_tuning._super_affordances = tuple(current) + (affordance,)
            added.append(object_tuning.__name__)
        log.write('Computer menu added to {} objects (marker {}): {}'.format(
            len(added), marker, ', '.join(sorted(added))))
    except Exception:
        log.exception('adding computer menu')


def install():
    try:
        import services
        import sims4.resources
        services.get_instance_manager(sims4.resources.Types.OBJECT).add_on_load_complete(
            _on_objects_loaded)
        return True
    except Exception:
        log.exception('registering computer menu')
        return False
