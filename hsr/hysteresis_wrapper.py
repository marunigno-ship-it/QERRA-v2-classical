# =====================================================
# hysteresis_wrapper.py
# QERRA-HSR — Hysteresis wrapper (dwell + separated thresholds)
#
# This file does NOT modify hsr/qerra_hsr.py. It sits next to it and
# calls it. The original evaluate_hsr() function is completely
# untouched — same inputs, same outputs, same formal guarantees.
#
# Rule, always, no exceptions:
#   - Escalating (getting MORE cautious) applies INSTANTLY. Zero delay.
#   - De-escalating (getting LESS cautious) only applies after the
#     calmer reading has held steady for DWELL_SECONDS in a row.
# =====================================================

import time
from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus

# ---- Tunable constants -------------------------------------------
# Starting estimates, not empirically validated — same honest framing
# as the thresholds in hsr/qerra_hsr.py itself. Easy to change later;
# nothing else in the codebase depends on these exact numbers.

DWELL_SECONDS = 1.0            # how long a calmer reading must hold
                                # before the system relaxes

MONITOR_EXIT_THRESHOLD = 0.35  # must drop this low (not just below
                                # 0.45) before MONITOR steps down

_SEVERITY = {
    HSRStatus.CLEAR: 0,
    HSRStatus.MONITOR: 1,
    HSRStatus.CRITICAL: 2,
}


class StabilizedHSR:
    """
    Wraps evaluate_hsr() with memory between calls, to prevent a
    single noisy reading from flipping the reported state back and
    forth. Call .evaluate(hsr_input) the same way you'd call
    evaluate_hsr(hsr_input) directly.
    """

    def __init__(self):
        self._current_status = HSRStatus.CLEAR
        self._calm_reading_since = None

    def evaluate(self, hsr_input: HSRInput):
        raw_result = evaluate_hsr(hsr_input)
        raw_status = raw_result.status
        now = time.monotonic()

        raw_severity = _SEVERITY[raw_status]
        current_severity = _SEVERITY[self._current_status]

        if raw_severity >= current_severity:
            # Escalating, or staying the same — instant, no exceptions.
            self._current_status = raw_status
            self._calm_reading_since = None
        else:
            # Trying to de-escalate — don't trust it immediately.
            if (self._current_status == HSRStatus.MONITOR
                    and hsr_input.distress_confidence > MONITOR_EXIT_THRESHOLD):
                self._calm_reading_since = None
            else:
                if self._calm_reading_since is None:
                    self._calm_reading_since = now
                elif now - self._calm_reading_since >= DWELL_SECONDS:
                    self._current_status = raw_status
                    self._calm_reading_since = None

        raw_result.status = self._current_status
        return raw_result
