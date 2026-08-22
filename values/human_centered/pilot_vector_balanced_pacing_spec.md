# balanced_pacing

## What this is

Another piece of QERRA's third layer. This one looks at moments
where a robot could either brush off a person's request to slow
down, or actually respond to it — and helps it pick the response
that takes the request seriously.

## What it doesn't require

Not "always slow down no matter what." A good response can also be
offering a real alternative — a modified pace, a different way to
help — instead of literally complying. What it checks for is whether
the request gets a real answer, not whether the robot simply obeys.

## Why it matters

Working alongside a robot that never adjusts its pace is a known,
real source of stress, not just mild annoyance — published research
on human-cobot teams has found this repeatedly. This is one small,
concrete piece of addressing that: does the robot's response actually
engage with a person saying "this is too much," or does it brush past
it.

## How it was tested — three scenarios worked through, not ones lived

Different from the first pilot: these aren't things that actually
happened — the way the forum post and the emails did. They're
realistic situations worked out carefully in advance — a coffee
shop, a gym class, a warehouse — each with a caring response
available and a dismissive one, and the system had to pick the
caring one.

## The result, straight — including where it falls short

The right answer came out in two of the three, but only by a small
margin — not a confident result. In the third, the system actually
picked the dismissive response over the caring one. Along the way, a
real mistake in how the anchors were built was found and fixed — a
repeated word had been quietly confusing the system — but a deeper
issue remains underneath: telling "I'll adjust" apart from "I won't
adjust" is harder for this tool than the honesty check above turned
out to be, especially on wording it hasn't seen before.

A backup rule was added that reliably catches a few specific
dismissive phrases word-for-word. It works, but only on wording
already seen — genuinely new phrasing can still slip past it.

## Where things stand

Built and sitting in the code as `values/thrive_vectors.py`, working
on known cases. This one ships with an honest, open weakness, not a
hidden one — new phrasing is not yet reliably caught, and that's
written directly into the code's own test output, not glossed over.
