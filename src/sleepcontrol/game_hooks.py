"""Hooks into the game's autonomy so sleep and naps follow the player's rules.

How it works (checked against the game's code, patch 1.128.90)
--------------------------------------------------------------
Every time autonomy considers an interaction, the game calls that
interaction's SuperInteraction._test(target, context, ...). We wrap that
classmethod: for the sleep and nap interactions listed below, when the
request comes from autonomy (context.source == SOURCE_AUTONOMY), we apply the
time window and energy threshold first.

- Player-ordered sleep (clicking a bed) comes from the pie menu, so it is
  never blocked.
- Collapsing from exhaustion is a different interaction (sim_EnergyFailure),
  so it still happens.
- A Sim already asleep keeps sleeping: we only gate starting.

Safety: any unexpected error inside our check is logged once and the game is
allowed to behave normally ("fail open").
"""

import re

from sleepcontrol import rules, log
from sleepcontrol.settings import SETTINGS

# Interactions autonomy uses to start sleep or a nap, taken from the game's
# tuning files (base game + packs). Names that are not installed are simply
# never seen. Pets, horses, babies, infants and toddlers use other interactions.
SLEEP_AFFORDANCE_NAMES = frozenset({
    'bed_Autonomous_DoubleBed_Sleep', 'bed_Autonomous_DoubleBed_Sleep_Child',
    'bed_Autonomous_SingleBed_Sleep', 'bed_Autonomous_SingleBed_Sleep_Child',
    'bed_Autonomous_Sleep_NoAutonomyPref_DoubleBed', 'bed_Autonomous_Sleep_NoAutonomyPref_SingleBed',
    'bed_sleep', 'bed_Sleep_NoAutonomyPref', 'bed_Sleep_SleepingBag', 'generic_Bed_Sleep',
    'generic_SleepingBag_Sleep', 'bed_sleep_Werebies', 'bed_Sleep_MasteryPerk_SkillfulSleep',
    'bed_Sleep_Swallow',
    'coffin_Autonomous_Sleep', 'coffin_Sleep', 'generic_CoffinSleep',
    'Tent_Sleep', 'Interaction_Tent_Sleep', 'kidsTent_Sleep',
    'sleepingPod_Interactions_Sleep', 'sleepingPod_Interactions_Sleep_Upgraded', 'SleepingPod_Sleep',
    'super_Treehouse_Enclosure_Sleep', 'swim_Mermaid_Sleep', 'swim_Mermaid_Sleep_Autonomous',
    'pool-swim_Mermaid_Sleep_Autonomous',
    'interactableCave_Sleep', 'Interactable_Cave_Sleep',
    'generic_NLS_SleepOnGround', 'gohere_NLS_SleepOnGround',
    'sI_NLS_SleepOnGround_Comfortable', 'si_NLS_SleepOnGround_Uncomfortable',
    'EP16World_Motel_Sleep', 'super_FairyHome_Object_Sleep', 'dwelling_Sleep',
})

NAP_AFFORDANCE_NAMES = frozenset({
    'bed_Autonomous_DoubleBed_Nap', 'bed_Autonomous_DoubleBed_Nap_Child',
    'bed_Autonomous_SingleBed_Nap', 'bed_Autonomous_SingleBed_Nap_Child',
    'bed_Nap', 'bed_nap', 'generic_Bed_Nap', 'bed_Nap_SleepingBag', 'generic_SleepingBag_Nap',
    'sofa_Nap', 'generic_SofaNap', 'Sofa_Nap_TwoSeated', 'sectional_Sofa_Chaise_Nap',
    'SectionalSofa_Chaise_Nap',
    'chair_Nap', 'chair_Nap_RockingChair', 'chair_Nap_RockingChair_Elder',
    'chair_LoungeChair_Nap', 'chair_LoungeChair_NapFromRelax', 'loungeChair_Nap', 'LoungeChair_Nap',
    'chair_SitLoungeFloat_Nap', 'chair_SitLoungeFloat_NapFromRelax', 'sitLoungeFloat_Nap',
    'sitLounge_Chaise_Nap', 'chair_BubbleBlower_Nap',
    'bathtub_Nap', 'bathtub_Nap_Mermaid', 'hotTub_Nap', 'si_HotSprings_Nap', 'kotatsu_Nap',
    'beachTowel_Nap',
    'coffin_Autonomous_Nap', 'coffin_Nap', 'Tent_Nap', 'kidsTent_Nap',
    'sleepingPod_Interactions_Nap', 'sleepingPod_Interactions_Nap_Upgraded',
    'super_Treehouse_Enclosure_Nap',
    'dumpster_Nap', 'generic_Dumpster_Nap', 'interactiveBush_Nap', 'vault_WalkInSafe_Nap',
    'napOnGround', 'Crypts_Nap',
    'werewolf_Abilities_Nap', 'werewolf_Abilities_Nap_Self', 'gohere_Werewolf_Nap',
    'ghostPowers_Abilities_GhostNap', 'ghostPowers_Abilities_GhostNap_NPC_Autonomous',
    'ghostPowers_GhostNap',
})

# Used only by the 'sleepcontrol.list' check command to spot sleep/nap
# interactions this list might be missing; it never blocks anything.
_REVIEW_EXCLUDE_TOKENS = {
    'wake', 'walk', 'over', 'sleepover', 'talk', 'debug', 'cheat', 'tuck', 'napkin', 'sleepy',
    'social', 'socials', 'ask', 'invite', 'woohoo', 'cuddle', 'watch', 'alarm', 'pet', 'cat',
    'dog', 'horse', 'horses', 'fox', 'infant', 'baby', 'toddler', 'crib', 'bassinet', 'death',
    'potion', 'guitar', 'lull', 'mind', 'mixer', 'picker', 'butler', 'npc', 'failure', 'dream',
}

