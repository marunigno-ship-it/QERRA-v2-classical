# unbiased_perception

## What this is

Part of QERRA's third layer — built to give autonomous systems real,
tested, human-centered values. This piece looks at moments where a
system can either evaluate people and situations based on objective facts,
merit, and direct communication, or fall into pre-judgment, stereotypes,
and background bias.

## What "unbiased perception" means here

Evaluating evidence, code, capability, and expressed facts directly. It
does not mean ignoring toxic behavior or lacking intuition; it means
refusing to pre-judge an individual's capability based on labels,
family status, credentials, age, or social standing.

## The subtle human reality

Pre-judgment takes many forms in daily life and engineering:
assuming a working mother cannot handle high-pressure deadlines,
dismissing a solid codebase simply because the developer is self-taught
without a formal computer science degree, excluding older workers from new
technology training, or assuming an individual from a modest financial
background does not belong in a high-standard working group. Neutrality
requires evaluating actual contributions and communicating directly rather
than relying on sweeping generalizations.

## Why it matters

Robots and AI middleware operating in shared workspaces, homes, and
collaborative groups must evaluate human input on actual merits,
capabilities, and direct communication, ensuring technology supports fair,
equal treatment rather than reinforcing societal biases or credentialism.

## How it was tested — four realistic scenarios, not physical lab experiments

Different from physical hardware testing: these are realistic situations
evaluated as text candidate choices through local Python test scripts —
not physical experiments conducted with human subjects on hardware in a
laboratory setting.

1. **Family Status / Working Mothers:** Speaking directly with an employee
   about her capacity for a high-priority task vs. assuming she cannot
   manage deadlines because she is a working mother.
2. **Background / Credentials:** Evaluating software architecture directly
   on its engineering merits vs. dismissing code because the developer is
   self-taught without a formal CS degree.
3. **Age & Tech Adaptability:** Offering new software training to all team
   members equally vs. excluding older workers based on assumptions.
4. **Financial & Social Class:** Judging an individual's standing by vision,
   effort, and contribution vs. excluding someone based on social class.

## The result, straight

Pure semantic similarity achieved correct decision directions across all
four scenarios, but sweeping stereotyping language produced a thin margin
(1.05% separation) on the financial class scenario.

To ensure long-term stability across unseen wording, a hybrid model was
implemented: semantic similarity combined with a regex penalty (`-0.15`)
targeting sweeping generalizations and dismissive language ("usually/always
struggle", "not worth"). With this regex fallback, all four test scenarios
achieved decisive winning margins (16.1% to 21.8% score separation) for
the unbiased, fair responses.

## Where things stand

Built and working in `values/thrive_vectors.py` as
`rank_unbiased_perception()`. Exposed in `values/__init__.py` for
direct package import. Not yet wired into `app.py`.
