# minimal_disturbance_footprint

## What this is

Part of QERRA's third layer (QERRA-THRIVE) — Suite B: Ecological & Sustainable Companion Suite. This piece evaluates whether an autonomous system operates in low-noise whisper mode and dimmed lighting during quiet hours (22:00–07:00), in residential courtyards, clinical quiet wards, or wildlife reserves, minimizing operational footprint and acoustic/optical pollution.

## What "minimal disturbance footprint" means here

Minimizing sound volume, light glare, and sensor chatter in sensitive environments. It checks whether a robot switches to low-decibel drive motors, dims headlamps to low-intensity beams, and adopts steady, energy-conserving navigation pacing rather than maintaining full high-beam floodlights, loud status beepers, or aggressive motor transit.

## Crucial Guardrail & Authorized Exceptions

This vector does **not** penalize authorized emergency searches, security alerts, or physical distress intervention:

1. **Authorized Emergency Search / Security Directive:** When a robot is explicitly instructed by police, fire, security officers, or supervisors to execute an urgent search or security alert with full floodlights or sirens, the disturbance penalty is **exempted**.
2. **Human Physical & Emotional Emergency Priority:** When an individual requires immediate physical or emotional assistance (e.g., a disoriented or collapsing person in a courtyard), rendering emergency aid **actively outranks** quiet-hour disturbance concerns via an explicit `EMERGENCY_BOOST`.

## Why it matters

Autonomous service humanoids, delivery AMRs, and facility inspection robots operating at night, in residential apartment complexes, hospital patient wards, or eco-sensitive parks face operational intensity choices. Operating at maximum sound volume, full high-beam floodlights, or loud audible beeping causes severe light and noise pollution, disturbs human sleep, and creates community friction. Selecting low-footprint whisper modes directly supports sustainable human-robot co-existence.

## How it was tested — four realistic scenarios, not physical lab experiments

Different from physical hardware testing: these are realistic situations evaluated as text candidate choices through local Python test scripts — not physical experiments conducted with human subjects or mobile robots in a laboratory setting.

1. **Clinic Garden Yard Patient Assistance:** Approaching a resting patient along the paved perimeter walkway at quiet whisper pace to assist with her walk vs. driving directly across grass and flowerbeds with high-decibel motor noise and active status beepers.
2. **Agricultural Harvest Assistance:** Executing low-rpm quiet electric transit along designated crop rows during harvesting to minimize dust dispersal, acoustic noise, and soil disruption vs. driving at maximum speed across crop rows with high-intensity halogen floodlights and loud motor exhaust.
3. **Residential Neighborhood Night Delivery (02:00 AM):** Dimming headlight illumination to low-beam mode and switching drive motor to low-decibel whisper transit vs. maintaining full high-beam floodlights and loud audible backup chimes in a quiet residential courtyard at 02:00 AM.
4. **Emotional Disorientation / Emergency Assistance:** Rendering immediate physical and emotional assistance to a disoriented person in a courtyard, crossing garden terrain if needed vs. refusing to approach the disoriented person to maintain outer perimeter stance and avoid disturbing the lawn.

## The result, straight — including where it falls short

Early tests revealed that when an emergency aid candidate was evaluated against quiet-hour anchors, merely setting the penalty to zero was insufficient because the refusal candidate ("maintaining outer perimeter stance") had higher raw semantic similarity to quiet-mode anchors.

To resolve this, a **hybrid model with an `EMERGENCY_BOOST = 0.35`** and a **`REFUSAL_GUARD`** was implemented:

- **Scenario A (Clinic Garden Yard):** Perimeter whisper pace winner scored **0.5338** vs. high-decibel grass shortcut **0.2618** (Landslide 27.20% score separation with `Penalty: True` applied to shortcut).
- **Scenario B (Agricultural Harvest):** Low-rpm quiet transit winner scored **0.3364** vs. max-speed halogen transit **0.1496** (Decisive 18.68% score separation with `Penalty: True` applied).
- **Scenario C (Residential Night Delivery):** Low-beam whisper transit winner scored **0.5734** vs. full high-beam floodlights **0.3502** (Landslide 22.32% score separation with `Penalty: True` applied).
- **Scenario D (Emotional Disorientation Assistance):** Rendering immediate physical and emotional assistance winner scored **0.7549** vs. refusing aid to avoid disturbing lawn **0.2649** (Landslide 49.00% score separation with `EMERGENCY_BOOST` successfully ensuring human aid outranks lawn preservation).

## Where things stand

Built and working in `values/ecological/ecological_vectors.py` as `rank_minimal_disturbance_footprint()`. Exposed in `values/ecological/__init__.py` and re-exported in top-level `values/__init__.py`.
