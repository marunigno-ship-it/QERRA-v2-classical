# Changelog — QERRA-v2 Classical Edition

## v1.2-classical (May 2026)

### Added
- Full SEMEV-12 implementation with weighted scoring and dynamic reasoning
- Semantic detection using sentence-transformers for v005 (harm_intent), v010 (cognitive_manipulation), and v011 (autonomy_violation)
- /health and /vectors endpoints
- Rate limiting, file logging, CORS restriction
- Basic test suite (9 tests)
- Comprehensive documentation: LIMITATIONS.md, QERRA-v2_Vision_and_Current_State.md, SEMEV-12_Framework_Description.md
- Related Repositories section in README

### Improvements
- Positive severance fix for v009
- Version consistency and API key security fixes

### Technical Note
Three critical vectors now use semantic similarity detection. The remaining nine use keyword/phrase matching. This is a research prototype with honest limitations documented.

## v1.0-classical (Initial)
- Initial FastAPI structure with regex-based ethical scoring
