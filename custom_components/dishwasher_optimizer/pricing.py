"""Compose variable energy prices without treating power tariffs as SEK/kWh.

Eltariff's cached models are inspected structurally; no upstream code is copied.
Only fixed energy components with explicit validity are supported initially.
"""

from dataclasses import dataclass
from datetime import date, datetime, time

from .engine import Price, finite, parse_prices


class PriceInputError(ValueError):
    """A price source cannot safely describe the requested energy intervals."""

    def __init__(self, status):
        self.status = status
        super().__init__(status)


@dataclass(frozen=True)
class MarketInputs:
    attributes: dict | None = None
    tariff: object = None
    grid_zone: object = None
    error: str | None = None


def _edge(day, zone, default):
    if day is None:
        return default
    if type(day) is not date:
        raise PriceInputError("grid_unsupported")
    return datetime.combine(day, time.min, tzinfo=zone).timestamp()


def grid_prices(tariff, zone, currency, start, end):
    """Use published component validity, never a projection of today's sensor value."""
    try:
        if tariff.direction not in (None, "consumption") or zone is None:
            raise PriceInputError("grid_unsupported")
        if type(tariff.valid_period.from_including) is not date:
            raise PriceInputError("grid_unsupported")
        start = max(start, _edge(tariff.valid_period.from_including, zone, start))
        end = min(end, _edge(tariff.valid_period.to_excluding, zone, end))
        if end <= start:
            return []
        group = tariff.energy_price
        if group is None or not group.components:
            raise PriceInputError("grid_unsupported")
        formula = "".join((group.cost_function or "").split())
        if formula not in ("", "sum(energy(c)*price(c))"):
            raise PriceInputError("grid_unsupported")
        edges = {start, end}
        components = []
        for c in group.components:
            if type(c.valid_period.from_including) is not date:
                raise PriceInputError("grid_unsupported")
            a = _edge(c.valid_period.from_including, zone, start)
            b = _edge(c.valid_period.to_excluding, zone, end)
            if b <= start or a >= end:
                continue
            if (
                c.recurring_periods
                or c.url
                or c.spot_price_settings
                or c.priced_period
                or str(c.component_type) not in ("fixed", "energy", "public")
                or c.unit != "kWh"
            ):
                raise PriceInputError("grid_unsupported")
            if c.price.currency != currency:
                raise PriceInputError("currency_mismatch")
            value = finite(c.price.price_inc_vat)
            components.append((a, b, c.reference, value))
            edges.update((max(start, a), min(end, b)))
        result = []
        points = sorted(edges)
        for a, b in zip(points, points[1:], strict=False):
            if b <= a:
                continue
            active = [c for c in components if c[0] <= a and c[1] >= b]
            refs = [c[2] for c in active]
            if len(set(refs)) != len(refs):
                raise PriceInputError("grid_unsupported")
            # Missing tax/transfer is unknown rather than a fabricated free component.
            if not {"main", "tax"} <= set(refs):
                continue
            result.append(Price(a, b, finite(sum(c[3] for c in active))))
        return result
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, PriceInputError):
            raise
        raise PriceInputError("grid_unsupported") from error


def source_prices(config, attributes, now, market=None):
    """Return normalized intervals, source status and a compact calculation description."""
    mode = config.get("price_source", "sensor")
    if mode == "sensor":
        if not config["price_entity"]:
            return [], "not_configured", "Färdig totalprislista"
        if attributes is None:
            return [], "unavailable", "Färdig totalprislista"
        try:
            prices = parse_prices(attributes, config)
            return prices, "ok" if prices else "no_intervals", "Färdig totalprislista"
        except ValueError, TypeError, KeyError, OverflowError:
            return [], "invalid_format", "Färdig totalprislista"
    basis = "Nord Pool + nät och energiskatt från Eltariff + avtalspåslag (inkl. moms)"
    if not config.get("grid_entry"):
        basis = "Nord Pool + avtalspåslag (inkl. moms; nätavgift och energiskatt ingår inte)"
    basis += f" Påslag: {config['contract_markup']} {config['currency']}/kWh."
    if market is None or market.error:
        return [], market.error if market else "unavailable", basis
    attrs = market.attributes
    if attrs is None:
        return [], "unavailable", basis
    try:
        if mode == "nordpool_sensor":
            unit = attrs.get("unit_of_measurement")
            if unit != f"{config['currency']}/kWh":
                raise PriceInputError("currency_mismatch")
            # Already-added charges must be removed at source or used as a complete price list.
            extra = finite(attrs.get("additional_costs_current_hour", 0))
            if extra != 0:
                raise PriceInputError("spot_includes_fees")
            mapping = {
                **config,
                "price_attributes": "raw_today,raw_tomorrow",
                "value_key": "value",
                "price_multiplier": 1,
                "start_key": "start",
                "end_key": "end",
            }
            multiplier = 1 if config["spot_includes_vat"] else 1 + config["vat_percent"] / 100
        elif mode == "nordpool_core":
            mapping = {
                **config,
                "price_attributes": "prices",
                "value_key": "price",
                "price_multiplier": 0.001,
                "start_key": "start",
                "end_key": "end",
            }
            multiplier = 1 + config["vat_percent"] / 100
        else:
            raise PriceInputError("invalid_format")
        spot = parse_prices(attrs, mapping)
        if not spot:
            return [], "no_intervals", basis
        markup = finite(config["contract_markup"])
        spot = [Price(p.start, p.end, finite(p.value * multiplier + markup)) for p in spot]
        if not config.get("grid_entry"):
            return spot, "ok", basis
        if market.tariff is None:
            raise PriceInputError("grid_unavailable")
        grid = grid_prices(
            market.tariff,
            market.grid_zone,
            config["currency"],
            min(p.start for p in spot),
            max(p.end for p in spot),
        )
        prices = [
            Price(max(p.start, g.start), min(p.end, g.end), finite(p.value + g.value))
            for p in spot
            for g in grid
            if max(p.start, g.start) < min(p.end, g.end)
        ]
        return prices, "ok" if prices else "grid_no_coverage", basis
    except PriceInputError as error:
        return [], error.status, basis
    except ValueError, TypeError, KeyError, OverflowError:
        return [], "invalid_format", basis
