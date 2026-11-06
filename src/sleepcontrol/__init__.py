"""Sleep Control: limits when Sims choose to sleep and nap on their own."""

VERSION = '0.1.0'


def start():
    from sleepcontrol import log, settings, game_hooks, nudge, computer, commands  # noqa: F401
    settings.SETTINGS.load()
    log.write('Sleep Control {} starting, settings at {}'.format(VERSION, settings.SETTINGS.path))
    if settings.SETTINGS.last_error is not None:
        log.write('Settings file was unreadable ({}); defaults restored, old file kept as .broken'.format(
            settings.SETTINGS.last_error))
    game_hooks.install()
    nudge.install()
    computer.install()
