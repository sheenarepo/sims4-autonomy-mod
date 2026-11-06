import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sleepcontrol import rules, settings, game_hooks, computer  # noqa: E402


class TimeTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(rules.parse_time('22:00'), 22 * 60)
        self.assertEqual(rules.parse_time('22'), 22 * 60)
        self.assertEqual(rules.parse_time('7:05'), 7 * 60 + 5)
        self.assertEqual(rules.parse_time('22.30'), 22 * 60 + 30)
        self.assertEqual(rules.parse_time('24:00'), 0)
        self.assertEqual(rules.parse_time(' 06:00 '), 360)
        for bad in ('', '25', '12:60', 'abc', '1:2:3', None, '-1'):
            self.assertIsNone(rules.parse_time(bad), bad)

    def test_window_overnight(self):
        s, e = rules.parse_time('22:00'), rules.parse_time('06:00')
        self.assertTrue(rules.in_window(rules.parse_time('23:30'), s, e))
        self.assertTrue(rules.in_window(rules.parse_time('00:00'), s, e))
        self.assertTrue(rules.in_window(rules.parse_time('05:59'), s, e))
        self.assertFalse(rules.in_window(rules.parse_time('06:00'), s, e))
        self.assertFalse(rules.in_window(rules.parse_time('14:00'), s, e))
        self.assertTrue(rules.in_window(rules.parse_time('22:00'), s, e))

    def test_window_same_day_and_all_day(self):
        s, e = rules.parse_time('15:00'), rules.parse_time('16:00')
        self.assertTrue(rules.in_window(rules.parse_time('15:30'), s, e))
        self.assertFalse(rules.in_window(rules.parse_time('16:00'), s, e))
        self.assertTrue(rules.in_window(123, 600, 600))


class CheckTests(unittest.TestCase):
    block = {'window_start': '22:00', 'window_end': '06:00', 'energy_threshold': 30}

    def test_blocked_outside_window_even_when_exhausted(self):
        allowed, _ = rules.check('sleep', rules.parse_time('14:00'), 5, self.block)
        self.assertFalse(allowed)

    def test_blocked_inside_window_when_energy_high(self):
        allowed, reason = rules.check('sleep', rules.parse_time('23:00'), 60, self.block)
        self.assertFalse(allowed)
        self.assertIn('threshold', reason)

    def test_allowed_inside_window_at_threshold(self):
        self.assertTrue(rules.check('sleep', rules.parse_time('23:00'), 30, self.block)[0])
        self.assertTrue(rules.check('sleep', rules.parse_time('23:00'), 10, self.block)[0])

    def test_unknown_energy_only_uses_window(self):
        self.assertTrue(rules.check('sleep', rules.parse_time('23:00'), None, self.block)[0])
        self.assertFalse(rules.check('sleep', rules.parse_time('12:00'), None, self.block)[0])

    def test_energy_percent(self):
        self.assertEqual(rules.energy_percent(-100, -100, 100), 0)
        self.assertEqual(rules.energy_percent(0, -100, 100), 50)
        self.assertEqual(rules.energy_percent(100, -100, 100), 100)
        self.assertEqual(rules.energy_percent(-40, -100, 100), 30)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'SleepControl_Settings.json')

    def test_missing_file_creates_defaults(self):
        s = settings.Settings(self.path)
        s.load()
        self.assertEqual(s.data, settings.DEFAULTS)
        self.assertTrue(os.path.exists(self.path))

    def test_bad_values_fall_back(self):
        with open(self.path, 'w') as f:
            json.dump({'enabled': 'yes', 'sleep': {'window_start': '99:00', 'energy_threshold': 500},
                       'nap': {'window_end': '17', 'energy_threshold': 45}}, f)
        s = settings.Settings(self.path)
        s.load()
        self.assertTrue(s.data['enabled'])
        self.assertEqual(s.data['sleep'], settings.DEFAULTS['sleep'])
        self.assertEqual(s.data['nap']['window_end'], '17:00')
        self.assertEqual(s.data['nap']['energy_threshold'], 45)

    def test_corrupt_file_is_kept_and_defaults_used(self):
        with open(self.path, 'w') as f:
            f.write('{not json')
        s = settings.Settings(self.path)
        s.load()
        self.assertEqual(s.data, settings.DEFAULTS)
        self.assertTrue(os.path.exists(self.path + '.broken'))

    def test_set_reset_roundtrip(self):
        s = settings.Settings(self.path)
        s.load()
        s.set('sleep', 'energy_threshold', 55)
        s.set('nap', 'window_start', '13:00')
        s2 = settings.Settings(self.path)
        s2.load()
        self.assertEqual(s2.get('sleep', 'energy_threshold'), 55)
        self.assertEqual(s2.get('nap', 'window_start'), '13:00')
        s2.reset('sleep', 'energy_threshold')
        self.assertEqual(s2.get('sleep', 'energy_threshold'), settings.DEFAULTS['sleep']['energy_threshold'])

    def test_mods_folder_detection(self):
        self.assertEqual(
            settings.find_mods_folder('/Users/x/Documents/Electronic Arts/The Sims 4/Mods/SleepControl.ts4script/sleepcontrol/settings.pyc'),
            '/Users/x/Documents/Electronic Arts/The Sims 4/Mods')
        self.assertEqual(
            settings.find_mods_folder('/Users/x/Documents/Electronic Arts/The Sims 4/Mods/Sub/SleepControl.ts4script/sleepcontrol/settings.pyc'),
            '/Users/x/Documents/Electronic Arts/The Sims 4/Mods/Sub')
        self.assertEqual(
            settings.find_mods_folder('/Users/x/Documents/Electronic Arts/The Sims 4/Mods/SleepControl/Scripts/sleepcontrol/settings.py'),
            '/Users/x/Documents/Electronic Arts/The Sims 4/Mods')


class ClassifyTests(unittest.TestCase):
    def test_names(self):
        c = game_hooks.classify_name
        self.assertEqual(c('bed_Autonomous_SingleBed_Sleep'), 'sleep')
        self.assertEqual(c('bed_Autonomous_DoubleBed_Nap'), 'nap')
        self.assertEqual(c('sofa_Nap'), 'nap')
        self.assertEqual(c('coffin_Autonomous_Sleep'), 'sleep')
        # never caught: collapse, pets, babies, guitar lullaby
        for name in ('sim_EnergyFailure', 'pet_Sleep', 'infant_Sleep', 'guitar_Social_Lull_To_Sleep',
                     'bed_Sleep_Toddler_Autonomous', 'mermaid_EnergyFailure_SleepAuto'):
            self.assertIsNone(c(name), name)
        self.assertFalse(set(game_hooks.SLEEP_AFFORDANCE_NAMES) & set(game_hooks.NAP_AFFORDANCE_NAMES))

    def test_review(self):
        r = game_hooks.review_candidate
        self.assertTrue(r('newObject_Sleep'))
        self.assertFalse(r('bed_sleep'))
        self.assertFalse(r('pet_Sleep_Dog'))
        self.assertFalse(r('reaction_Inappropriate'))


class ComputerTests(unittest.TestCase):
    def test_id_is_stable_and_high_bit(self):
        self.assertEqual(computer.fnv64(''), 0xCBF29CE484222325)
        self.assertTrue(computer.MENU_INTERACTION_ID & 0x8000000000000000)


if __name__ == '__main__':
    unittest.main()
