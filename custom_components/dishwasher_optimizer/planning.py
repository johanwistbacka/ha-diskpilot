"""Immutable calculation snapshots and read-only chart views; run on HA's executor."""

from .engine import cost_at, optimise, profile_for
from .pricing import source_prices


def prepare_plan(runs, names, config, attributes, now, market=None):
    """Keep price mapping, average curves and optimal costs from one source snapshot."""
    profiles = {key: profile_for(runs, key) for key in names}
    prices, price_status, price_basis = source_prices(config, attributes, now, market)
    deadline = now + config["horizon_hours"] * 3600
    results = {}
    for key, profile in profiles.items():
        result = optimise(profile, now, deadline, prices) if profile and prices else {}
        results[key] = {
            **result,
            "sample_count": profile.count if profile else 0,
            "energy_kwh": sum(profile.energy_wh) / 1000 if profile else None,
            "duration_minutes": profile.duration_seconds / 60 if profile else None,
            "energy_min_kwh": profile.min_kwh if profile else None,
            "energy_max_kwh": profile.max_kwh if profile else None,
            "status": (
                ("needs_labelled_run" if config["power_entity"] else "needs_saved_profile")
                if profile is None
                else price_status
                if price_status != "ok"
                else "ok"
                if result.get("cost") is not None
                else "insufficient_price_coverage"
            ),
        }
    return {
        "names": names,
        "profiles": profiles,
        "prices": tuple(prices),
        "results": results,
        "price_status": price_status,
        "currency": config["currency"],
        "price_basis": price_basis,
        "generated_at": now,
        "deadline": deadline,
    }


def planning_view(plan, now, selected_start):
    """Return transient averages, not raw runs or extra Recorder attributes."""
    profiles = []
    for key, name in plan["names"].items():
        profile = plan["profiles"][key]
        selected_cost = cost_at(profile, selected_start, plan["prices"]) if profile else None
        profiles.append(
            {
                "id": key,
                "name": name,
                **plan["results"][key],
                "duration_seconds": profile.duration_seconds if profile else None,
                "energy_wh": list(profile.energy_wh) if profile else [],
                "selected_cost": selected_cost,
                "selected_end": selected_start + profile.duration_seconds if profile else None,
            }
        )
    return {
        "now": now,
        "selected_start": selected_start,
        "generated_at": plan["generated_at"],
        "planning_deadline": plan["deadline"],
        "currency": plan["currency"],
        "price_status": plan["price_status"],
        "price_basis": plan["price_basis"],
        "prices": [
            [p.start, p.end, p.value] for p in plan["prices"] if p.end > min(now, selected_start)
        ],
        "profiles": profiles,
    }
