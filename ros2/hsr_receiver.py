# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
ROS 2 package shim for gate.hsr_receiver.

Maintains 100% backward compatibility for ROS 2 nodes and test suites importing
HsrReceiver from ros2.hsr_receiver while the pure-Python core lives in gate/.
"""
from __future__ import annotations

from gate.hsr_receiver import (
    DEFAULT_HSR_PORT,
    MAX_DATAGRAM_BYTES,
    MAX_DRAIN_PER_CALL,
    MAX_REJECTION_REASON_CHARS,
    HsrReceiver,
    _self_test,
)

__all__ = [
    "DEFAULT_HSR_PORT",
    "MAX_DATAGRAM_BYTES",
    "MAX_DRAIN_PER_CALL",
    "MAX_REJECTION_REASON_CHARS",
    "HsrReceiver",
]

if __name__ == "__main__":
    _self_test()
