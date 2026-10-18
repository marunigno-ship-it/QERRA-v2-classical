# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Default parameter factory for the QERRA Supervisory Gate (SAFETY_CONCEPT.md v0.2).
Provides live parameters with justified reaction time (F4) decoupled from Webots.
Standard library only.
"""
from __future__ import annotations

from gate.gate_core import GateParams

# TIAGo simulation step: dt = 32 ms (32,000 µs).
# F4 reaction-time allowance: 1 discrete control tick (32,000 µs).
# At cruise speed (196 mm/s), this accounts for 7 mm of reaction displacement,
# growing the stopping envelope from 339 mm to 346 mm.
DEFAULT_LIVE_T_REACT_US = 32_000


def get_live_gate_params(
    lidar_n_expected: int,
    *,
    dt_us: int = 32_000,
    w_max_urad_s: int = 3_000_000,
    t_react_us: int = DEFAULT_LIVE_T_REACT_US,
    **overrides,
) -> GateParams:
    """
    Factory creating GateParams configured with live deployment defaults.
    F4: ensures t_react_us > 0 so reaction latency is active in the stopping envelope.
    """
    params_dict = dict(
        lidar_n_expected=lidar_n_expected,
        dt_us=dt_us,
        t_watch_us=150_000,
        proposer_period_us=33_000,
        lidar_period_us=dt_us,
        t_stale_us=3 * dt_us,
        t_dwell_us=1_000_000,
        max_tick_gap_us=2 * dt_us,
        wheel_radius_mm=98,
        w_min_urad_s=0,
        w_max_urad_s=w_max_urad_s,
        a_design_mmps2=500,
        margin_mm=300,
        min_raw_lidar_returns=5,
        t_react_us=t_react_us,
    )
    params_dict.update(overrides)
    return GateParams(**params_dict)
