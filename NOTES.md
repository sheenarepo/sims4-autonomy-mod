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

## Session status: paused (2026-11-10)

### Queued-sleep feature: design decisions (agreed)
1. Scope: only Sims in the active household.
2. Window: applies for the whole sleep or nap window, using that window's own threshold.
3. Trigger: a Sim at or below the threshold is pulled toward a bed. Above the threshold, nothing changes.
4. Bed choice: a Sim with an assigned bed prefers it; a Sim without one uses any unassigned bed; if none is free, any other sleep or nap spot.
5. Continuity: a Sim already asleep keeps sleeping. If they wake in the window and are at or below the threshold, the pull resumes.
6. Interruptions: the mod does not stop the current activity. It queues a sleep or nap behind it, including sitting on a sofa or chair. Not yet confirmed that the game queue supports this.
7. Window end: a Sim still asleep keeps sleeping.
8. Player orders are never changed. The pull applies only to Sims' own choices.
9. Same rules for every Sim in the household.
10. Applies to sick and injured Sims. Babies, infants and toddlers stay exempt.
11. A queued sleep or nap still runs after the window closes.
12. Once queued, it always runs, even if energy rises above the threshold first.
- Open: the game's queue API is unverified. A read-only probe (`sleepcontrol.probe_queue`, src/sleepcontrol/probe.py) exists on branch `sleepcontrol-queue-probe` but has not been run in game.
- Open: how a bed pull increases the chance a Sim picks a bed (game scoring) is unverified.

### Sleep/nap name list decisions
Nap additions: bed_Nap_PowerNap, bathtub_Nap_Loop, bathtub_Nap_Loop_Auto, beachTowel_Nap_PutInInventory_BeachTowel, sit_Chaise_Mixers_Nap.
Nap excluded: chair_LoungeChair_RelaxFromNap, chair_LoungeChair_RelaxFromNap_Child, HighChair_Nap (toddler-exempt), atWorkActions_Daycare_Nap (disregarded).
Sleep additions: bed_Sleep_MasteryPerk_SkillfulSleep_FromLoad (higher priority than other sleep options), masteryPerk_SkillfulSleep_AutonomyPing (lead-in to the perk sleep), hospitalExamBed_Patient_Recline_Sleep.
Sleep excluded: costumeBox_CalledToWear_Sleep, closet_TryNewOutfit_Gather_Sleep, costumeBox_CallToWear_Sleep (outfit actions, disregarded).
Proposed (not yet confirmed as final): sleep additions sleep_Passive, sleep_Passive_Coffin, sleep_SleepingBag_Passive, sleep_Coffin_VampireDaymare, sleep_Coffin_HumanNightmare, si_Touching_MurphyBed_Sleep_Swallow_Two_Sims. Excluded: mannequin_OutfitChange_Generate_Sleep, switch_outfit_Sleep, ranchNectarMaker_MasteryPerk_SkillfulSleep_Stomp, the two superInteraction_FairyOccult shrink events, and the sleep_MonsterUnderBed_* names.

### Build
- tools/build.py requires Python 3.7 (the game's version). Not available in the cloud sandbox or on the ThinkPad as of this note.
