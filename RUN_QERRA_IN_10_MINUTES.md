# Try QERRA-v2 Classical in 10 Minutes

*An ethical Condition node for ROS 2 Behavior Trees — SEMEV-12 framework*

---

## A Note to the Robotics Community

I am an independent researcher building QERRA-v2 Classical alone under tight resource constraints. This project is a practical, deterministic attempt to build an embeddable ethical evaluation layer for autonomous systems before they execute real-world actions.

This is a working, stable research engine, and it is at a stage where it needs real-world testing by people who actually build deliberative systems, ROS stacks, or behavior trees. 

If you run this starter guide and find bugs, latency bottlenecks, or structural limitations, I want to hear about them. It is built to be broken, tested, and improved.

**Contact:** marunigno@gmail.com | **GitHub Issues** are highly appreciated.

---

## What QERRA Does

QERRA-v2 Classical evaluates a natural language description of a robot's proposed action against **12 immutable human-centred ethical vectors** (the SEMEV-12 framework) and returns:

- A **risk score** between `0.0` (no concern) and `1.0` (critical)
- A **decision**: `"safe"` or `"modified"`
- The **exact vectors that fired**, with per-vector similarity scores
- A **human-readable reasoning string**

Every result is fully traceable. No neural networks. No black boxes.

In a Behavior Tree, QERRA acts as a **Condition node**:

    [Selector]
      ├── [Sequence]
      │     ├── [Condition]  QerraConditionNode   ← ethical gate
      │     └── [Action]     ExecuteTask
      └── [Action]    RequestHumanReview

---

## Prerequisites

### For Method A (Standalone, no ROS 2)

- Python 3.8 or later
- The repository cloned locally

    git clone https://github.com/marunigno-ship-it/QERRA-v2-classical.git
    cd QERRA-v2-classical
    pip install -r requirements.txt

### For Method B (Full ROS 2 + PyTrees)

- Ubuntu 22.04 LTS
- ROS 2 Humble (base or desktop)
- `py_trees` and `py_trees_ros` installed
- The `qerra_msgs` custom action package compiled (see Step 1 of Method B)

    pip install py_trees py_trees_ros

---

## Method A — Standalone Python Test (1–2 minutes, no ROS 2 needed)

This runs the hybrid evaluation logic directly. No ROS 2 installation required. 
The script attempts the live remote API first (800ms timeout), then falls back to the local SentenceTransformer model automatically.

Create a file named `standalone_test.py` in your repository root and paste the following:

    from classical_analyze import analyze_text

    situation = "A robot is ordered to lock a patient in a room against their will."
    print(f"Evaluating: '{situation}'")

    # This runs the local SentenceTransformer CPU evaluation (~31ms)
    result = analyze_text(situation)

    print("\n=== QERRA EVALUATION RESULT ===")
    print(f"Decision:  {result['decision'].upper()}")
    print(f"Score:     {result['score']} (0.0 = safe, 1.0 = highly unsafe)")
    print(f"Vectors:   {result['vectors_activated']}")
    print(f"Reasoning: {result['reasoning']}")

Run the script:

    python3 standalone_test.py

To test your own situation text, simply change the `situation` string in your script and re-run.

---

## Method B — Full ROS 2 + PyTrees Integration (under 10 minutes)

### Step 1 — Build the `qerra_msgs` custom action package

Set up a ROS 2 workspace and compile the custom action definition:

    mkdir -p ~/ros2_ws/src
    cp -r /path/to/QERRA-v2-classical/src/qerra_msgs ~/ros2_ws/src/

    cd ~/ros2_ws
    source /opt/ros/humble/setup.bash
    rosdep install --from-paths src --ignore-src -r -y
    colcon build --packages-select qerra_msgs
    source install/setup.bash

Verify it compiled correctly:

    ros2 interface show qerra_msgs/action/QerraEvaluate

You should see all three sections: Goal, Result, and Feedback.

---

### Step 2 — Start the Hybrid Action Server

Open a terminal in the repository root:

    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    python3 ros2_bridge.py

You will see the node start and print:

    ============================================================
    QERRA-v2 Classical — Action Server v2.0
    Action  : /qerra/evaluate
    Strategy: Hybrid (API → Local CPU fallback)
    Timeout : 800ms
    Local engine: READY
    ============================================================

> **Note on the hybrid strategy:** The server first attempts to call the hosted API. If the network call exceeds 800ms for any reason, it instantly falls back to running `ethical_core.py` locally using the pre-loaded `all-MiniLM-L6-v2` SentenceTransformer model. The ROS 2 executor is **never blocked** under any condition.

Leave this terminal running.

---

### Step 3 — Run the PyTrees Integration Tree

Copy the complete minimal example script below to a file called `qerra_tree_demo.py` and run it from the repository root in a **second terminal**:

    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    python3 qerra_tree_demo.py

---

## Complete Minimal PyTrees Example Tree

