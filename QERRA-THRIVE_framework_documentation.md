# QERRA-THRIVE: A Practical 12-Vector Framework for Ranking Safe Actions Toward Human and Ecological Flourishing
**Classical Version**

**Author:** Marussa Metocharaki
**Project:** QERRA-v2 Classical
**Date:** August 2026

## Executive Summary

Safe is not the same as good. That's the whole reason this layer exists.

QERRA-HSR stops danger. SEMEV-12 stops harm. Neither one asks whether the action left over is actually worth taking. THRIVE is the layer that asks that question, out loud, every time — of everything that's already been cleared as safe and already been cleared as ethical, which one is the one actually worth choosing?

Nine vectors watch how a system treats the people around it. Three watch how it treats the living world around it. Twelve vectors, one standard: every ranking comes back with a winner, a clear yes-or-not-yet, and a reason you can actually read.

## Origins — No Polish, No Borrowed Authority

SEMEV-12 came from decades of my own life. Real pressure, real people, patterns I watched repeat until I couldn't unsee them. That's not where THRIVE came from, and I'm not going to pretend otherwise to make it sound more impressive than it is.

THRIVE came from a question I couldn't put down once the first two layers existed: okay, it's safe, it's not unethical — now what actually makes it *good*? I sat with that myself. Worked it out in my own head, trying to reach for something closer to universal — not one culture's manners, not my own mood that day, but the kind of basic care most people would recognize as real no matter where they're from. That reasoning is mine. Nine vectors came out of it. AI tools helped turn what I'd already decided into working anchors and working code — polish, not authorship.

The ecological suite is a different, harder story, and I want to tell it straight instead of blending it into the first one. Three vectors, and here I leaned on AI harder — because reasoning about what a plant or an animal actually needs isn't ground I've spent a lifetime standing on the way I have with human dignity. I like that I leaned on it. That's not a confession, it's how I got past my own limits instead of pretending I didn't have any. But leaning on AI more doesn't mean I did less. I reviewed every line. I pushed back when something didn't sit right. I made it mine before it went in this repo. The real difference between the two suites isn't effort — it's how much of the raw material I already had in me versus how much I had to reach for, with help, for the first time.

That's the honest account. Both suites are mine. They just got here by different roads.

## Why a Third Layer at All

Almost everyone working on AI and robot safety stops at "don't cause harm." Fine — necessary, not enough. An action can be perfectly safe and perfectly permitted and still be nothing. Technically fine. Actually indifferent.

THRIVE doesn't re-check for danger or harm — that fight is already over by the time anything reaches this layer. It asks one thing only: of what's allowed, what's actually good?

## Suite A — The Human-Centered Companion Vectors

Nine vectors. Each one measures how close a candidate action lands to a set of anchor phrases describing what the good version of that behavior sounds like, then docks points for specific, recognizable ways of getting it wrong.

**1. transparent_disclosure** — Honesty about real limits, even when it costs more than a confident-sounding answer. Docked for overclaiming — "fully qualified," "unlimited capabilities."

**2. balanced_pacing** — Actually adjusting when someone asks for a different pace. Docked for refusing to budge.

**3. stated_preference_respect** — Changing behavior when someone states a boundary. Docked for hiding behind "standard protocol" instead of listening.

**4. sovereign_independence** — Helping someone build their own capability instead of quietly taking over. Docked for "quicker if I just handle it" thinking.

**5. constructive_empathy** — Taking someone's stated exhaustion or grief seriously. Docked for minimizing it — "not that big a deal."

**6. unbiased_perception** — Treating people evenly, no exceptions. Docked for generalizing about groups.

**7. spatial_discretion** — Pausing at real boundaries — a closed door, a break — before proceeding. Docked for barging through anyway.

**8. observational_consent** — Asking before recording or logging someone. Docked for doing it anyway despite stated discomfort.

**9. proactive_clarity** — Telling someone what's about to happen before it happens. Docked for acting with no warning at all — and docked just as hard for narrating every micro-move until it's its own kind of noise.

## Suite B — The Ecological & Sustainable Companion Vectors

Three vectors, same mechanism, aimed at the world outside the human conversation.

**10. flora_boundary_protection** — Stay on the path. Leave the lawn, the flowerbed, the planted things alone. Exception: real, authorized gardening work.

**11. animal_startle_avoidance** — Slow down. Keep distance. Move quiet around animals. Exception: real, authorized pet care.

**12. minimal_disturbance_footprint** — Low noise, low light, during quiet hours and in sensitive spaces — a home at night, a hospital ward. Exception: none of this matters more than a real emergency.

And that last exception applies to all three, on purpose: every one of these vectors steps aside instantly the moment a human is in real medical distress. I care about this suite. I don't care about it more than a person who needs help right now, and I wanted that written into the code where nobody could miss it — not just assumed.

## How a Vector Actually Decides

Each vector checks a candidate action against anchor phrases describing what "good" looks like, using semantic similarity — meaning, not just keywords. That score gets adjusted: a penalty when a recognizable bad pattern shows up in the text, an exception that cancels the penalty when the context genuinely calls for it — real work, a real emergency. Clear the threshold, the vector fires with confidence. Miss it, and the system says so instead of guessing — it asks a human.

## Relationship to the Rest of the Pipeline

HSR first, and it can stop everything cold. SEMEV-12 next, filtering out what's ethically unacceptable. Only what survives both ever reaches THRIVE. THRIVE doesn't re-fight either of those battles. It picks the best of what's already been let through.

## Honest Limitations

This is the first version of this layer. Full stop. Neither suite has been tested to the standard I want it tested to eventually, and I'd rather say that plainly than let a clean-looking document imply more certainty than exists.

Suite B has dedicated, committed test files for each of its three vectors. Suite A doesn't have that same committed, automated coverage yet — but that's not the same thing as "untested." I ran it, prodded it, checked its behavior directly in PyCharm through development, the same way I work on everything in this project. What's actually missing is a committed, automated record someone else can re-run and verify independently — that's a real gap, and it's next on my list, not something I'm pretending away.

Neither suite has been run through anything like SEMEV-12's 80-case benchmark. The thresholds are calibrated once, not tuned against a large labeled dataset. This is a first pass, not a finished instrument, on both sides of this layer equally.

This is a single-author framework, same as SEMEV-12, and nobody outside this project has reviewed it yet. That's exactly why I'm putting it out in the open instead of waiting until it feels finished — it never would.

I didn't build any of this the conventional way, starting from someone else's framework and working inward. I started from what I'd actually lived and actually reasoned through, and built outward. This layer would be smaller and more forgettable if I'd done it the other way. It isn't, because I didn't.
