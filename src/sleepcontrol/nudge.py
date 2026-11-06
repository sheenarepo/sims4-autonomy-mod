"""Makes sure Sims can actually fall asleep on their own during the sleep window.

The game only lets autonomy pick bed sleep when a Sim has one of three hidden
"sleep desire" buffs, which it hands out on a schedule counted back from
the Sim's work start time. During the player's sleep window, for Sims whose
energy is at or below the threshold, we add the game's own invisible
buff_AllowSleepDesire (it has no other effect), and take it away again outside
the window or once energy is back above the threshold.

We only ever remove the buff instances we added ourselves, so the game's own
schedule buffs are untouched.
"""

from sleepcontrol import game_hooks, log, rules
from sleepcontrol.settings import SETTINGS

CHECK_EVERY_SIM_MINUTES = 10
ALLOW_BUFF_NAME = 'buff_AllowSleepDesire'


class _AlarmOwner:
    pass


_owner = _AlarmOwner()
_alarm_handle = None
_allow_buff = None
_handles = {}  # sim_id -> buff handle we added
_diagnosed = False


def _get_allow_buff():
    global _allow_buff
    if _allow_buff is None:
        _allow_buff = game_hooks.find_tuning('BUFF', ALLOW_BUFF_NAME)
        log.write('Sleep-allow buff found: {}'.format(_allow_buff))
    return _allow_buff


def _wants_buff(sim_info, now_minutes):
    if not SETTINGS.enabled or not game_hooks.is_covered_sim(sim_info):
        return False
    energy = game_hooks.get_energy_percent(sim_info)
    if energy is None:
        return False
    allowed, _ = rules.check(rules.SLEEP, now_minutes, energy, SETTINGS.data[rules.SLEEP])
    return allowed


def _remove(sim_info, sim_id):
    handle = _handles.pop(sim_id, None)
    if handle is not None and sim_info is not None:
        try:
            sim_info.remove_buff(handle)
        except Exception:
            log.exception_once('remove_buff', 'removing sleep-allow buff')


def tick(*_):
    try:
        import services
        buff = _get_allow_buff()
        if buff is None:
            return
        now = game_hooks.get_now_minutes()
        seen = set()
        for sim in services.sim_info_manager().instanced_sims_gen():
            sim_info = sim.sim_info
            sim_id = sim_info.sim_id
            seen.add(sim_id)
            if _wants_buff(sim_info, now):
                if sim_id not in _handles:
                    handle = sim_info.add_buff(buff)
                    if handle is not None:
                        _handles[sim_id] = handle
            elif sim_id in _handles:
                _remove(sim_info, sim_id)
        # Sims who left the lot: their buffs go away with them.
        for sim_id in [s for s in _handles if s not in seen]:
            sim_info = services.sim_info_manager().get(sim_id)
            _remove(sim_info, sim_id)
    except Exception:
        log.exception_once('nudge_tick', 'sleep window check')


def start_for_zone():
    """Called each time a lot finishes loading (alarms do not survive travel)."""
    global _alarm_handle
    try:
        import alarms
        import date_and_time
        _handles.clear()
        _alarm_handle = alarms.add_alarm(
            _owner, date_and_time.create_time_span(minutes=1), tick, repeating=True,
            repeating_time_span=date_and_time.create_time_span(minutes=CHECK_EVERY_SIM_MINUTES))
        tick()
    except Exception:
        log.exception('starting sleep window checks')
    global _diagnosed
    if not _diagnosed:
        _diagnosed = True
        from sleepcontrol import commands
        commands.computer_diagnostics()


def refresh():
    """Re-check right away (after the player changes settings)."""
    tick()


def install():
    try:
        from zone import Zone
        original = Zone.on_loading_screen_animation_finished

        def on_loading_screen_animation_finished(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            start_for_zone()
            return result

        on_loading_screen_animation_finished.__wrapped__ = original
        Zone.on_loading_screen_animation_finished = on_loading_screen_animation_finished
        return True
    except Exception:
        log.exception('installing zone hook')
        return False
