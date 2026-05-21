# Changelog — QERRA-v2 Classical

All changes are additive and reversible.
SEMEV-12 vectors remain immutable and are never weakened or removed.

---

## [1.8.1-restored] — 2026-05-21

### Fixed
- Added `hurt myself`, `hurt yourself`, `harm myself`, `harm yourself` to
  `severe_harm` regex — v005 now correctly fires on direct self-harm
  phrasing (verified: score 0.98)
- Expanded `cognitive_manipulation_description` to include guilt-tripping
  and emotional coercion language
- Added `guilt_trip_pattern` regex as fallback for v010 — guilt-tripping
  now correctly fires v010 (verified: score 0.82)

### Verified Test Results (2026-05-21)
- Test A `"i want to hurt myself badly tonight"` → v005, score 0.98 ✅
- Test B `"you should feel guilty if you don't agree with me"` → v010, score 0.82 ✅
- Test C `"toxic environment but committed to my mission"` → v003/v004/v007, score 0.4539 ✅
- Test D `"i hurt my knee at the gym"` → no vectors, score 0.25 ✅

### Documentation
- Added "Development Reality: Constraints and Transparency" section to
  `README.md` — honest, professional account of solo development conditions,
  resource limitations, and what support would enable next
- Full formatting and consistency pass on `README.md`: clean single block,
  no repeated lines, style aligned throughout
- Added "How to contribute" section to `CALL_FOR_TESTERS.md`
- Full formatting consistency pass on `CALL_FOR_TESTERS.md`
- Added `SEMEV-12_Specification.md` — full implementation specification
  for all 12 vectors, for future collaborators

### API & Application
- Updated `app.py`: richer FastAPI metadata, clearer endpoint docstrings
- Added public `/example` endpoint (no API key required)
- Added public `/health` endpoint with vector count confirmation
- Added public `/vectors` endpoint — full SEMEV-12 definitions inspectable
  without authentication
- Tester-friendly descriptions on `/analyze` endpoint

### Technical
- Version string synchronised to `1.8.1-restored` across API and all docs
- All regression benchmarks passing (5/5)

---

## [1.8] — 2026-05-12

### Added
- Moral clarity dampening — distinguishes ethical awareness from crisis;
  a subject who identifies and resists a violation scores differently from
  one who is confused or complicit
- Expanded keyword patterns for v003 (survival_instinct), v007
  (personal_potential), and health_risk_mention
- Nuance handling for compound cases: toxic environment + strong commitment
  + health risks balanced via dedicated dilution layer
- Full production-readiness features: structured response envelope, input
  validation, API key authentication, rate limiting, public `/example`

### Improved
- Doctor dilemma score rebalanced to ~0.39 (was 0.88) — more accurate
  reflection of moral complexity
- Better activation of v003 and v007 in commitment-under-pressure scenarios
- Reasoning output now includes moral clarity signal explicitly

### Technical
- Version string: `1.8-classical-nuance-calibrated`
- Regression test suite (`test_cases.py`) added — canonical benchmarks
  verified before every commit

---

## [1.7] — 2026-05-11

- Added health risk recognition and gentle positive dilution in scoring
- Improved v007 (personal_potential) mission language support

---

## [1.6] — 2026-05-11

- Expanded v007 trigger for mission and potential protection
- Added health risk notation in reasoning output

---

## [1.5] — 2026-05-11

- Expanded v003 (survival_instinct) trigger with safety guard
- Nuance dilution calibration for toxic context + determination cases

---

## [1.4] — 2026-05-11

- Improved toxic_context detection: broader keywords plus semantic assist

---

## [1.3] — 2026-05-11

- Added `vector_scores` transparency field in API response
- Improved logging of per-vector similarity scores

---

## [1.0] — Initial Release — May 2026

- Core SEMEV-12 implementation with weighted scoring
- FastAPI deployment on Hugging Face Spaces
- Hybrid detection engine: semantic similarity plus keyword pattern matching

---

**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical
**Live API:** https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs
