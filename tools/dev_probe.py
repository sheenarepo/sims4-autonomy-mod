# Run inside the game with: sleepcontrol.dev  (copied to Mods/SleepControl_dev.txt)
import services
import sims4.resources
from sleepcontrol import computer

objs = list(services.object_manager().get_all())
log.write('PROBE: {} objects in object manager'.format(len(objs)))
aff = services.get_instance_manager(sims4.resources.Types.INTERACTION).get(computer.MENU_INTERACTION_ID)
seen = {}
for obj in objs:
    t = type(obj)
    name = t.__name__
    sa = getattr(t, '_super_affordances', ()) or ()
    browse = any(getattr(a, '__name__', '') == 'computer_Browse_Web' for a in sa)
    if 'comp' in name.lower() or browse or 'laptop' in name.lower():
        seen[name] = (browse, aff in sa, computer.is_computer(t), t.__mro__[1].__name__, getattr(t, 'guid64', None))
for name, info in sorted(seen.items()):
    log.write('PROBE: {} browse={} has_menu={} is_computer={} base={} guid={}'.format(name, *info))
sample = sorted({type(o).__name__ for o in objs})[:80]
log.write('PROBE: sample types: {}'.format(', '.join(sample)))
out('probe done: {} objects, {} computer-like'.format(len(objs), len(seen)))
