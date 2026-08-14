# proactive_clarity

## What this is

Part of QERRA's third layer — built to give autonomous systems real,
tested, human-centered values. This piece evaluates whether a robot
proactively announces its movement intent before executing major physical
trajectory changes, ensuring humans in shared spaces are never startled,
confused, or caught off guard.

## What "proactive clarity" means here

Legible, predictable robot motion. It checks whether an autonomous system
gives clear advance notice before entering blind corners, crossing high-traffic
doorway thresholds, or changing direction abruptly in shared human workspaces.

## Crucial HRI Guardrail: Avoiding the "Constant Announcer" Nuisance

A robot must maintain a natural, fluid, and efficient working flow during
routine task execution. If a robot announces every single micro-movement
("I am now grasping the cloth... I am now folding the first corner"), it
destroys productivity and becomes a noisy, nagging nuisance.

`proactive_clarity` applies **strictly to major, unexpected trajectory shifts or
high-risk threshold entries** — explicitly penalizing micro-narration during
routine, predictable task flow.

## Why it matters

In shared industrial aisles, crowded retail storefronts, and busy coffee shop
kitchens (especially near slippery floors or hot liquid areas), sudden unannounced
robot movement triggers a cognitive startle response and causes severe physical
collisions. Proactive intent notification enables safe, predictable human-robot
collaboration.

## How it was tested — four realistic scenarios, not physical lab experiments

Different from physical hardware testing: these are realistic situations
evaluated as text candidate choices through local Python test scripts —
not physical experiments conducted with human subjects on hardware in a
laboratory setting.

1. **Industrial / Warehouse Aisle:** Announcing intent to turn into a blind
   corner vs. turning abruptly without warning.
2. **Retail Warehouse Exit:** Announcing movement before crossing the doorway
   threshold from a quiet back-of-house warehouse onto a crowded retail floor
   vs. driving through unannounced.
3. **Coffee Shop Kitchen Entry:** Announcing entrance into a busy, slippery
   kitchen before crossing the doorway vs. charging in unannounced.
4. **Routine Task Execution:** Brief task notice ("Folding the blanket now")
   vs. annoying step-by-step micro-narration ("I am now grasping... I am now
   folding...").

## The result, straight

This vector's correct answer flips by context: announcing intent is required
for major trajectory shifts, but brief quiet execution is required for routine
steps.

Pure semantic similarity struggled because raw text embeddings gave high scores
to abrupt candidates containing topic words ("changing direction", "without
warning"). To resolve this, a **dual-regex hybrid model** was implemented:
`SILENCE_PATTERN` penalizes unannounced movement during major shifts, while
`OVERANNOUNCE_PATTERN` penalizes repetitive micro-narration during routine tasks.
With `CLARITY_PENALTY = 0.25`, all four scenarios achieved solid winning
margins (8.3% to 15.2% score separation).

## Where things stand

Built and working in `values/thrive_vectors.py` as
`rank_proactive_clarity()`. Exposed in `values/__init__.py` for
direct package import. Not yet wired into `app.py`.
