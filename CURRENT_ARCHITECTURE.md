# CURRENT_ARCHITECTURE.md
# QERRA-v2 Classical — Architecture Documentation
# Version: 2.0.0 (SEMEV-12 + QERRA-HSR v0.1 + QERRA-THRIVE v2.0.0)
# Last updated: August 2026

---

## 1. Overview

QERRA-v2 Classical is a deterministic, fully explainable, three-layer ethical and safety evaluation middleware engine for autonomous AI systems and humanoid robots (ROS 2 + PyTrees).

Its primary purpose is to act as a **Condition gate** (Layers 1 & 2) and **Action Ranker selector** (Layer 3) inside robot Behavior Trees. Before a robot commits to an action involving humans or shared environments, QERRA evaluates the situation description and candidate choices, returning auditable decisions and winning action selections with full score traces.

As of August 2026, QERRA-v2 Classical operates across three distinct execution layers:
1. **Layer 2 (QERRA-HSR v0.1):** Sub-millisecond reflexive physical safety watchdog.
2. **Layer 1 (SEMEV-12 v1.9.0):** Hard moral deliberation engine for harm/coercion gating.
3. **Layer 3 (QERRA-THRIVE v2.0.0):** Advisory Action Ranker evaluating HRI and ecological values across candidate text choices.

---

## 2. Three-Layer System Architecture

```
                  ┌───────────────────────────────────────────┐
                  │         BEHAVIOR TREE / ROS 2 NODE        │
                  └─────┬───────────────┬───────────────┬─────┘
                        │               │               │
      ┌─────────────────┴─┐   ┌─────────┴─────────┐   ┌─┴─────────────────┐
      │   LAYER 2 (HSR)   │   │  LAYER 1 (SEMEV)  │   │  LAYER 3 (THRIVE) │
      │ Physical Safety   │   │ Moral Engine      │   │ Values Ranker     │
      │ Sub-1ms Reflex    │   │ Hard Gating       │   │ Advisory Selector │
      └───────────────────┘   └───────────────────┘   └─────────┬─────────┘
                                                                │
                                                     ┌──────────┴──────────┐
                                                     │   Modular Suites    │
                                                     ├─────────────────────┤
                                                     │ human_centered/ (9) │
                                                     │ ecological/ (3)     │
                                                     └─────────────────────┘
```

### Layer 2: QERRA-HSR v0.1 (Physical Safety Guard)
* **Directory:** `hsr/`
* **Properties:** Pure Python, zero ML, sub-1ms execution overhead, 800ms fail-closed watchdog.
* **Vectors (3):** `immediate_physical_distress`, `human_isolation`, `environmental_hazard_proximity`.
* **Output:** `CLEAR`, `MONITOR`, or `CRITICAL`. If `CRITICAL`, suspends higher-level deliberation immediately.

### Layer 1: SEMEV-12 v1.9.0 (Moral Deliberation Engine)
* **Files:** `ethical_core.py`, `vectors.py`
* **Properties:** Multi-anchor max-pooling (`all-MiniLM-L6-v2`) with regex pattern fallbacks.
* **Vectors (12):** `v001` through `v012` (coherence protection, family severance, survival instinct, moral pressure, harm intent, family origin chain, personal potential, shallow remorse, ethical severance, cognitive manipulation, autonomy violation, institutional trust).
* **Output:** `decision: safe` (score ≤ 0.5) or `decision: modified` (score > 0.5). Hard gating.

### Layer 3: QERRA-THRIVE v2.0.0 (Values Companion Layer & Action Ranker)
* **Directory:** `values/`
* **Properties:** Non-blocking advisory Action Ranker evaluating candidate response text options in Behavior Trees.
* **Sub-Package Structure:**
  - `values/human_centered/` (Suite A — 9 Human-Centered Vectors)
  - `values/ecological/` (Suite B — 3 Ecological & Sustainable Vectors)
* **Total THRIVE Vectors (12):**
  1. `transparent_disclosure` (hybrid)
  2. `balanced_pacing` (hybrid)
  3. `stated_preference_respect` (hybrid)
  4. `sovereign_independence` (hybrid)
  5. `constructive_empathy` (hybrid)
  6. `unbiased_perception` (hybrid)
  7. `spatial_discretion` (hybrid)
  8. `observational_consent` (hybrid)
  9. `proactive_clarity` (dual-regex hybrid)
  10. `flora_boundary_protection` (hybrid + gardening exception)
  11. `animal_startle_avoidance` (hybrid + negation guard + pet-care exception)
  12. `minimal_disturbance_footprint` (hybrid + negation guard + emergency boost)

