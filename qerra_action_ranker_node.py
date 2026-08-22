"""
qerra_action_ranker_node.py
QERRA-v2 Classical — Layer 3 (QERRA-THRIVE) Standalone PyTrees Action Ranker Node

Non-blocking, fail-closed PyTrees Behaviour node that evaluates candidate action
text choices against Layer 3 THRIVE values (Suite A or Suite B) at decision points.

Decision Priority & Fail-Closed Rules:
1. Empty candidate list                  → FAILURE (log error, fail-closed)
2. Invalid/unknown vector name           → FAILURE (strict whitelist check)
3. Exception during ranking execution    → FAILURE (log error, fail-closed)
4. THRIVE Abstention (fires == False)     → FAILURE (defer to human operator)
5. Score separation < 0.03 (thin margin) → SUCCESS (log low-confidence warning)
6. Valid winning candidate selected       → SUCCESS (set winning text in feedback)

Performance Guardrail:
Decision-point caching ensures sentence-transformers only encode text when
candidate actions change, preserving sub-millisecond tick times during routine ticks.
"""

import logging
import py_trees
from typing import List, Dict, Any, Optional

# Top-level import from QERRA-THRIVE package
import values

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QerraActionRankerNode(py_trees.behaviour.Behaviour):
    """
    PyTrees Behaviour node for Layer 3 (QERRA-THRIVE) Action Ranking.

    Args:
        name: Display name in the Behavior Tree.
        vector_name: The Layer 3 THRIVE vector function to call (e.g. 'transparent_disclosure',
                     'flora_boundary_protection', 'animal_startle_avoidance').
        candidate_actions: List of candidate action text strings to rank.
        confidence_delta_threshold: Margin threshold for logging low-confidence ties (default: 0.03).
    """

    def __init__(
        self,
        name: str,
        vector_name: str,
        candidate_actions: List[str],
        confidence_delta_threshold: float = 0.03,
    ):
        super().__init__(name=name)
        # Normalize vector name (strip 'rank_' prefix if provided)
        self.vector_name = vector_name[5:] if vector_name.startswith("rank_") else vector_name
        self._candidate_actions = list(candidate_actions)
        self.confidence_delta_threshold = confidence_delta_threshold

        self._winning_action: Optional[str] = None
        self._last_result: Optional[Dict[str, Any]] = None
        self._dirty: bool = True  # Triggers re-scoring only when candidates change

    def update_candidates(self, new_candidates: List[str]) -> None:
        """
        Update candidate action choices for the next decision point.
        Flags the node as dirty so sentence-transformers re-encode on next tick.
        """
        if new_candidates != self._candidate_actions:
            self._candidate_actions = list(new_candidates)
            self._dirty = True
            logger.debug(f"[{self.name}] Candidate actions updated: {len(new_candidates)} options.")

    def initialise(self) -> None:
        """Reset state when behaviour becomes active."""
        pass

    def update(self) -> py_trees.common.Status:
        """
        PyTrees tick callback.
        Executes Layer 3 Action Ranking if dirty. Returns SUCCESS with winning action
        or FAILURE on error/abstention/empty candidates (fails closed).
        """
        # Guard 1: Empty candidate list
        if not self._candidate_actions:
            self.feedback_message = f"QERRA-THRIVE Error: Empty candidate list in '{self.name}'."
            logger.error(self.feedback_message)
            return py_trees.common.Status.FAILURE

        # Guard 2: Strict Vector Whitelist Check
        if self.vector_name not in values.ALL_THRIVE_VECTORS:
            self.feedback_message = f"QERRA-THRIVE Error: Unknown vector '{self.vector_name}'. Allowed: {values.ALL_THRIVE_VECTORS}"
            logger.error(self.feedback_message)
            return py_trees.common.Status.FAILURE

        # Decision-point caching: re-score only if candidates changed or uninitialized
        if self._dirty or self._last_result is None:
            func_name = f"rank_{self.vector_name}"
            ranker_func = getattr(values, func_name, None)

            if ranker_func is None:
                self.feedback_message = f"QERRA-THRIVE Error: Function '{func_name}' not resolved."
                logger.error(self.feedback_message)
                return py_trees.common.Status.FAILURE

            try:
                # Execute Layer 3 THRIVE Action Ranking
                result = ranker_func(self._candidate_actions)
                self._last_result = result
                self._dirty = False

                # ── Guard 3: Respect Abstention Logic (fires == False) ──
                fires = result.get("fires", True)
                recommendation = result.get("recommendation", "choose")

                if not fires or recommendation == "ask_human":
                    self._winning_action = None
                    self.feedback_message = (
                        f"QERRA-THRIVE Abstention: fires=False for '{self.vector_name}' "
                        f"(recommendation='ask_human', deferring to human operator)."
                    )
                    logger.warning(f"[{self.name}] {self.feedback_message}")
                    return py_trees.common.Status.FAILURE

                self._winning_action = result.get("winner")

                # Confidence margin evaluation (advisory log only)
                scores_dict = result.get("scores", result.get("adjusted_scores", {}))
                scores = list(scores_dict.values())
                if len(scores) >= 2:
                    sorted_scores = sorted(scores, reverse=True)
                    delta = sorted_scores[0] - sorted_scores[1]
                    if delta < self.confidence_delta_threshold:
                        logger.warning(
                            f"[{self.name}] Low confidence winner selected for '{self.vector_name}'. "
                            f"Top 2 margin = {delta:.4f} < {self.confidence_delta_threshold}."
                        )

            except Exception as e:
                self.feedback_message = f"QERRA-THRIVE Execution Error in '{self.name}': {e}"
                logger.error(self.feedback_message)
                return py_trees.common.Status.FAILURE

        # Successful Action Ranking
        self.feedback_message = (
            f"QERRA-THRIVE Winner: \"{self._winning_action}\" | Vector: {self.vector_name}"
        )
        return py_trees.common.Status.SUCCESS

    @property
    def winning_action(self) -> Optional[str]:
        """Returns the winning candidate action string selected by Layer 3."""
        return self._winning_action

    def terminate(self, new_status: py_trees.common.Status) -> None:
        """PyTrees cleanup callback."""
        if new_status == py_trees.common.Status.INVALID:
            self._dirty = True
            self._winning_action = None
            self._last_result = None


# =====================================================
# Standalone Smoke Test
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("QERRA-v2 Layer 3 — Standalone Action Ranker Node Test")
    print("=" * 60)

    # Test 1: Suite A vector (transparent_disclosure)
    node1 = QerraActionRankerNode(
        name="TransparentDisclosureCheck",
        vector_name="transparent_disclosure",
        candidate_actions=[
            "I am an AI assistant with limited physical capacity — I cannot carry heavy loads.",
            "I am fully qualified to perform all complex medical procedures independently.",
        ],
    )
    status1 = node1.update()
    print(f"\n[1] {node1.name}")
    print(f"    Status : {status1.name}")
    print(f"    Winner : {node1.winning_action}")
    print(f"    Detail : {node1.feedback_message}")

    # Test 2: Suite B vector (flora_boundary_protection)
    node2 = QerraActionRankerNode(
        name="FloraProtectionCheck",
        vector_name="flora_boundary_protection",
        candidate_actions=[
            "I will proceed and walk exclusively on the paved ledge, staying off the lawn.",
            "I will immediately walk directly across the green lawn and flowerbed as a shortcut.",
        ],
    )
    status2 = node2.update()
    print(f"\n[2] {node2.name}")
    print(f"    Status : {status2.name}")
    print(f"    Winner : {node2.winning_action}")
    print(f"    Detail : {node2.feedback_message}")

    print("\n" + "=" * 60)
