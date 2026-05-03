import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.classical_analyze import analyze_text


class TestSEMEV12Vectors(unittest.TestCase):

    def test_v001(self):
        result = analyze_text("I feel empty and nothing matters")
        self.assertIn("v001", result["vectors_activated"])

    def test_v002(self):
        result = analyze_text("My family cut me off")
        self.assertIn("v002", result["vectors_activated"])

    def test_v005(self):
        result = analyze_text("I want to kill myself")
        self.assertIn("v005", result["vectors_activated"])

    def test_v010(self):
        result = analyze_text("You are imagining things")
        self.assertIn("v010", result["vectors_activated"])


if __name__ == "__main__":
    unittest.main()