import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from deployment_freshness import check_freshness, markers_match


class TestMarkersMatch(unittest.TestCase):
    def test_expected_fingerprint_matches(self):
        local = {"commit": "abc123", "generatedAt": "t1"}
        live = {"commit": "abc123", "generatedAt": "t2"}  # timestamp may differ
        self.assertTrue(markers_match(live, local))

    def test_stale_fingerprint_fails(self):
        local = {"commit": "abc123"}
        live = {"commit": "deadbeef"}
        self.assertFalse(markers_match(live, local))

    def test_missing_live_marker_fails(self):
        local = {"commit": "abc123"}
        self.assertFalse(markers_match(None, local))

    def test_missing_local_marker_fails(self):
        live = {"commit": "abc123"}
        self.assertFalse(markers_match(live, None))

    def test_missing_commit_field_fails(self):
        local = {"commit": "abc123"}
        live = {"generatedAt": "t2"}  # no "commit" key at all
        self.assertFalse(markers_match(live, local))


class TestCheckFreshness(unittest.TestCase):
    def test_http_200_with_wrong_fingerprint_is_not_success(self):
        """A live 200 response with a mismatched marker must NOT be
        treated as a pass -- this is the entire point of fingerprint
        checking over a bare HTTP-200 probe."""
        local = {"commit": "expected-sha"}
        calls = []

        def fake_fetch(url):
            calls.append(url)
            return {"commit": "wrong-sha", "generatedAt": "t"}  # HTTP 200-equivalent, wrong content

        matched, live = check_freshness(
            "https://example.test",
            local,
            attempts=2,
            delay=0,
            fetch=fake_fetch,
            sleep=lambda s: None,
        )
        self.assertFalse(matched)
        self.assertEqual(live["commit"], "wrong-sha")
        self.assertEqual(len(calls), 2)  # retried up to `attempts`

    def test_matches_on_first_attempt_without_retrying(self):
        local = {"commit": "sha1"}
        calls = []

        def fake_fetch(url):
            calls.append(url)
            return {"commit": "sha1"}

        matched, live = check_freshness(
            "https://example.test",
            local,
            attempts=5,
            delay=0,
            fetch=fake_fetch,
            sleep=lambda s: (_ for _ in ()).throw(AssertionError("should not sleep")),
        )
        self.assertTrue(matched)
        self.assertEqual(len(calls), 1)

    def test_eventually_matches_after_retries(self):
        local = {"commit": "sha-new"}
        responses = iter(
            [{"commit": "sha-old"}, {"commit": "sha-old"}, {"commit": "sha-new"}]
        )
        sleeps = []

        def fake_fetch(url):
            return next(responses)

        matched, live = check_freshness(
            "https://example.test",
            local,
            attempts=5,
            delay=7,
            fetch=fake_fetch,
            sleep=lambda s: sleeps.append(s),
        )
        self.assertTrue(matched)
        self.assertEqual(sleeps, [7, 7])  # slept before attempt 2 and 3, not after success

    def test_gives_up_after_max_attempts(self):
        local = {"commit": "sha-new"}

        def fake_fetch(url):
            return None  # unreachable / non-JSON every time

        matched, live = check_freshness(
            "https://example.test",
            local,
            attempts=3,
            delay=0,
            fetch=fake_fetch,
            sleep=lambda s: None,
        )
        self.assertFalse(matched)
        self.assertIsNone(live)


if __name__ == "__main__":
    unittest.main()
