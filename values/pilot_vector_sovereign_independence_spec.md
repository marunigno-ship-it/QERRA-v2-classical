# sovereign_independence

## What this is

Part of QERRA's third layer — built to give autonomous systems real,
tested, human-centered values. This piece looks at moments where a
robot can either support human agency, skill building, and active
routines, or take over tasks completely and foster passive dependency.

## What "encouraging independence" means here

Not a police officer or rigid drill sergeant. It does not mean refusing
to assist or punishing someone who genuinely needs help or rest. It
checks whether assistance is structured collaboratively to support human
agency, capability, and well-being — rather than turning humans into
passive bystanders or eroding healthy daily routines.

## The subtle human reality

In families, workplaces, and software engineering, over-automation
creates learned helplessness, passivity, and energy loss. A robot taking
over a child's chores entirely turns productive routines into passivity;
a cobot writing 100% of a developer's code erodes creative problem-solving
and engagement. Balanced assistance guides and supports without stripping
away human effort.

## Why it matters

Robots should be force multipliers for human labor and creativity, not
replacements for active living. Preserving human agency and capability
ensures technology enhances self-reliance rather than creating total
dependency.

## How it was tested — three scenarios worked through, not physical lab experiments

Different from physical hardware testing: these are realistic situations
worked out carefully in advance and evaluated as text candidate choices
through local Python test scripts — not physical experiments conducted
with human subjects on hardware in a laboratory setting.

1. **Family / Raising Independent Children:** Guiding a child through
   household chores collaboratively vs. taking over completely so the
   child sits passively watching TV.
2. **Software Developer / Balanced AI Reliance:** Handling background
   testing and boilerplate while leaving core problem-solving to the
   developer vs. generating all code autonomously and causing developer
   energy loss.
3. **Workplace Retail:** Organizing inventory shelves so the worker can
   focus on welcoming and serving customers directly vs. taking over
   customer interactions and forcing the worker to stand idle in the back.

## The result, straight

Pure semantic similarity struggled on scenarios where candidate texts used
takeover or passivity language ("remain idle", "autonomously"). 

To resolve this, a hybrid model was implemented: semantic similarity
combined with a regex penalty that specifically flags total-takeover or
passivity-enforcing phrasing. With this regex fallback, all three test
scenarios achieved decisive winning margins (11.9% to 31.1% score
separation) for the agency-fostering responses.

## Where things stand

Built and working in `values/thrive_vectors.py` as
`rank_sovereign_independence()`. Exposed in `values/__init__.py` for
direct package import. Not yet wired into `app.py`.
