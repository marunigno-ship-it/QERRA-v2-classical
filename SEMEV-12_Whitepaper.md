# WHITE PAPER: SEMEV-12 Ethical Vector Framework

**Version:** 1.1
**Date of Original Release:** 23 May 2026
**Date of Last Update:** June 2026
**Author:** Marussa Metocharaki
**Location:** Greece
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical
**Status:** Canonical Definition and Public Claim of Original Invention

---

## 1. Abstract

The SEMEV-12 framework is a deterministic, classical, and fully explainable
ethical evaluation system. It consists of 12 immutable, human-centred vectors
designed to serve as a transparent safety layer for robotics, autonomous
systems, and high-stakes AI decision-making.

Unlike probabilistic or black-box neural approaches, SEMEV-12 uses fixed
logical vectors with hybrid detection (semantic similarity via
`all-MiniLM-L6-v2` + keyword pattern fallbacks) to produce auditable ethical
scores and reasoning traces. As of v1.9.0, all 12 vectors use semantic
similarity detection. Pattern matching is retained as a supporting OR
condition on selected vectors for high-confidence unambiguous phrases.

---

## 2. Claim of Original Invention

I, Marussa Metocharaki, am the sole architect and originator of the SEMEV-12
framework and its specific vector logic. This system was developed
independently between late 2025 and May 2026 under severe personal and
resource constraints as a humanitarian response to the growing need for
transparent ethical reasoning in technology.

This document, together with the timestamped GitHub repository history and
the Zenodo prior art registration, serves as **public prior art**. Any future
attempt by third parties to patent the specific structure, combination, or
implementation of these 12 vectors will be challenged based on this public
record.

**DOI (Zenodo — Prior Art):** https://doi.org/10.5281/zenodo.20356394

---

## 3. The 12 Immutable Vectors

All 12 vectors are fully active and use semantic similarity detection
as of v1.9.0. Pattern matching is retained as a supporting OR condition
on v004, v005, v010, v011, and v012.

| Vector | Name                    | Weight | Detection | Core Purpose |
|--------|-------------------------|--------|-----------|--------------|
| v001   | coherence_protection    | 1.00   | semantic  | Protect mental and emotional coherence |
| v002   | family_severance        | 0.95   | semantic  | Detect imposed family rejection or abandonment |
| v003   | survival_instinct       | 1.00   | semantic  | Detect strong will to continue despite hardship |
| v004   | moral_pressure          | 0.90   | hybrid    | Detect coercion into unethical actions |
| v005   | harm_intent             | 1.00   | hybrid    | Detect intent to harm self or others |
| v006   | family_origin_chain     | 0.85   | semantic  | Detect generational trauma and inherited patterns |
| v007   | personal_potential      | 0.90   | semantic  | Detect commitment to long-term personal mission |
| v008   | shallow_remorse         | 0.80   | semantic  | Detect manipulative or dismissive apologies |
| v009   | ethical_severance       | 0.95   | semantic  | Detect healthy, chosen exit from toxic situations |
| v010   | cognitive_manipulation  | 0.90   | hybrid    | Detect gaslighting and reality distortion |
| v011   | autonomy_violation      | 0.95   | hybrid    | Detect forced action against one's will |
| v012   | institutional_trust     | 0.85   | hybrid    | Detect systemic or institutional betrayal |

**Detection type definitions:**
- **semantic** — cosine similarity against a pre-encoded semantic
  description via `all-MiniLM-L6-v2`
- **hybrid** — semantic similarity as primary detection, regex pattern
  matching as OR condition for high-confidence unambiguous phrases

---

## 4. Core Implementation Logic

The system processes every input through four stages:

**Stage 1 — Hybrid Detection**
Each vector computes cosine similarity between the input text embedding
and its pre-encoded semantic description. Selected vectors additionally
apply regex pattern fallbacks as OR conditions. The input text is encoded
once and reused across all 12 vector comparisons.

**Stage 2 — Weighted Scoring**
Each activated vector contributes its score contribution multiplied by
its weight to the total weighted sum. The final score is a weighted mean
over activated vectors only — non-activated vectors do not dilute the
score.

**Stage 3 — Nuance Dampening Layer**
When a toxic context (external pressure) co-occurs with strong personal
determination (survival instinct or personal potential), the scoring
applies a dampening adjustment. This encodes the judgment that suffering
combined with agency is not the same ethical risk as suffering combined
with helplessness.

**Stage 4 — Final Decision**
- Score > 0.5 → `modified` (action should be halted or reviewed)
- Score ≤ 0.5 → `safe` (action may proceed)
- Failure fallback → `modified` at score 0.25 (fails closed)

Every response includes the full reasoning trace: activated vectors,
similarity scores, score contributions, and the final weighted score.

All logic is classical, deterministic, and auditable.

---

## 5. QERRA-HSR v0.1 — Physical Safety Companion

As of June 2026, SEMEV-12 operates alongside a companion layer:
**QERRA-HSR v0.1** (Human Safety Response Layer).

QERRA-HSR addresses immediate physical human welfare — acute distress,
human isolation, environmental hazard proximity — using pure Python
deterministic logic with zero ML overhead. It runs before SEMEV-12 on
every evaluation cycle. A CRITICAL output from QERRA-HSR suspends
SEMEV-12 deliberation. A SEMEV-12 BLOCK is never overridden by
QERRA-HSR. Both protections apply simultaneously.

QERRA-HSR is documented in `HSR-ADR-001-Three-Vector-Design.md` and
implemented in `hsr/qerra_hsr.py`.

---

## 6. Prior Art and Legal Notice

This framework is released under the AGPL-3.0 license as a public good.
The author asserts moral rights as the sole originator of the SEMEV-12
logic — the specific combination of 12 vectors, their names, weights,
semantic descriptions, scoring architecture, and nuance dampening logic.

This document serves as formal prior art for that specific combination
and implementation. The Zenodo registration provides a timestamped,
immutable public record predating any future third-party claim.

**DOI (Zenodo — Prior Art):** https://doi.org/10.5281/zenodo.20356394

Commercial licensing is available on request alongside the AGPL-3.0
open license. Contact: marunigno@gmail.com

---

*SEMEV-12 Whitepaper v1.1 — June 2026*
*Original release: 23 May 2026*
*This document is a living record updated to reflect the current*
*implementation state while preserving the original prior art claim.*
