# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- lidar corridor filter and ingestion pipeline (Demo 7).
SAFETY_CONCEPT.md v0.1: R-01, R-04, AR-7.

Problem this solves
  A fixed-angle cone (for example +-8 degrees, 5 samples) covers only a few centimetres
  either side of the centre line at close range, while the robot is about half a metre wide.
  An obstacle intruding into the swept path beside the centre line is then invisible.

What it does
  Keeps every sample whose position lies inside the robot's swept corridor
  (forward of the sensor, lateral offset <= half_width) and replaces all other
  valid samples with +inf ("no return"). The output has the SAME LENGTH as the input,
  so gate_core still validates the whole scan.
  Invalid values (NaN, <= 0, -inf, non-numbers, bool) are passed through UNCHANGED so that
  gate_core trips on them. This filter must never turn bad data into a clear reading.

Geometry assumption: samples are evenly spread over the field of view, symmetric about the
sensor axis. Because lateral offset uses |sin(angle)|, the scan direction (left-to-right or
right-to-left) does not matter. The sensor axis must point along the robot's forward direction.
Standard library only.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple


class CorridorFilter:
    def __init__(self, n_samples: int, fov_rad: float, half_width_m: float):
        if not isinstance(n_samples, int) or isinstance(n_samples, bool) or n_samples < 2:
            raise ValueError("n_samples must be an int >= 2")
        if not (isinstance(fov_rad, (int, float)) and math.isfinite(fov_rad) and 0.0 < fov_rad <= 2 * math.pi):
            raise ValueError("fov_rad must be finite and in (0, 2*pi]")
        if not (isinstance(half_width_m, (int, float)) and math.isfinite(half_width_m) and half_width_m > 0.0):
            raise ValueError("half_width_m must be finite and > 0")
        self.n = n_samples
        self.fov = float(fov_rad)
        self.half_width = float(half_width_m)
        self._abs_sin: List[float] = []
        self._ahead: List[bool] = []
        for i in range(n_samples):
            theta = (i / (n_samples - 1) - 0.5) * self.fov
            self._abs_sin.append(abs(math.sin(theta)))
            self._ahead.append(math.cos(theta) > 1e-9)

    def apply(self, ranges: Optional[Sequence[float]]) -> Optional[List[float]]:
        """Return the filtered scan, or None if the input is missing or has the wrong length."""
        if ranges is None:
            return None
        try:
            if len(ranges) != self.n:
                return None
        except TypeError:
            return None
        out: List[float] = []
        hw = self.half_width
        for i, r in enumerate(ranges):
            if isinstance(r, bool) or not isinstance(r, (int, float)) or math.isnan(r) or r <= 0.0:
                out.append(r)                      # invalid: leave it for gate_core to reject
            elif math.isinf(r):
                out.append(r)                      # no return
            elif self._ahead[i] and r * self._abs_sin[i] <= hw:
                out.append(r)                      # inside the swept corridor
            else:
                out.append(math.inf)               # valid but outside the corridor
        return out


class LidarPipeline:
    """
    Manages raw lidar scan ingestion, validity checks, corridor filtering,
    and acquisition timestamp tracking (F1, F2).

    Rules:
      - Validates and counts raw finite returns across the entire field of view (F1).
      - Applies CorridorFilter to mask non-corridor returns as +inf.
      - Maintains the timestamp of the last actual hardware acquisition.
      - If sensor acquisition stalls (stalled=True) or fails, the timestamp does NOT advance,
        allowing the gate core's t_stale watchdog to detect frozen hardware (F2).
    """

    def __init__(self, corridor: CorridorFilter):
        if not isinstance(corridor, CorridorFilter):
            raise TypeError("corridor must be an instance of CorridorFilter")
        self.corridor = corridor
        self.last_stamp_us: Optional[int] = None

    def process(
        self,
        raw_ranges: Optional[Sequence[float]],
        sim_time_us: int,
        stalled: bool = False,
    ) -> Tuple[Optional[List[float]], Optional[int], int]:
        """
        Processes a raw scan reading at current simulation time sim_time_us.

        Returns:
            (filtered_ranges, lidar_stamp_us, raw_valid_points)
        """
        if raw_ranges is None:
            return None, self.last_stamp_us, 0

        # Count finite, positive returns across the raw 240-degree field of view (F1)
        raw_valid_points = sum(
            1 for r in raw_ranges
            if isinstance(r, (int, float)) and not isinstance(r, bool)
            and math.isfinite(r) and r > 0.0
        )

        # Update last acquisition stamp unless acquisition is stalled (F2)
        if not stalled:
            self.last_stamp_us = sim_time_us

        filtered = self.corridor.apply(raw_ranges)
        return filtered, self.last_stamp_us, raw_valid_points
