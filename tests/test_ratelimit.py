import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from ratelimit import AccountLimiter


def ts(day=18, hour=12, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=timezone.utc).timestamp()


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class AccountLimiterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "state", "ratelimit.json")  # diretório ainda não existe
        self.clock = Clock(ts())

    def limiter(self, **kwargs):
        kwargs.setdefault("min_interval", 30)
        kwargs.setdefault("max_per_day", 3)
        return AccountLimiter(self.path, clock=self.clock, **kwargs)

    def test_fresh_account_is_allowed(self):
        self.assertEqual(self.limiter().check("acc"), 0)

    def test_min_interval_between_profiles(self):
        lim = self.limiter()
        lim.record_start("acc")
        self.clock.now += 10
        self.assertAlmostEqual(lim.check("acc"), 20)
        self.clock.now += 20
        self.assertEqual(lim.check("acc"), 0)

    def test_daily_cap_waits_until_next_utc_midnight(self):
        lim = self.limiter(min_interval=0)
        for _ in range(3):
            lim.record_start("acc")
        self.assertAlmostEqual(lim.check("acc"), 12 * 3600)  # de 12:00 até 00:00 UTC
        self.clock.now = ts(day=19, hour=0, minute=0, second=1)
        self.assertEqual(lim.check("acc"), 0)
        lim.record_start("acc")  # novo dia recomeça a contagem
        self.assertEqual(lim.check("acc"), 0)

    def test_wait_is_the_larger_of_interval_and_cap(self):
        lim = self.limiter(min_interval=30)
        self.clock.now = ts(hour=23, minute=59, second=50)
        for _ in range(3):
            lim.record_start("acc")
        self.clock.now = ts(hour=23, minute=59, second=55)
        self.assertAlmostEqual(lim.check("acc"), 25, places=3)  # intervalo (25s) > falta p/ meia-noite (5s)

    def test_accounts_are_independent(self):
        lim = self.limiter()
        lim.record_start("a")
        self.assertGreater(lim.check("a"), 0)
        self.assertEqual(lim.check("b"), 0)

    def test_state_is_persisted_across_instances(self):
        self.limiter().record_start("acc")
        self.clock.now += 5
        self.assertAlmostEqual(self.limiter().check("acc"), 25)
        with open(self.path) as f:
            self.assertIn("acc", json.load(f)["accounts"])

    def test_corrupt_state_file_is_ignored(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{não é json")
        lim = self.limiter()
        self.assertEqual(lim.check("acc"), 0)
        lim.record_start("acc")  # sobrescreve com estado válido
        self.assertGreater(self.limiter().check("acc"), 0)

    def test_zero_disables_each_limit(self):
        lim = self.limiter(min_interval=0, max_per_day=0)
        for _ in range(500):
            lim.record_start("acc")
        self.assertEqual(lim.check("acc"), 0)

    def test_from_env_defaults_and_overrides(self):
        lim = AccountLimiter.from_env({}, clock=self.clock)
        self.assertEqual((lim.min_interval, lim.max_per_day), (30, 100))
        lim = AccountLimiter.from_env({"MIN_SECONDS_BETWEEN_PROFILES": "45", "MAX_PROFILES_PER_DAY": "10",
                                       "RATE_STATE_FILE": self.path}, clock=self.clock)
        self.assertEqual((lim.min_interval, lim.max_per_day, lim.state_path), (45, 10, self.path))

    def test_from_env_rejects_invalid_values(self):
        for env in ({"MIN_SECONDS_BETWEEN_PROFILES": "abc"}, {"MAX_PROFILES_PER_DAY": "-1"},
                    {"MIN_SECONDS_BETWEEN_PROFILES": "-5"}):
            with self.assertRaises(ValueError, msg=env):
                AccountLimiter.from_env(env)


if __name__ == "__main__":
    unittest.main()
