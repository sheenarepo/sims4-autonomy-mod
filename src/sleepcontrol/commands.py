"""Cheat-console commands. The computer interaction runs 'sleepcontrol.menu';
the others help with testing (open the cheat console with Ctrl+Shift+C,
or Cmd+Shift+C on a Mac).
"""

import sims4.commands

from sleepcontrol import game_hooks, log, menu, rules
from sleepcontrol.settings import SETTINGS


@sims4.commands.Command('sleepcontrol.menu', command_type=sims4.commands.CommandType.Live)
def open_menu(obj_id: int = None, _connection=None):
    # obj_id is the computer that was clicked; the slider panel is drawn next to it.
    try:
        menu.set_anchor(obj_id)
        menu.show_main_menu()
    except Exception:
        log.exception('opening menu')
        sims4.commands.CheatOutput(_connection)('Sleep Control: could not open menu, see SleepControl_Log.txt')


@sims4.commands.Command('sleepcontrol.status', command_type=sims4.commands.CommandType.Live)
def status(_connection=None):
    out = sims4.commands.CheatOutput(_connection)
    try:
        import services
        out('Sleep Control: hook installed = {}, enabled = {}'.format(
            game_hooks._installed, SETTINGS.enabled))
        now = game_hooks.get_now_minutes()
        out('Game time {}'.format(rules.format_time(now)))
        sim = services.get_active_sim()
        energy = game_hooks.get_energy_percent(sim.sim_info) if sim else None
        if energy is not None:
            out('Active Sim energy {:.0f}%'.format(energy))
        if sim is not None:
            desire = [name for name in ('buff_SmallSleepDesire', 'buff_LargeSleepDesire',
                                        'buff_AllowSleepDesire', 'buff_Nap')
                      if sim.sim_info.has_buff(game_hooks.find_tuning('BUFF', name))]
            out('Sleep/nap buffs: {}'.format(', '.join(desire) or 'none'))
        for kind in rules.KINDS:
            block = SETTINGS.data[kind]
            allowed, reason = rules.check(kind, now, energy, block)
            out('{}: {}-{}, threshold {}% -> {}'.format(
                kind, block['window_start'], block['window_end'], block['energy_threshold'],
                'allowed' if allowed else reason))
    except Exception:
        log.exception('status command')
        out('Sleep Control: status failed, see SleepControl_Log.txt')


@sims4.commands.Command('sleepcontrol.list', command_type=sims4.commands.CommandType.Live)
def list_matched(_connection=None):
    out = sims4.commands.CheatOutput(_connection)
    try:
        found = game_hooks.matched_affordances()
        for kind, names in found.items():
            log.write('{} interactions ({}): {}'.format(kind, len(names), ', '.join(names)))
            out('{}: {} interactions (full list in SleepControl_Log.txt)'.format(kind, len(names)))
        from sleepcontrol import computer
        log.write('Computer menu interaction ID: {}'.format(computer.MENU_INTERACTION_ID))
    except Exception:
        log.exception('list command')


@sims4.commands.Command('sleepcontrol.diag', command_type=sims4.commands.CommandType.Live)
def diag_command(_connection=None):
    out = sims4.commands.CheatOutput(_connection)
    if computer_diagnostics():
        out('Sleep Control: details written to SleepControl_Log.txt')
    else:
        out('Sleep Control: diagnostics failed, see SleepControl_Log.txt')


def computer_diagnostics():
    """Log, for each computer on the lot, whether the menu entry is offered and why not."""
    try:
        import services
        import sims4.resources
        from interactions.context import InteractionContext
        from interactions.priority import Priority
        from sleepcontrol import computer
        affordance = services.get_instance_manager(sims4.resources.Types.INTERACTION).get(
            computer.MENU_INTERACTION_ID)
        sim = services.get_active_sim()
        context = InteractionContext(sim, InteractionContext.SOURCE_PIE_MENU, Priority.High)
        log.write('DIAG: affordance={} allow_user_directed={} visible={} has_display_name={}'.format(
            affordance, getattr(affordance, 'allow_user_directed', None),
            getattr(affordance, 'visible', None), bool(getattr(affordance, 'display_name', None))))
        for obj in list(services.object_manager().get_all()):
            if not computer.is_computer(type(obj)):
                continue
            lines = ['DIAG: object {} ({})'.format(type(obj).__name__, obj.id)]
            lines.append('  in tuning: {}'.format(affordance in type(obj)._super_affordances))
            try:
                lines.append('  available: {}'.format(affordance.is_affordance_available(context=context)))
            except Exception as exc:
                lines.append('  available: error {!r}'.format(exc))
            lines.append('  in super_affordances: {}'.format(affordance in list(obj.super_affordances(context))))
            parts = getattr(obj, 'parts', None) or ()
            lines.append('  parts: {}'.format([type(p).__name__ for p in parts]))
            for target in [obj] + list(parts):
                try:
                    lines.append('  supports on {}: {}'.format(target, target.supports_affordance(affordance)))
                except Exception as exc:
                    lines.append('  supports on {}: error {!r}'.format(target, exc))
                try:
                    result = affordance.test(target=target, context=context)
                    lines.append('  test on {}: {} {}'.format(target, bool(result), getattr(result, 'reason', '')))
                except Exception as exc:
                    lines.append('  test on {}: error {!r}'.format(target, exc))
                try:
                    names = [aop.affordance.__name__ for aop in target.potential_interactions(context)]
                    lines.append('  offered on {}: {} ({} total)'.format(
                        target, affordance.__name__ in names, len(names)))
                except Exception as exc:
                    lines.append('  offered on {}: error {!r}'.format(target, exc))
            log.write('\n'.join(lines))
        return True
    except Exception:
        log.exception('computer diagnostics')
        return False


@sims4.commands.Command('sleepcontrol.reload', command_type=sims4.commands.CommandType.Live)
def reload_settings(_connection=None):
    SETTINGS.load()
    sims4.commands.CheatOutput(_connection)('Sleep Control: settings reloaded from file')