_installed = False
_classify_cache = {}
_energy_stat_type = None
_energy_lookup_done = False
_exempt_ages = None
_human_species = None
_autonomy_source = None


def _tokens(name):
    spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
    return [t for t in re.split(r'[^A-Za-z0-9]+', spaced.lower()) if t]


def classify_name(name):
    """Return 'sleep', 'nap' or None for an interaction tuning name."""
    if name in SLEEP_AFFORDANCE_NAMES:
        return rules.SLEEP
    if name in NAP_AFFORDANCE_NAMES:
        return rules.NAP
    return None


def review_candidate(name):
    """True for names that look like sleep/nap but are not in the lists (for checking only)."""
    if classify_name(name) is not None:
        return False
    tokens = _tokens(name)
    if not ('sleep' in tokens or 'nap' in tokens):
        return False
    return not any(t in _REVIEW_EXCLUDE_TOKENS for t in tokens)


def classify(affordance):
    try:
        return _classify_cache[affordance]
    except KeyError:
        pass
    kind = classify_name(getattr(affordance, '__name__', '') or '')
    _classify_cache[affordance] = kind
    return kind


def find_tuning(resource_type_name, tuning_name):
    import services
    import sims4.resources
    manager = services.get_instance_manager(getattr(sims4.resources.Types, resource_type_name))
    wanted = tuning_name.lower()
    for tuning in manager.types.values():
        if tuning.__name__.lower() == wanted:
            return tuning
    return None


def _get_energy_stat_type():
    global _energy_stat_type, _energy_lookup_done
    if not _energy_lookup_done:
        _energy_lookup_done = True
        try:
            _energy_stat_type = find_tuning('STATISTIC', 'motive_Energy')
            log.write('Energy need found: {}'.format(_energy_stat_type))
        except Exception:
            log.exception('looking up energy need')
    return _energy_stat_type


def get_energy_percent(sim_info):
    stat_type = _get_energy_stat_type()
    if stat_type is None:
        return None
    tracker = sim_info.commodity_tracker
    if tracker is None:
        return None
    stat = tracker.get_statistic(stat_type)
    if stat is None:  # this Sim has no regular energy need
        return None
    return rules.energy_percent(stat.get_value(), stat.min_value, stat.max_value)


def get_now_minutes():
    import services
    now = services.time_service().sim_now
    return now.hour() * 60 + now.minute()


def is_covered_sim(sim_info):
    """Humans of child age and up. Babies, infants and toddlers are exempt."""
    global _exempt_ages, _human_species
    if _exempt_ages is None:
        from sims.sim_info_types import Age, Species
        _exempt_ages = frozenset(a for a in (getattr(Age, n, None) for n in ('BABY', 'INFANT', 'TODDLER'))
                                 if a is not None)
        _human_species = Species.HUMAN
    if sim_info.age in _exempt_ages:
        return False
    species = getattr(sim_info, 'species', _human_species)
    return species == _human_species


def block_reason(affordance, context):
    """Return a reason string if this autonomous sleep/nap must be blocked, else None."""
    if context is None or context.source != _autonomy_source:
        return None
    kind = classify(affordance)
    if kind is None or not SETTINGS.enabled:
        return None
    sim = context.sim
    if sim is None:
        return None
    sim_info = sim.sim_info
    if not is_covered_sim(sim_info):
        return None
    allowed, reason = rules.check(kind, get_now_minutes(), get_energy_percent(sim_info),
                                  SETTINGS.data[kind])
    return None if allowed else reason


def install():
    global _installed, _autonomy_source
    if _installed:
        return True
    try:
        from event_testing.results import TestResult
        from interactions.base.super_interaction import SuperInteraction
        from interactions.context import InteractionContext
        _autonomy_source = InteractionContext.SOURCE_AUTONOMY

        raw = SuperInteraction.__dict__.get('_test')
        if not isinstance(raw, classmethod):
            log.write('Not installed: SuperInteraction._test is {!r}, expected a classmethod'.format(raw))
            return False
        original = raw.__func__

        def _test(cls, target, context, **interaction_parameters):
            try:
                reason = block_reason(cls, context)
            except Exception:
                log.exception_once('block_reason', 'sleep/nap check (game behaves normally)')
                reason = None
            if reason:
                return TestResult(False, reason)
            return original(cls, target, context, **interaction_parameters)

        _test.__wrapped__ = original
        SuperInteraction._test = classmethod(_test)
        _installed = True
        log.write('Autonomy hook installed')
        return True
    except Exception:
        log.exception('installing autonomy hook')
        return False


def matched_affordances():
    """What this mod covers in the installed game, plus possible gaps to review."""
    import services
    import sims4.resources
    manager = services.get_instance_manager(sims4.resources.Types.INTERACTION)
    found = {rules.SLEEP: [], rules.NAP: [], 'review': []}
    for affordance in manager.types.values():
        name = affordance.__name__
        kind = classify(affordance)
        if kind:
            found[kind].append(name)
        elif review_candidate(name) and getattr(affordance, 'allow_autonomous', False):
            found['review'].append(name)
    for names in found.values():
        names.sort()
    return found