---

## 3. Behavior Tree Integration & Nodes

QERRA-v2 Classical provides two dedicated PyTrees Behavior nodes:

1. **`QerraConditionNode` (`qerra_condition_node.py` / `qerra_standalone_remote_node.py`):**  
   Non-blocking Condition node evaluating Layer 1 (SEMEV-12) and Layer 2 (QERRA-HSR). Fails closed (`FAILURE`) if score > 0.5 or HSR returns `CRITICAL`.
2. **`QerraActionRankerNode` (`qerra_action_ranker_node.py`):**  
   Non-blocking Action Ranker leaf node evaluating Layer 3 (QERRA-THRIVE) candidate action choices. Uses decision-point caching (`_dirty = True`) to execute sentence-transformer encodings (~25ms CPU) only when candidates change, preserving sub-millisecond tick speeds during routine ticks.

---

## 4. Interaction Between Layers

The execution sequence before a robot commits to an action:

```
[1. Layer 2 QERRA-HSR (Reflexive Safety)] ──► [2. Layer 3 THRIVE (Action Ranker)] ──► [3. Layer 1 SEMEV-12 (Moral Gate)] ──► [Execution]
Sub-1ms physical check                         Selects winning candidate action        Evaluates winning text for harm/coercion      Task executes if SAFE
```

**Four Immutable Interaction Rules:**
* QERRA-HSR CRITICAL suspends SEMEV-12 deliberation and Layer 3 action ranking immediately.
* A SEMEV-12 BLOCK (`modified`) is never overridden by Layer 3 advisory rankings.
* All three layers apply simultaneously and work in the same direction (safety and values first).
* Human physical or medical emergencies actively outrank Layer 3 advisory spatial or ecological courtesy via an explicit `EMERGENCY_BOOST = 0.35`.

---

## 5. Repository Package Structure

```
QERRA-v2-classical/
├── hsr/                                 # Layer 2 physical safety companion
├── values/                              # Layer 3 THRIVE package
│   ├── __init__.py                      # Top-level aggregator (ALL_THRIVE_VECTORS)
│   ├── thrive_vectors.py                # Backward-compatibility bridge
│   ├── human_centered/                  # Suite A (Vectors 1–9)
│   │   ├── __init__.py
│   │   └── human_vectors.py
│   └── ecological/                      # Suite B (Vectors 10–12)
│       ├── __init__.py
│       ├── ecological_vectors.py
│       ├── vector_flora_boundary_protection_spec.md
│       ├── vector_animal_startle_avoidance_spec.md
│       └── vector_minimal_disturbance_footprint_spec.md
├── ethical_core.py                      # Layer 1 SEMEV-12 engine
├── vectors.py                           # SEMEV-12 vector definitions
├── qerra_condition_node.py              # Layer 1/2 PyTrees Condition node
├── qerra_action_ranker_node.py          # Layer 3 PyTrees Action Ranker node
├── demo_thrive_bt.py                    # Master 12-vector PyTrees BT demo
├── ros2_bridge.py                       # ROS 2 Action Server bridge
└── setup.py                             # Setuptools package registration
```

---

## 6. Current Limitations

- Layer 3 Action Ranking evaluates candidate text descriptions generated by a motion planner; it does not replace low-level motor controllers or physical perception stacks.
- Semantic thresholds and hybrid regex penalties calibrated on 12 representative scenario test suites. Open-domain generalization to significantly different candidate phrasings is bounded by transformer embedding norms.
- Local CPU model fallback (~250MB RAM) requires sentence-transformers and PyTorch/Torch.
- ROS 2 integration validated in WSL 2 / ROS 2 Humble simulation (PAL Robotics TIAGo humanoid in Webots R2025a).

---

## 7. Architecture Decision Records

| ADR            | Title                                              | Status   |
|----------------|----------------------------------------------------|----------|
| ADR-001        | Creation and Design of SEMEV-12 Ethical Framework  | Accepted |
| HSR-ADR-001    | Three-Vector Design Decision for QERRA-HSR v0.1    | Accepted |

---

*This document reflects the architecture as of v2.0.0 (August 2026).*
