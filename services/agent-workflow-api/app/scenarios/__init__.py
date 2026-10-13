from __future__ import annotations

from ..specs import Scenario
from . import card_alert, coding_team, holiday_promo, trial_finder, work_order

SCENARIOS: dict[str, Scenario] = {
    s.id: s
    for s in [
        card_alert.SCENARIO,
        trial_finder.SCENARIO,
        work_order.SCENARIO,
        coding_team.SCENARIO,
        holiday_promo.SCENARIO,
    ]
}


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as exc:
        raise KeyError(f"Unknown scenario {scenario_id!r}") from exc
