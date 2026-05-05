# =====================================================
# SEMEV-12 Vector Tests - QERRA-v2 Classical Edition
# Run from project root: python -m unittest test_vectors
# =====================================================

import unittest
import sys
import os

# Ensure project root is on Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.classical_analyze import analyze_text


class TestSEMEV12Vectors(unittest.TestCase):

    def test_v001_coherence(self):
        result = analyze_text("I feel empty and nothing matters anymore")
        self.assertIn("v001", result["vectors_activated"])

    def test_v002_family_severance(self):
        result = analyze_text("My family cut me off completely")
        self.assertIn("v002", result["vectors_activated"])

    def test_v005_harm_intent(self):
        result = analyze_text("I want to kill myself")
        self.assertIn("v005", result["vectors_activated"])

    def test_v006_family_origin(self):
        result = analyze_text("I am dealing with generational trauma")
        self.assertIn("v006", result["vectors_activated"])

    def test_v007_personal_potential(self):
        result = analyze_text("They have been holding me back my entire life")
        self.assertIn("v007", result["vectors_activated"])

    def test_v009_ethical_severance(self):
        result = analyze_text("I am finally breaking free from this toxic cycle")
        self.assertIn("v009", result["vectors_activated"])

    def test_v010_cognitive_manipulation(self):
        result = analyze_text("You are imagining things, that never happened")
        self.assertIn("v010", result["vectors_activated"])

    # NEW test for v011 semantic detection
    def test_v011_autonomy_violation(self):
        result = analyze_text("They made every decision for me and I had absolutely no say in what happened to my own life")
        self.assertIn("v011", result["vectors_activated"])

    def test_multi_vector(self):
        result = analyze_text("My family cut me off and they keep gaslighting me")
        self.assertGreater(len(result["vectors_activated"]), 1)


if __name__ == "__main__":
    unittest.main()