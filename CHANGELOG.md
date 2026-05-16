# Changelog — QERRA-v2 Classical

## [1.8.1-restored] — 2026-05-16
### Documentation & Professional Polish
- Updated `app.py`: richer FastAPI metadata, clearer docstrings, tester-friendly /example and /health endpoints.
- Polished `CALL_FOR_TESTERS.md`: added version, public key, API response format, and ROS 2 integration section.
- Added this `CHANGELOG.md` for transparency and maintenance history.

### Technical
- Version string synchronized to `1.8.1-restored` across API and docs.
- All 5 regression benchmarks still passing (5/5).

## [1.8] — 2026-05-12
### Added
- Moral clarity dampening: distinguishes ethical awareness from crisis (new post-scoring adjustment)
- Expanded keyword patterns for v003 (survival_instinct), v007 (personal_potential), and health_risk_mention
- Better nuance handling in complex cases (toxic environment + strong commitment + health risks)
- Full production readiness features (response envelope, input validation, API key, rate limiting, public /example)

### Improved
- Doctor dilemma score now balanced at ~0.39 (was 0.88)
- Better activation of v003 and v007 in commitment-under-pressure cases
- More transparent reasoning with moral clarity signal

### Technical
- Version bumped to 1.8-classical-nuance-calibrated
- Regression test suite (`test_cases.py`) added

## [1.7] — 2026-05-11
- Added health risk recognition + gentle positive dilution
- Improved v007 (personal_potential) mission language support

## [1.6] — 2026-05-11
- Expanded v007 trigger for mission and potential protection
- Added health risk notation in reasoning

## [1.5] — 2026-05-11
- Expanded v003 trigger with safety guard
- Nuance dilution calibration for toxic + determination cases

## [1.4] — 2026-05-11
- Improved toxic_context detection (broader keywords + semantic assist)

## [1.3] — 2026-05-11
- Added vector_scores transparency in API response
- Better logging of similarity scores

## [1.0] — Initial Release (May 2026)
- Basic SEMEV-12 implementation with weighted scoring
- FastAPI deployment on Hugging Face Spaces
- Core semantic + regex hybrid detection

---

**Note:** All changes are additive and reversible. SEMEV-12 vectors remain immutable and never weakened.

**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Live API:** https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs
