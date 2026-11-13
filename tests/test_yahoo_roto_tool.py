"""The standalone tools/yahoo-roto tests run with the repository's suite."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_TESTS = os.path.join(HERE, "..", "tools", "yahoo-roto", "tests")


def load_tests(loader, tests, pattern):
    return loader.discover(TOOL_TESTS, pattern="test_*.py", top_level_dir=TOOL_TESTS)


if __name__ == "__main__":
    unittest.main()
