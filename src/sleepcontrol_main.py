"""Entry point the game imports when it loads SleepControl.ts4script."""

try:
    import sleepcontrol
    sleepcontrol.start()
except Exception:
    try:
        from sleepcontrol import log
        log.exception('starting Sleep Control')
    except Exception:
        pass
