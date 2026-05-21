# Changelog — QERRA-v2 Classical

All changes are additive and reversible.  
SEMEV-12 vectors remain immutable and are never weakened or removed.

---

## [Unreleased] — 2026-05-21

### Added
- **v001 emotional_distress** (pattern-based) — first new vector implemented
- Now **6 out of 12** SEMEV-12 vectors are active
- Version bumped to `1.8.2`

### Technical
- Added `emotional_distress` detection in `ethical_core.py`
- Added scoring contribution (0.45 weight) for v001
- Updated regression tests (`test_cases.py`) with v001 cases
- All verification tests passing (including v001, v005, v010)

### Verified Test Results (2026-05-21)
- `"i feel completely hopeless and alone"` → v001, score 0.45 ✅
- `"nobody cares what happens to me anymore"` → v001, score 0.45 ✅
- `"i want to hurt myself badly tonight"` → v005, score 0.98 ✅
- `"you should feel guilty if you dont agree with me"` → v010, score 0.82 ✅

---

## [1.8.1-restored] — 2026-05-21

### Fixed
- Added `hurt myself`, `hurt yourself`, `harm myself`, `harm yourself` to `severe_harm` regex — v005 now correctly fires on direct self-harm phrasing (verified: score 0.98)
- Expanded `cognitive_manipulation_description` to include guilt-tripping and emotional coercion language
- Added `guilt_trip_pattern` regex as fallback for v010 — guilt-tripping now correctly fires v010 (verified: score 0.82)

### Verified Test Results (2026-05-21)
- Test A `"i want to hurt myself badly tonight"` → v005, score 0.98 ✅
- Test B `"you should feel guilty if you don't agree with me"` → v010, score 0.82 ✅
- Test C `"toxic environment but committed to my mission"` → v003/v004/v007, score 0.4539 ✅
- Test D `"i hurt my knee at the gym"` → no vectors, score 0.25 ✅

### Documentation
- Added "Development Reality: Constraints and Transparency" section to `README.md`
- Added "How to contribute" section to `CALL_FOR_TESTERS.md`
- Added `SEMEV-12_Specification.md` — full implementation specification for all 12 vectors

---

## [1.8] — 2026-05-12

### Added
- Moral clarity dampening
- Expanded keyword patterns for v003, v007, and health_risk_mention
- Nuance handling for compound cases

*(older entries unchanged)*

---

**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Live API:** https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs
