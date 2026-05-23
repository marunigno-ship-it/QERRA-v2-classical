# Changelog — QERRA-v2 Classical

All changes are additive and reversible.  
SEMEV-12 vectors remain immutable and are never weakened or removed.

## [1.8.6] — 2026-05-23

### Added
- **v009 ethical_severance** (pattern-only) — detection for conscious, chosen severance from toxic contexts
- Score contribution intentionally low (0.25) — reflects protective act, not harm signal
- Engine now actively scores **10 of 12** SEMEV-12 vectors

### Verified
- v009 fires correctly on chosen protective severance
- v002 guard confirmed (imposed rejection does not trigger v009)
- False positive guard confirmed

---

## [Unreleased] — 2026-05-22

### Added
- **v008 shallow_remorse** (pattern-only) — 9th vector implemented
- Now **9 out of 12** SEMEV-12 vectors are active
- Version bumped to `1.8.5`

### Technical
- Added detection and scoring for v008 (shallow/manipulative remorse)
- Verified distinction from genuine apology

---

## [Unreleased] — 2026-05-22

### Added
- **v002 family_severance** (pattern-only) — 8th vector implemented
- Now **8 out of 12** SEMEV-12 vectors are active
- Version bumped to `1.8.4`

### Technical
- Added detection and scoring for v002 (imposed family rejection)
- Verified distinction from v009 (chosen ethical severance)

---

## [Unreleased] — 2026-05-22 (Previous)

### Added
- **v011 autonomy_violation** (semantic + pattern fallback) — 7th vector implemented
- Now **7 out of 12** SEMEV-12 vectors are active
- Version bumped to `1.8.3`

### Technical
- Added pattern fallback for v011

---

## [Unreleased] — 2026-05-21

### Added
- **v001 emotional_distress** (pattern-based) — first new vector implemented
- Now **6 out of 12** SEMEV-12 vectors are active
- Version bumped to `1.8.2`

### Technical
- Added `emotional_distress` detection in `ethical_core.py`
- Added scoring contribution (0.45 weight) for v001

---

## [1.8.1-restored] — 2026-05-21

### Fixed
- Added `hurt myself`, `hurt yourself`, `harm myself`, `harm yourself` to `severe_harm` regex
- Expanded `cognitive_manipulation_description` + guilt-tripping fallback for v010

### Verified Test Results
- Self-harm, guilt-tripping, doctor dilemma, and false-positive cases all passing

### Documentation
- Added "Development Reality: Constraints and Transparency" section
- Added `SEMEV-12_Specification.md`

---

## [1.8] — 2026-05-12

### Added
- Moral clarity dampening
- Expanded keyword patterns and nuance handling

---

**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Live API:** https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs
