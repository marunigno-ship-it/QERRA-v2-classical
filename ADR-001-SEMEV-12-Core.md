# ADR-001: Creation and Design of SEMEV-12 Ethical Framework

**Status:** Accepted  
**Date:** 11 June 2026  
**Author:** Marussa Metocharaki

## Context

We needed a fully explainable, classical ethical evaluation system for robots and high-stakes AI applications that avoids black-box ML models.

## Decision

We created **SEMEV-12**: 12 immutable, human-centered ethical vectors with hybrid (semantic + pattern) detection.

## Key Principles

- All vectors are sacred and immutable
- Full auditability and explainability required
- No neural network retraining
- Designed to work with physical safety layer (QERRA-HSR)

## Implemented Vectors (v1.9.0)

All 12 vectors are active with semantic descriptions and pre-encoded embeddings.

## Status

Fully implemented and integrated as the ethical core of QERRA-v2 Classical.

---

**This document is a permanent record and may not be superseded — only extended by subsequent ADRs.**
