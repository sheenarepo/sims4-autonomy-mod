"""Runs the whole mod against stand-in game modules whose names and signatures
mirror the real ones (checked against the decompiled game, patch 1.128.90)."""

import enum
import os
import sys
import tempfile
import types
import unittest

SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
MODS = tempfile.mkdtemp()


def module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    parent, _, child = name.rpartition('.')
    if parent:
        if parent not in sys.modules:
            module(parent)
        setattr(sys.modules[parent], child, mod)
    return mod


# --- game stand-ins ----------------------------------------------------------

class TestResult:
    TRUE = None

    def __init__(self, result, *args, tooltip=None, icon=None, influence_by_active_mood=False):
        self.result = result
        self.reason = args[0] if args else None

    def __bool__(self):
        return self.result


TestResult.TRUE = TestResult(True)


class InteractionSource(enum.Enum):
    PIE_MENU = 0
    AUTONOMY = 1
    SCRIPT = 2


class InteractionContext:
    SOURCE_PIE_MENU = InteractionSource.PIE_MENU
    SOURCE_AUTONOMY = InteractionSource.AUTONOMY
    SOURCE_SCRIPT = InteractionSource.SCRIPT

    def __init__(self, sim, source, priority=None, **kwargs):
        self.sim = sim
        self.source = source


class SuperInteraction:
    original_calls = 0

    @classmethod
    def _test(cls, target, context, **interaction_parameters):
        SuperInteraction.original_calls += 1
        return TestResult.TRUE


def make_affordance(name):
    return type(name, (SuperInteraction,), {'allow_autonomous': True})


class Age(enum.IntEnum):
    BABY = 1
    TODDLER = 2
    CHILD = 4
    ADULT = 32
    INFANT = 128


class Species(enum.IntEnum):
    HUMAN = 1
    DOG = 2


class Tuning:
    def __init__(self, name):
        self.__name__ = name


Commodity = type('motive_Energy', (), {'max_value': 100, 'min_value_tuning': -100})


class EnergyStat:
    def __init__(self, value):
        self.value = value
        self.min_value = -100
        self.max_value = 100

    def get_value(self):
        return self.value


class Tracker:
    def __init__(self, value):
        self.stat = EnergyStat(value)

    def get_statistic(self, stat_type, add=False):
        return self.stat if stat_type is Commodity else None


class SimInfo:
    _next = 1

    def __init__(self, energy_pct, age=Age.ADULT, species=Species.HUMAN):
        self.sim_id = SimInfo._next
        SimInfo._next += 1
        self.age = age
        self.species = species
        self.commodity_tracker = Tracker(energy_pct * 2 - 100)
        self.buffs = {}

    def add_buff(self, buff_type, buff_reason=None, **kwargs):
        handle = len(self.buffs) + 100
        self.buffs[handle] = buff_type
        return handle

    def remove_buff(self, handle_id, update_mood=True, immediate=False, on_destroy=False):
        self.buffs.pop(handle_id, None)

    def has_buff(self, buff_type):
        return buff_type in self.buffs.values()


class Sim:
    def __init__(self, sim_info):
        self.sim_info = sim_info


class Clock:
    minutes = 14 * 60

    def hour(self):
        return Clock.minutes // 60

    def minute(self):
        return Clock.minutes % 60


class Manager:
    def __init__(self, tunings):
        self.types = {i: t for i, t in enumerate(tunings)}
        self.by_id = {}
        self.callbacks = []

    def get(self, key):
        return self.by_id.get(key)

    def add_on_load_complete(self, callback):
        self.callbacks.append(callback)


AFFORDANCES = [make_affordance(n) for n in (
    'bed_Autonomous_SingleBed_Sleep', 'sofa_Nap', 'bed_sleep', 'fridge_Grab', 'newObject_Sleep')]
ALLOW_BUFF = Tuning('buff_AllowSleepDesire')
OBJECTS = []
for name in ('object_Computer', 'object_computerLOW_01', 'object_Laptop_EP01', 'object_ComputerChair', 'object_Bed',
             'object_computerDesktopMED_01'):
    obj = Tuning(name)
    obj._super_affordances = ()
    OBJECTS.append(obj)

MANAGERS = {
    'STATISTIC': Manager([Commodity]),
    'BUFF': Manager([ALLOW_BUFF, Tuning('buff_SmallSleepDesire')]),
    'INTERACTION': Manager(AFFORDANCES),
    'OBJECT': Manager(OBJECTS),
}

SIMS = []
SHOWN = []
COMMANDS = {}
ALARMS = []
CAMERA = []


class Dialog:
    def __init__(self, kind, owner, kwargs):
        self.kind = kind
        self.owner = owner
        self.kwargs = kwargs
        self.rows = []
        self.listeners = []
        self.accepted = False
        self.text_input_responses = {}
        self.picked = None

    def add_row(self, row):
        self.rows.append(row)

    def add_listener(self, cb):
        self.listeners.append(cb)

    def show_dialog(self, **kwargs):
        SHOWN.append(self)

    def get_single_result_tag(self):
        return self.picked

    # helpers for the tests
    def choose(self, index):
        self.accepted = True
        self.picked = self.rows[index].tag
        for cb in self.listeners:
            cb(self)

    def type_text(self, text):
        assert 'value' in self.kwargs['text_inputs'] and hasattr(self.kwargs['text_inputs'], 'value')
        self.accepted = True
        self.text_input_responses['value'] = text
        for cb in self.listeners:
            cb(self)


def factory(kind, allowed):
    class F:
        def __init__(self, **factory_kwargs):
            if kind == 'text':
                assert factory_kwargs == {'text_inputs': ('value',)}

        def default(self, owner, **kwargs):
            unknown = set(kwargs) - allowed
            assert not unknown, unknown
            for key in ('text', 'title'):
                assert callable(kwargs[key])
            return Dialog(kind, owner, kwargs)
    return lambda **kw: F(**kw)


class UiObjectPicker:
    class UiObjectPickerObjectPickerType(enum.IntEnum):
        OBJECT = 1
    TunableFactory = staticmethod(factory('list', {'text', 'title', 'min_selectable', 'picker_type'}))


class ObjectPickerRow:
    def __init__(self, option_id=None, name=None, row_description=None, tag=None, **kwargs):
        self.option_id = option_id
        self.name = name
        self.row_description = row_description
        self.tag = tag


class UiDialogTextInputOkCancel:
    TunableFactory = staticmethod(factory('text', {'text', 'title', 'text_inputs'}))


class UiDialogNotification:
    TunableFactory = staticmethod(factory('notice', {'text', 'title'}))


class UiTextInput:
    def __init__(self, *args, sort_order, **kwargs):
        self.sort_order = sort_order


class _TextInputLengthFixed:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class AttributeDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class Zone:
    def on_loading_screen_animation_finished(self):
        return 'zone-loaded'


def command(name, command_type=None):
    def deco(fn):
        COMMANDS[name] = fn
        return fn
    return deco


OUTPUT = []

module('services',
       get_instance_manager=lambda t: MANAGERS[t],
       time_service=lambda: types.SimpleNamespace(sim_now=Clock()),
       get_active_sim=lambda: SIMS[0] if SIMS else None,
       client_manager=lambda: None,
       object_manager=lambda: types.SimpleNamespace(get_all=lambda: [], get=lambda i: None),
       sim_info_manager=lambda: types.SimpleNamespace(
           instanced_sims_gen=lambda: iter(SIMS),
           get=lambda sim_id: next((s.sim_info for s in SIMS if s.sim_info.sim_id == sim_id), None)))
module('sims4.resources', Types=types.SimpleNamespace(**{k: k for k in MANAGERS}))
module('sims4.commands', Command=command, CommandType=types.SimpleNamespace(Live=4),
       CheatOutput=lambda c: OUTPUT.append)
module('sims4.localization', LocalizationHelperTuning=types.SimpleNamespace(get_raw_text=lambda t: ('raw', t)))
module('sims4.collections', AttributeDict=AttributeDict)
module('event_testing.results', TestResult=TestResult)
module('interactions.base.super_interaction', SuperInteraction=SuperInteraction)
module('interactions.context', InteractionContext=InteractionContext)
module('interactions.priority', Priority=types.SimpleNamespace(High=2))
module('sims.sim_info_types', Age=Age, Species=Species)
module('ui.ui_dialog_picker', UiObjectPicker=UiObjectPicker, ObjectPickerRow=ObjectPickerRow)
module('ui.ui_dialog_generic', UiDialogTextInputOkCancel=UiDialogTextInputOkCancel)
module('ui.ui_text_input', UiTextInput=UiTextInput, _TextInputLengthFixed=_TextInputLengthFixed)
module('ui.ui_dialog_notification', UiDialogNotification=UiDialogNotification)
class SliderDialog:
    def __init__(self, obj, r, g, b, slider_value=0, on_update=None, palette=None, style=None,
                 palette_label=None, slider_label=None, **kwargs):
        self.kind = 'slider'
        self.on_update = on_update
        self.listeners = []
        self.header = palette_label

    def add_listener(self, cb):
        self.listeners.append(cb)

    def show_dialog(self, **kwargs):
        SHOWN.append(self)

    def slide_and_close(self, value):
        self.on_update(color=0, slider_value=value)
        for cb in self.listeners:
            cb(self)


module('objects.color.object_color_dialog', UiDialogObjectColorPicker=SliderDialog)
module('objects.color.object_color_enums',
       ObjectColorPickerPalette=types.SimpleNamespace(INVALID=0),
       ObjectColorPickerStyle=types.SimpleNamespace(SLIDER=1))
module('zone', Zone=Zone)
module('alarms', add_alarm=lambda owner, span, cb, repeating=False, repeating_time_span=None, **kw:
       ALARMS.append((owner, span, cb, repeating, repeating_time_span)) or len(ALARMS),
       add_alarm_real_time=lambda owner, span, cb, **kw: cb(None) or 'rt')
module('camera', focus_on_sim=lambda sim=None, follow=True, client=None: CAMERA.append(sim))
module('clock', interval_in_real_seconds=lambda s: s)
module('date_and_time', create_time_span=lambda days=0, hours=0, minutes=0: minutes)

# Pretend the mod sits in a Mods folder
sys.path.insert(0, SRC)
import sleepcontrol.settings as _settings  # noqa: E402
_settings.find_mods_folder = lambda start_path=None: MODS
import sleepcontrol_main  # noqa: E402,F401
from sleepcontrol import game_hooks, nudge, computer, menu  # noqa: E402
from sleepcontrol.settings import SETTINGS  # noqa: E402


def aff(name):
    return next(a for a in AFFORDANCES if a.__name__ == name)


def test(name, sim, source):
    return aff(name).test_target(sim, source)


def run_test(name, sim_info, source):
    return aff(name)._test(None, InteractionContext(Sim(sim_info), source))


class FakeGameTests(unittest.TestCase):
    def setUp(self):
        SETTINGS.reset_all()
        SIMS.clear()
        SHOWN.clear()
        OUTPUT.clear()

    def test_installed(self):
        self.assertTrue(game_hooks._installed)
        with open(os.path.join(MODS, 'SleepControl_Log.txt')) as f:
            self.assertIn('Autonomy hook installed', f.read())

    def test_autonomous_sleep_blocked_in_afternoon(self):
        Clock.minutes = 14 * 60
        tired = SimInfo(10)
        self.assertFalse(run_test('bed_Autonomous_SingleBed_Sleep', tired, InteractionSource.AUTONOMY))
        self.assertTrue(run_test('bed_Autonomous_SingleBed_Sleep', tired, InteractionSource.PIE_MENU))
        self.assertTrue(run_test('fridge_Grab', tired, InteractionSource.AUTONOMY))
        self.assertTrue(run_test('newObject_Sleep', tired, InteractionSource.AUTONOMY))

    def test_night_threshold(self):
        Clock.minutes = 23 * 60
        self.assertTrue(run_test('bed_Autonomous_SingleBed_Sleep', SimInfo(30), InteractionSource.AUTONOMY))
        self.assertFalse(run_test('bed_Autonomous_SingleBed_Sleep', SimInfo(60), InteractionSource.AUTONOMY))

    def test_naps(self):
        Clock.minutes = 15 * 60 + 30
        self.assertTrue(run_test('sofa_Nap', SimInfo(20), InteractionSource.AUTONOMY))
        Clock.minutes = 11 * 60
        self.assertFalse(run_test('sofa_Nap', SimInfo(20), InteractionSource.AUTONOMY))
        self.assertTrue(run_test('sofa_Nap', SimInfo(20), InteractionSource.PIE_MENU))

    def test_exempt(self):
        Clock.minutes = 14 * 60
        for info in (SimInfo(10, Age.TODDLER), SimInfo(10, Age.INFANT), SimInfo(10, Age.BABY),
                     SimInfo(10, species=Species.DOG)):
            self.assertTrue(run_test('bed_Autonomous_SingleBed_Sleep', info, InteractionSource.AUTONOMY))
        self.assertFalse(run_test('bed_Autonomous_SingleBed_Sleep', SimInfo(10, Age.CHILD),
                                  InteractionSource.AUTONOMY))

    def test_disabled(self):
        Clock.minutes = 14 * 60
        SETTINGS.enabled = False
        self.assertTrue(run_test('bed_Autonomous_SingleBed_Sleep', SimInfo(10), InteractionSource.AUTONOMY))

    def test_error_fails_open(self):
        broken = SimInfo(10)
        broken.commodity_tracker = None
        del broken.commodity_tracker  # attribute error inside our check
        Clock.minutes = 14 * 60
        self.assertTrue(run_test('bed_Autonomous_SingleBed_Sleep', broken, InteractionSource.AUTONOMY))

    def test_nudge(self):
        tired, awake, toddler = SimInfo(20), SimInfo(80), SimInfo(10, Age.TODDLER)
        SIMS.extend([Sim(tired), Sim(awake), Sim(toddler)])
        Clock.minutes = 14 * 60
        Zone().on_loading_screen_animation_finished()
        self.assertTrue(ALARMS and ALARMS[-1][3] and ALARMS[-1][4] == 10)
        self.assertFalse(tired.has_buff(ALLOW_BUFF))
        Clock.minutes = 23 * 60
        nudge.tick()
        self.assertTrue(tired.has_buff(ALLOW_BUFF))
        self.assertFalse(awake.has_buff(ALLOW_BUFF))
        self.assertFalse(toddler.has_buff(ALLOW_BUFF))
        nudge.tick()
        self.assertEqual(list(tired.buffs.values()).count(ALLOW_BUFF), 1)
        Clock.minutes = 7 * 60
        nudge.tick()
        self.assertFalse(tired.has_buff(ALLOW_BUFF))

    def test_computer_menu(self):
        menu_aff = make_affordance('SleepControl:Computer_OpenSettings')
        MANAGERS['INTERACTION'].by_id[computer.MENU_INTERACTION_ID] = menu_aff
        for cb in MANAGERS['OBJECT'].callbacks:
            cb(MANAGERS['OBJECT'])
        got = {o.__name__: menu_aff in o._super_affordances for o in OBJECTS}
        self.assertEqual(got, {'object_Computer': True, 'object_computerLOW_01': True,
                               'object_Laptop_EP01': True, 'object_ComputerChair': False,
                               'object_Bed': False, 'object_computerDesktopMED_01': True})

    def test_menu_threshold_opens_number_box_directly(self):
        SIMS.append(Sim(SimInfo(50)))
        COMMANDS['sleepcontrol.menu']()
        main = SHOWN[-1]
        self.assertEqual(main.rows[2].name[1], 'Sleep energy threshold: 38%')
        main.choose(4)           # Nap energy threshold -> number box straight away
        ask = SHOWN[-1]
        self.assertEqual(ask.kind, 'text')
        ask.type_text('23')
        self.assertEqual(SETTINGS.get('nap', 'energy_threshold'), 23)
        self.assertEqual(SHOWN[-1].rows[4].name[1], 'Nap energy threshold: 23%')
        # bad input -> notice and asked again, value unchanged
        SHOWN[-1].choose(4)
        SHOWN[-1].type_text('abc')
        self.assertEqual([d.kind for d in SHOWN[-2:]], ['notice', 'text'])
        self.assertEqual(SETTINGS.get('nap', 'energy_threshold'), 23)

    def test_added_sleep_and_nap_names(self):
        from sleepcontrol import game_hooks, rules
        for name in ('bed_Sleep_MasteryPerk_SkillfulSleep_FromLoad',
                     'masteryPerk_SkillfulSleep_AutonomyPing',
                     'hospitalExamBed_Patient_Recline_Sleep'):
            self.assertEqual(game_hooks.classify_name(name), rules.SLEEP, name)
        for name in ('bed_Nap_PowerNap', 'bathtub_Nap_Loop', 'bathtub_Nap_Loop_Auto',
                     'beachTowel_Nap_PutInInventory_BeachTowel', 'sit_Chaise_Mixers_Nap'):
            self.assertEqual(game_hooks.classify_name(name), rules.NAP, name)
        # decided exclusions stay unclassified
        for name in ('chair_LoungeChair_RelaxFromNap', 'HighChair_Nap',
                     'atWorkActions_Daycare_Nap', 'costumeBox_CalledToWear_Sleep'):
            self.assertIsNone(game_hooks.classify_name(name), name)

    def test_menu_window_and_reset(self):
        SIMS.append(Sim(SimInfo(50)))
        COMMANDS['sleepcontrol.menu']()
        SHOWN[-1].choose(1)          # Sleep window
        SHOWN[-1].choose(0)          # Start
        SHOWN[-1].choose(0)          # Change
        SHOWN[-1].type_text('21:30')
        self.assertEqual(SETTINGS.get('sleep', 'window_start'), '21:30')
        SHOWN[-1].choose(0)          # back in window menu -> Start again
        SHOWN[-1].choose(1)          # Reset to default
        self.assertEqual(SETTINGS.get('sleep', 'window_start'), '22:00')
        COMMANDS['sleepcontrol.menu']()
        SHOWN[-1].choose(0)          # toggle enabled
        self.assertFalse(SETTINGS.enabled)
        SHOWN[-1].choose(len(SHOWN[-1].rows) - 1)  # reset everything
        self.assertTrue(SETTINGS.enabled)

    def test_commands(self):
        SIMS.append(Sim(SimInfo(30)))
        COMMANDS['sleepcontrol.status']()
        self.assertTrue(any('hook installed = True' in line for line in OUTPUT), OUTPUT)
        COMMANDS['sleepcontrol.list']()
        with open(os.path.join(MODS, 'SleepControl_Log.txt')) as f:
            log = f.read()
        self.assertIn('review interactions (1): newObject_Sleep', log)
        COMMANDS['sleepcontrol.reload']()
        COMMANDS['sleepcontrol.diag']()
        self.assertIn('details written', OUTPUT[-1])

    def test_settings_file_written(self):
        self.assertTrue(os.path.exists(os.path.join(MODS, 'SleepControl_Settings.json')))


if __name__ == '__main__':
    unittest.main()
