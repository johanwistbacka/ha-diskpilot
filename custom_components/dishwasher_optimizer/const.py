"""Constants for Dishwasher Optimizer."""

DOMAIN = "dishwasher_optimizer"
VERSION = "0.1.0-beta.2"
PROGRAMS = {"P2": "P2 · 70 °C", "P3": "P3 · Snabb", "P4": "P4 · Eco"}
DEFAULTS = {
    "power_entity": "",
    "energy_entity": "",
    "price_entity": "",
    "price_attributes": "prices",
    "start_key": "start",
    "end_key": "end",
    "value_key": "value",
    "price_multiplier": 1.0,
    "currency": "SEK",
    "horizon_hours": 24,
    "start_w": 5.0,
    "start_seconds": 30,
    "stop_w": 1.0,
    "stop_minutes": 10,
}
