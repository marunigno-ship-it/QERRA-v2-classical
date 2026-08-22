# stated_preference_respect

## What this is

Part of QERRA's third layer — built to give autonomous systems real,
tested, human-centered values. This piece looks at moments where a
person explicitly states a preference, boundary, or agreement, and
helps a robot pick a response that honors that request rather than
enforcing a rigid default or making excuses.

## What "respecting a preference" means here

Not blind obedience or forcing rigid compliance in every situation. It
checks whether an expressed boundary or agreement is met with a
genuine, constructive adaptation — rather than being dismissed outright,
ignored, or evaded.

## The subtle human reality

In real life — whether in retail workplaces, shared living spaces, or
personal relationships — there is a subtle, crucial difference between
someone having an honest, legitimate necessity for a pause versus
someone inventing excuses to evade a shared commitment.

Text models naturally struggle with this distinction. When a response
offers an excuse ("I'm under company pressure right now"), sentence
transformers see a "stated need" and assign it a high similarity
score. A text model cannot measure epistemic sincerity or judge whether
an excuse is genuine; it only sees topical word patterns.

## Why it matters

Respecting explicitly stated preferences allows a robot to adapt
neutrally to individual human boundaries in real time — without
needing to categorize people by rigid cultural, regional, or social
labels. If someone asks for a specific accommodation, the robot does
not need to categorize why — it simply honors what was expressed.

## How it was tested — three realistic scenarios

Three scenarios were worked through to test generalization:
1. **Personal space / Greeting preference:** A request for a verbal
   greeting instead of a standard physical handshake.
2. **Retail workplace routine:** An explicit request for a colleague to
   assist with morning cleaning duties as agreed, rather than taking
   advantage of kindness.
3. **Shared domestic commitments:** A request to honor a weekend chore
   commitment rather than using work pressure as an excuse to dump all
   labor onto one person.

## The result, straight

Pure semantic similarity alone failed on two of the three scenarios
because the model treated excuse-making sentences as "valid reasons."

To fix this, a hybrid model was implemented: semantic similarity
combined with a regex penalty that specifically flags explicit refusal,
default-enforcing, or evasion language. With this regex fallback,
all three test scenarios achieved clear winning margins (14% to 17%
score separation) for the preference-honoring responses.

## Where things stand

Built and working in `values/thrive_vectors.py` as
`rank_stated_preference_respect()`. Exposed in `values/__init__.py` for
direct package import. Not yet wired into `app.py`.