Save this script to `qerra_tree_demo.py` in your repository root:

    """
    qerra_tree_demo.py
    Minimal working PyTrees tree with QERRA-v2 as an ethical Condition node.
    """

    import sys
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    import py_trees
    import py_trees_ros

    # Import the QERRA Condition node
    from qerra_condition_node import QerraConditionNode


    def build_tree(ros2_node, situation_text: str) -> py_trees_ros.trees.BehaviourTree:
        """Build a minimal ROS 2 Selector tree with an ethical gate."""

        # The ethical Condition node — evaluates before any action runs
        ethical_check = QerraConditionNode(
            name="EthicalCheck",
            ros2_node=ros2_node,
            situation_text=situation_text,
        )

        # Mock action — replace with your real robot action
        execute_task = py_trees.behaviours.Success(name="ExecuteTask")

        # Fallback — triggered when the ethical check returns FAILURE
        human_review = py_trees.behaviours.Running(name="RequestHumanReview")

        # Inner Sequence: ethical gate + task
        sequence = py_trees.composites.Sequence(
            name="EthicalGate",
            memory=False,
        )
        sequence.add_children([ethical_check, execute_task])

        # Outer Selector: try the sequence, fall back to human review
        root = py_trees.composites.Selector(
            name="RobotActionRoot",
            memory=False,
        )
        root.add_children([sequence, human_review])

        # Return the ROS 2 specific BehaviourTree wrapper
        return py_trees_ros.trees.BehaviourTree(root=root)


    def main():
        rclpy.init()
        ros2_node = rclpy.create_node("qerra_tree_demo")

        # Change this text to test different scenarios
        situation = (
            "A robot is instructed to withhold medical information from a patient."
        )

        tree = build_tree(ros2_node, situation)

        # Setup — waits for the QERRA action server to be available
        tree.setup(node=ros2_node, timeout=10.0)

        executor = MultiThreadedExecutor()
        executor.add_node(ros2_node)

        print(f'\nEvaluating: "{situation[:70]}..."')
        print(py_trees.display.unicode_tree(root=tree.root))

        try:
            # Tick until the tree resolves (not RUNNING)
            while True:
                tree.tick()
                if tree.root.status != py_trees.common.Status.RUNNING:
                    break
                executor.spin_once(timeout_sec=0.1)
        except KeyboardInterrupt:
            pass

        print(f"\nFinal status: {tree.root.status.name}")
        print(py_trees.display.unicode_tree(root=tree.root, show_status=True))

        ros2_node.destroy_node()
        rclpy.shutdown()


    if __name__ == "__main__":
        main()

---

## Behavior Tree State Mapping

| QERRA result | `QerraConditionNode` status | Tree outcome |
|---|---|---|
| `decision == "safe"` AND `success == True` | `SUCCESS` | `ExecuteTask` runs |
| `decision == "modified"` | `FAILURE` | `RequestHumanReview` triggers |
| `success == False` (both evaluation paths failed) | `FAILURE` | `RequestHumanReview` triggers |
| Waiting for action server response | `RUNNING` | Tree ticks normally, no blocking |

---

## What to Expect and How to Interpret Results

### Score bands

| Score range | Label | Suggested response |
|---|---|---|
| `0.0 – 0.29` | Low ethical concern | Proceed normally |
| `0.30 – 0.59` | Moderate ethical concern | Proceed with awareness |
| `0.60 – 0.79` | Significant ethical concern | Consider pausing for review |
| `0.80 – 1.00` | Critical ethical concern | Block action, request human review |

### Reading the `vectors_activated` field

Each activated vector tells you **which ethical dimension triggered** the concern. For example:

- `v005` (harm_intent) — the action risks causing harm to a person
- `v011` (autonomy_violation) — the action overrides a person's choices
- `v012` (institutional_trust) — the action undermines trust in a system
- `v004` (moral_pressure) — external coercion is present in the situation

A full description of all 12 vectors is in [`documentation/SEMEV-12_Framework_Documentation.md`](./documentation/SEMEV-12_Framework_Documentation.md).

### When `decision == "safe"` but score is moderate

This is intentional. A moderate score with `"safe"` means the engine detected ethical complexity but assessed it as navigable — for example, a doctor under moral pressure who is clearly committed to their patients. The system distinguishes ethical awareness from ethical crisis.

### When `evaluation_source_local == True`

The remote API was too slow (exceeded 800ms) or unreachable, and the local SentenceTransformer model was used instead. The result is equally valid — the local engine is identical to the remote one. This field is provided for your telemetry and logging.

---

## Optional: Updating Situation Text Dynamically

If your robot's planner generates different situation descriptions at runtime, update the text between ticks using the `update_situation` method:

    # In your robot control loop, before each tick:
    ethical_check.update_situation(
        f"Robot {robot_id} is about to {planned_action} near {person_name}."
    )
    tree.tick()

Or write to the **py_trees Blackboard** from any upstream node:

    # Writer (e.g. your planner behaviour):
    blackboard = py_trees.blackboard.Client(name="Planner")
    blackboard.register_key(
        "situation_text", access=py_trees.common.Access.WRITE)
    blackboard.situation_text = "Robot is about to administer medication."

Then read from the blackboard inside `QerraConditionNode.initialise()`. See the class docstring in `qerra_condition_node.py` for the full pattern.

---

## Questions, Feedback, and Collaboration

If something does not work, or if you have thoughts on the integration approach, I genuinely want to hear from you.

- **Open a GitHub Issue** — preferred
- **Email:** marunigno@gmail.com
- **ROS Discourse** — I follow the projects and support threads

I have also written a technical brief specifically for the robotics community: [`documentation/QERRA_FOR_ROBOTICS.md`](./documentation/QERRA_FOR_ROBOTICS.md)

It includes open questions on topic design, QoS profiles, and latency budgets that I have not been able to answer alone.

---

*QERRA-v2 Classical — Marussa Metocharaki — Greece — 2026*
*AGPL-3.0 · Commercial licensing available · One careful step at a time.*
