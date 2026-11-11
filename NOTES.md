# Sleep Control mod: working notes

## Agreed behaviour
- Separate sleep and nap time windows (24-hour). Outside a window, Sims never
  choose that on their own, even when exhausted.
- Separate sleep and nap energy thresholds (1-100 = energy %). Sims only choose
  to sleep/nap on their own at or below the threshold.
- Player-ordered sleep/naps are never blocked.
- Critical exhaustion still makes Sims collapse anywhere, any time.
- A Sim already asleep when the window closes keeps sleeping.
- Babies, infants and toddlers are exempt.
- Same rules for every Sim, trait, job, lot and world. Global settings for all saves.
- Menu on every computer, laid out like MCCC. Changes apply instantly (no restart).
- Must coexist with MCCC.

## Layout
- src/sleepcontrol/rules.py: pure logic (tested in tests/test_logic.py)
- src/sleepcontrol/settings.py: JSON settings in the Mods folder
- src/sleepcontrol/game_hooks.py: wraps SuperInteraction._test for autonomous sleep/nap
- src/sleepcontrol/menu.py and dialogs.py: in-game menu
- src/sleepcontrol/computer.py: adds the menu interaction to computers
- tools/build.py: builds dist/SleepControl.ts4script + dist/SleepControl.package (run with Python 3.7)

## Verified against the installed game (patch 1.128.90.1230, Python 3.7.0)
- SuperInteraction._test is a classmethod (cls, target, context, **interaction_parameters);
  Interaction.test calls it; InteractionContext.SOURCE_AUTONOMY exists.
- Autonomy starts sleep through launcher interactions (bed_Autonomous_*_Sleep/Nap, sofa_Nap,
  chair_Nap, ...); player sleep uses bed_sleep / bed_Nap from the pie menu.
- Collapse is sim_EnergyFailure (motive_Energy failure at -100); distress at -75.
- motive_Energy runs -100..100; its autonomy advertisement is 0 above -25 (37.5%),
  so the default threshold is 38%.
- Autonomous bed sleep also needs buff_SmallSleepDesire / LargeSleepDesire / AllowSleepDesire,
  given by the autonomy component's sleep schedule (counted back from work start time).
  nudge.py adds buff_AllowSleepDesire during the sleep window when energy <= threshold.
- Autonomous naps need buff_Nap (a visible Energized moodlet), Lazy trait, or Sloshed;
  the mod never adds it, so naps are only limited.
- Dialog APIs checked: UiObjectPicker (max_selectable is a variant, leave default),
  ObjectPickerRow(option_id, name, row_description, tag), get_single_result_tag,
  UiDialogTextInputOkCancel + UiTextInput + _TextInputLengthFixed + AttributeDict.
- ImmediateSuperInteraction locks allow_autonomous; DoCommand tuning = command + arguments.
- The game imports every module inside a .ts4script.

## Still to check in game
- Menu appears on computers and all dialogs work.
- sleepcontrol.list review entries (possible sleep/nap interactions missing from the list).
- Sims go to bed in the window at/below threshold; no sleep/naps outside windows.
- Coexistence with MCCC.
- Thresholds above ~38% will not make Sims sleep sooner (the game does not advertise
  sleep above 37.5% energy); would need a stronger nudge if wanted.

## In-game test results (Oct 9)
- Mod loads; hook installed; energy and clock read correctly; blocks sleep outside window.
- Settings menu, number entry and reset all work. Row icons use the energy icon.
- Computer menu bug fixed: 'desk' exclusion was hiding object_computerDesktopMED_01.
- Added from sleepcontrol.list review: pool-swim_Mermaid_Sleep_Autonomous, napOnGround, Crypts_Nap.
- Cheat console on Mac: Ctrl+Shift+C (hold the keys briefly).

## Before release
- Remove the temporary sleepcontrol.dev command and Mods/SleepControl_dev.txt.
- Remove the empty Mods/_to_delete folder.

## Applied 2026-11-10
- Added the confirmed sleep/nap names to game_hooks.py (3 sleep, 5 nap). The "proposed, not confirmed" sleep names were NOT added.
- Replaced the stale test_bar_icons (icons were removed) with a test for the added names and decided exclusions.
- Build verified with Python 3.7.12 (conda-forge). Queued-sleep feature still waits on the in-game queue probe (branch sleepcontrol-queue-probe).
