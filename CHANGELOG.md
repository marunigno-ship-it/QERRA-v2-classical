# Changelog — QERRA-v2 Classical

All changes are additive. SEMEV-12 vectors are immutable and are never
weakened, renamed, or removed across any version.

---

## [2.0.0-alpha] - 2026-06-29
- Official Zenodo publication of QERRA-v2 Classical.
- Integrated QERRA-HSR v0.1 physical safety companion layer (3 vectors: Distress, Isolation, Hazards).
- Upgraded remaining 5 vectors to use SentenceTransformer semantic similarity (all 12 vectors now semantic).

## [2.0-alpha — Benchmark] — June 2026

### Documentation
- **SEMEV-12 Benchmark Run 01** completed — 80 structured test cases
  across all 12 vectors, verified against live API (v1.9.0)
  - Test types: calibration, true_positive, true_negative, boundary,
    false_positive, false_negative, multi_vector, personal_scenario,
    corporate, robotics_healthcare, robotics_elder_care, societal
  - Results: 44 PASS · 33 FINDING · 1 NOTE · 2 PASS+FINDING
  - Key findings documented:
    - v004 false positive on "toxic"/"unsupportive" keywords (pressure_mention regex)
    - Compound semantic dilution in complex multi-concept sentences
    - v010 live API threshold discrepancy (TECH-FIND-01, ~0.35 vs documented 0.38)
    - v009 confirmed as system's only diluting vector
    - Corporate and professional language vocabulary gap identified
    - Intentional scope boundary confirmed (romantic/emotional conflict = out of scope)
  - Post-benchmark anchor expansion plan documented
  - See [`SEMEV-12_Benchmark_Run_01.md`](./SEMEV-12_Benchmark_Run_01.md)
- README.md updated — benchmark reference and repository structure entry added
- SEMEV-12_Whitepaper.md — Section 2 and Section 5 terminology corrections
- README.md — vector detection table corrected to "semantic" for all 12 vectors

---

## [2.0-alpha] — June 2026

### Added
- **QERRA-HSR v0.1** — Physical Safety Response Layer (companion to SEMEV-12)
  - Three deterministic vectors: `immediate_physical_distress`,
    `human_isolation`, `environmental_hazard_proximity`
  - Pure Python, zero ML, zero extra dependencies
  - Overhead < 1ms per evaluation — Hugging Face free tier compatible
  - Output states: `CLEAR` / `MONITOR` / `CRITICAL`
  - `robot_task_interruptible` flag respected — affects HOW, never WHETHER
  - Combined condition: moderate distress + isolation → CRITICAL
  - 12 regression tests — all passing (0.006s)
  - Lives in `hsr/` subdirectory — completely isolated from SEMEV-12 core
- **HSR-ADR-001** — Architecture Decision Record for QERRA-HSR three-vector
  design decision
- **ADR-001-SEMEV-12-Core.md** — Architecture Decision Record for SEMEV-12
  foundational design

### Architecture
- QERRA-HSR runs before SEMEV-12 on every evaluation cycle
- CRITICAL from QERRA-HSR suspends SEMEV-12 deliberation
- SEMEV-12 BLOCK is never overridden by QERRA-HSR CRITICAL
- Both protections apply simultaneously and work in the same direction

### Note
- QERRA-HSR is fully implemented and tested locally
- API integration (`app.py` unified endpoint) is planned as next step

---

## [1.9.0] — June 2026

### Upgraded
- **v001 `coherence_protection`** — upgraded from pattern to full semantic
  detection via `all-MiniLM-L6-v2`
- **v002 `family_severance`** — upgraded from pattern to full semantic
  detection
- **v006 `family_origin_chain`** — upgraded from pattern to full semantic
  detection
- **v008 `shallow_remorse`** — upgraded from pattern to full semantic
  detection
- **v009 `ethical_severance`** — upgraded from pattern to full semantic
  detection

### Result
- All 12 SEMEV-12 vectors now use semantic similarity detection
- Single text encoding optimization active for all 12 vectors
- All pre-encoded embeddings loaded once at startup
- 8 regression tests passing

### Technical
- `cognitive_manipulation` semantic description refined for improved
  precision on guilt-tripping and psychological pressure patterns
- Pattern fallbacks retained as OR conditions for high-confidence
  unambiguous phrases on v004, v005, v010, v011, v012

---

## [1.8.8] — May/June 2026

### Optimized
- Pre-encoding of static semantic descriptions moved to startup
- Runtime latency reduced — embeddings computed once, reused per call
- Affects v003, v004, v005, v007, v010, v011, v012

---

## [1.8.7] — May 2026

### Added
- **v006 `family_origin_chain`** (pattern) — detection of generational
  trauma and inherited family patterns
- Engine actively scoring 11 of 12 SEMEV-12 vectors

### Technical
- Full cleanup: consistent vector ordering and indentation
- v012 `institutional_trust` prepared for activation

---

## [1.8.6] — May 2026

### Added
- **v009 `ethical_severance`** (pattern) — conscious, chosen severance
  from toxic contexts
- Score contribution intentionally low (0.25) — reflects protective act,
  not ethical risk

---

## [1.8.5] — May 2026

### Added
- **v008 `shallow_remorse`** (pattern) — detection of dismissive or
  manipulative apologies
- Engine reached 9 of 12 vectors

---

## [1.8.4] — May 2026

### Added
- **v002 `family_severance`** (pattern)

---

## [1.8.3] — May 2026

### Added
- **v011 `autonomy_violation`** (semantic + pattern fallback)

---

## [1.8.2] — May 2026

### Added
- **v001 `coherence_protection`** (pattern-based)

---

## [1.8.1-restored] — May 2026

### Fixed
- v005 `harm_intent` — added explicit self-harm phrases to severe tier
- v010 `cognitive_manipulation` — expanded with guilt-tripping fallback

### Documentation
- Added Development Reality section to README
- Added SEMEV-12 specification documents

---

*Repository:* https://github.com/marunigno-ship-it/QERRA-v2-classical
*Live API:* https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs
