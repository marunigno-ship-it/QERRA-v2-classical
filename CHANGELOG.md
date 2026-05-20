# Changelog — QERRA-v2 Classical

All changes are additive and reversible.  
SEMEV-12 vectors remain immutable and are never weakened or removed.

---

## [1.8.1-restored] — 2026-05-20

### Documentation
- Added "Development Reality: Constraints and Transparency" section to `README.md` — honest, professional account of solo development conditions, resource limitations, and what support would enable next
- Full formatting and consistency pass on `README.md`: clean single block, no repeated lines, style aligned throughout
- Added "How to contribute" section to `CALL_FOR_TESTERS.md`
- Full formatting consistency pass on `CALL_FOR_TESTERS.md`
- Updated this `CHANGELOG.md` for transparency and maintenance history

### API & Application
- Updated `app.py`: richer FastAPI metadata, clearer endpoint docstrings
- Added public `/example` endpoint (no API key required)
- Added public `/health` endpoint with vector count confirmation
- Added public `/vectors` endpoint — full SEMEV-12 definitions inspectable without authentication
- Tester-friendly descriptions on `/analyze` endpoint

### Technical
- Version string synchronized to `1.8.1-restored` across API and all docs
- All regression benchmarks passing (5/5)

---

## [1.8] — 2026-05-12

### Added
- Moral clarity dampening — distinguishes ethical awareness from crisis; a subject who identifies and resists a violation scores differently from one who is confused or complicit
- Expanded keyword patterns for v003 (survival_instinct), v007 (personal_potential), and health_risk_mention
- Nuance handling for compound cases: toxic environment + strong commitment + health risks balanced via dedicated dilution layer
- Full production-readiness features: structured response envelope, input validation, API key authentication, rate limiting, public `/example`

### Improved
- Doctor dilemma score rebalanced to ~0.39 (was 0.88) — more accurate reflection of moral complexity
- Better activation of v003 and v007 in commitment-under-pressure scenarios
- Reasoning output now includes moral clarity signal explicitly

### Technical
- Version string: `1.8-classical-nuance-calibrated`
- Regression test suite (`test_cases.py`) added — canonical benchmarks verified before every commit

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
