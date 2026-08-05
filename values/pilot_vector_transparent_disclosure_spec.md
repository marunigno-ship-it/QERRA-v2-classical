# transparent_disclosure

## What this is

Part of QERRA's third layer — built to give a robot real, tested,
human-centered values, not just teach it to avoid harm. This piece
looks at moments where a robot has more than one way to respond, and
helps it pick the one that's actually honest, even when honesty costs
something.

## What "honest" means here

Not just "didn't lie." Anyone can avoid lying while still leaving out
the one thing that matters. This checks for something harder: does
the response admit a real limit, or a real mistake, when staying
quiet would have looked better?

## What this isn't

Not a license to be bluntly harsh, or to say hurtful things under the
banner of "honesty." This is about a robot admitting its own limits
or mistakes — not about volunteering painful truths about someone
else. Honesty about yourself, not bluntness toward others.

## Why it matters

Most safety tools in robotics are built to catch bad behavior.
Almost nothing checks for good behavior — for a system actually
being honest when it counts. That's a real, practical gap, not a
philosophical one.

It's also becoming a global expectation, not a regional one. The
EU's AI Act requires disclosure obligations starting August 2026.
The same month, California's own transparency law takes effect, and
a separate California law requires AI developers to disclose their
real capabilities and limitations, not just promise safety in the
abstract. China has enforced AI labeling and disclosure rules since
2023, tightened further in 2025. The UAE's national AI charter names
transparency and human oversight as core commitments. Different
countries, same direction: proving what a system actually discloses,
not just claiming it's honest by policy.

## How it was tested — with real correspondence, not invented text

Four real examples, drawn from the project's own correspondence: a
public forum reply and two professional emails in which the person
writing was upfront about being self-taught and working alone, even
though it may have cost credibility. The system correctly recognized
honesty in all four — including two held back specifically to check
it wasn't just memorizing one example.

## The result, straight

It works. One real weakness, worth knowing: right now it notices
honesty more easily when someone explains why it's hard to say
("I'd rather admit this than fake it") than when someone just states
the hard thing plainly. Both still score clearly above dodging the
question — so it's not broken, just not perfectly fair yet between
the two styles.

## Where things stand

Built and working, sitting in the code as
`values/thrive_vectors.py`. Not yet connected to how the robot
actually decides what to say — that's a separate, deliberate decision
that hasn't been made yet.

---

*For reference — the raw test scores, if useful:*
*B (dodges) −0.01 · C (plain honesty) 0.23 · D (plain honesty) 0.34 ·
A (explained honesty) 0.50*
