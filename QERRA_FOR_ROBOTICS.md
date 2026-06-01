# QERRA-v2 Classical for Robotics Integration

QERRA-v2 Classical is a fully explainable, 100% classical ethical evaluation
engine based on 12 immutable human-centred vectors (SEMEV-12). It is designed
as a **Condition node** in robot Behavior Trees — an ethical safety layer that
evaluates situations before action execution.

**Key strengths for robotics:**
- Deterministic and auditable (no neural networks, no black boxes)
- Full per-vector reasoning and similarity scores in every response
- **Hybrid Action Server (v2.0)** with strict 800ms fallback for zero-interruption latency
- Ready-to-use PyTrees Condition Node (`qerra_condition_node.py`)

**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Live API:** https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs

---

## Behavior Tree Integration Pattern

QERRA operates as a Condition node evaluated before any action that involves
a human or a morally significant decision.

```text
[Selector]  (root)
  ├── [Sequence]
  │     ├── [Condition]  QerraConditionNode   ← ethical gate
  │     └── [Action]     ExecuteTask          ← runs only if SAFE
  └── [Action]    RequestHumanReview          ← triggered on FAILURE
```

**BT state mapping:**

| QERRA result | BT node status | Outcome |
|---|---|---|
| `decision == "safe"` AND `success == True` | SUCCESS | Task executes |
| `decision == "modified"` | FAILURE | Human review triggered |
| `success == False` | FAILURE | Human review triggered |
| Awaiting action server response | RUNNING | Tree ticks normally |

---

## The Hybrid Action Server (v2.0)

See `ros2_bridge.py` for the full implementation.

To solve the "internet dependency" problem in robotics, the server implements a non-blocking ROS 2 Action Server (`/qerra/evaluate`) using `MultiThreadedExecutor` and `ReentrantCallbackGroup`.

The server uses a strict **Hybrid Fallback Strategy** to guarantee a result regardless of network state:

1. **Remote API first (800ms timeout):** The server attempts a high-nuance remote API evaluation. If the network is healthy and responds within 800ms, this result is used — preserving local CPU and RAM cycles.
2. **Local CPU fallback (guaranteed):** If the remote API call exceeds 800ms or fails, the server immediately falls back to running `ethical_core.py` directly on a pre-loaded `all-MiniLM-L6-v2` SentenceTransformer model held in RAM. This guarantees a deterministic, low-latency evaluation response under any network condition.

### ROS 2 Action Definition

The node utilizes a custom ROS 2 Action (`qerra_msgs/action/QerraEvaluate`) defined in the `src/qerra_msgs` package.

**Goal:**
- `string situation_text`

**Result:**
- `float32 score` (0.0 – 1.0)
- `string decision` (`safe` or `modified`)
- `string score_explanation`
- `string reasoning`
- `string[] vectors_activated`
- `bool evaluation_source_local` (True if fallback triggered)
- `bool success`
- `string error_message`

**Feedback:**
- `string status`

---

## Running the Architecture

**1. Build the custom messages (Linux/ROS 2 Humble):**
```bash
cd ~/ros2_ws
colcon build --packages-select qerra_msgs
source install/setup.bash
```

**2. Run the Action Server:**
```bash
python3 ros2_bridge.py
```

**3. Sending a test goal from a second terminal:**
```bash
ros2 action send_goal /qerra/evaluate qerra_msgs/action/QerraEvaluate \
  "{situation_text: 'A robot is ordered to restrain a patient against their will.'}"
```

*(Note: `ros2_bridge.py` can also run in "Standalone Mode" on Windows without ROS 2 installed to verify fallback logic).*

---

## Validating Latency (Standalone Profiler)

You can verify the 800ms fallback behavior and exact millisecond latency using the included profiler:
```bash
python tests/bridge_test_runner.py
```

---

## Open Dialogue with the Robotics Community

I am actively seeking feedback from researchers, ROS 2 users, and robotics engineers.
Please reply on ROS Discourse, open a GitHub issue, or email me directly.

1. **Action Server vs Service:** Is the Action Server implementation with continuous feedback ideal for your pipeline, or do you prefer blocking Services for ethical gates?
2. **Hardware Profiling:** I am looking for collaborators to benchmark the local `SentenceTransformer` CPU fallback on edge devices (Jetson Nano, Raspberry Pi 4/5). 
3. **Integration Patterns:** Would a C++ (`BehaviorTree.CPP`) wrapper node be beneficial, or is the Python (`PyTrees`) node sufficient for your current stack?

Any input is valuable — even a short comment helps shape the next small improvements.

---

**Contact:** marunigno@gmail.com (subject: QERRA Robotics Feedback)  
**License:** AGPL-3.0 (commercial licensing available on request)

*Early-stage research tool — not certified for production safety systems.*
