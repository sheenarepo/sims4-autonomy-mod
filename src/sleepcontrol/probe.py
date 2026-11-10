"""Read-only probe: lists the attributes of the active Sim's interaction queue.

Run 'sleepcontrol.probe_queue' in the cheat console. It changes nothing in the
game. The output goes to SleepControl_Log.txt so the queue API can be read
before the queued-sleep feature is written.
"""

import services
import sims4.commands

from sleepcontrol import log


@sims4.commands.Command('sleepcontrol.probe_queue', command_type=sims4.commands.CommandType.Live)
def probe_queue(_connection=None):
    out = sims4.commands.CheatOutput(_connection)
    try:
        sim = services.get_active_sim()
        if sim is None:
            out('Sleep Control probe: no active Sim')
            return
        lines = ['PROBE: active sim {}'.format(sim)]
        queue = getattr(sim, 'queue', None)
        for label, obj in (('sim', sim), ('sim.queue', queue)):
            if obj is None:
                lines.append('PROBE: {} is None'.format(label))
                continue
            names = sorted(n for n in dir(obj) if not n.startswith('__'))
            lines.append('PROBE: {} type {}'.format(label, type(obj).__name__))
            lines.append('PROBE: {} members: {}'.format(label, ', '.join(names)))
        if queue is not None:
            try:
                lines.append('PROBE: queue length {}'.format(len(queue)))
            except Exception as exc:
                lines.append('PROBE: queue length error {!r}'.format(exc))
        log.write('\n'.join(lines))
        out('Sleep Control probe written to SleepControl_Log.txt')
    except Exception:
        log.exception('probe queue')
        out('Sleep Control probe failed, see SleepControl_Log.txt')
