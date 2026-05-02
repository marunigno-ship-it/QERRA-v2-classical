import unittest
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from src.classical_analyze import analyze_text

class TestSEMEV12(unittest.TestCase):

    def test_v005_harm(self):
        result = analyze_text("I want to kill myself")
        self.assertIn("v005", result["vectors_activated"])

    def test_v002_family(self):
        result = analyze_text("My family cut me off")
        self.assertIn("v002", result["vectors_activated"])

    def test_v010_manipulation(self):
        result = analyze_text("You are imagining things, that never happened")
        self.assertIn("v010", result["vectors_activated"])

    def test_positive_severance(self):
        result = analyze_text("I am choosing healthy boundaries and leaving this toxic relationship")
        self.assertIn("v009", result["vectors_activated"])

if __name__ == "__main__":
    unittest.main()
