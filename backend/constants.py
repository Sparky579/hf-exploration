"""
Module purpose:
- Hold shared constants used by movement, phase control, and holy-water formulas.

Exposed symbols:
- MOVE_TIME_COST: Time consumed for one edge move.
- BASE_HOLY_WATER_PER_TIME: Base holy-water gain rate outside war.
- PHASE_EMERGENCY: Global state key for emergency phase.
- PHASE_BATTLE: Global state key for battle phase.
"""

MOVE_TIME_COST = 1.0
BASE_HOLY_WATER_PER_TIME = 0.5  # +1 holy water per 2 time units

PHASE_EMERGENCY = "emergency"
PHASE_BATTLE = "battle"
