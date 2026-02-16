"""Tests for the abuse prevention rate limiter."""

import pytest
from unittest.mock import patch
from app.rate_limiter import RateLimiter


class TestRateLimiter:
    """Core rate limiter logic."""

    def test_exempt_org_unlimited(self):
        rl = RateLimiter(daily_limit=2, exempt_orgs={"agentic-trust-labs"})
        for i in range(100):
            allowed, used, limit = rl.consume(1001, "agentic-trust-labs")
            assert allowed is True

    def test_exempt_org_case_insensitive(self):
        rl = RateLimiter(daily_limit=2, exempt_orgs={"Agentic-Trust-Labs"})
        allowed, _, _ = rl.consume(1001, "agentic-trust-labs")
        assert allowed is True

    def test_non_exempt_hits_limit(self):
        rl = RateLimiter(daily_limit=3, exempt_orgs={"agentic-trust-labs"})
        results = []
        for i in range(5):
            allowed, used, limit = rl.consume(2001, "external-org")
            results.append(allowed)
        assert results == [True, True, True, False, False]

    def test_limit_returns_correct_counts(self):
        rl = RateLimiter(daily_limit=2, exempt_orgs=set())
        _, used1, limit1 = rl.consume(3001, "some-org")
        assert used1 == 1 and limit1 == 2
        _, used2, _ = rl.consume(3001, "some-org")
        assert used2 == 2
        allowed, used3, _ = rl.consume(3001, "some-org")
        assert allowed is False and used3 == 2

    def test_different_installations_tracked_separately(self):
        rl = RateLimiter(daily_limit=1, exempt_orgs=set())
        a1, _, _ = rl.consume(4001, "org-a")
        a2, _, _ = rl.consume(4001, "org-a")
        b1, _, _ = rl.consume(4002, "org-b")
        assert a1 is True
        assert a2 is False
        assert b1 is True  # different installation, fresh quota

    def test_resets_on_new_day(self):
        rl = RateLimiter(daily_limit=1, exempt_orgs=set())
        rl.consume(5001, "org-x")
        allowed_day1, _, _ = rl.consume(5001, "org-x")
        assert allowed_day1 is False

        # Simulate next day
        with patch.object(rl, "_today", return_value="2099-01-02"):
            allowed_day2, used, _ = rl.consume(5001, "org-x")
            assert allowed_day2 is True
            assert used == 1

    def test_check_does_not_consume(self):
        rl = RateLimiter(daily_limit=1, exempt_orgs=set())
        allowed1, _, _ = rl.check(6001, "org-y")
        assert allowed1 is True
        allowed2, _, _ = rl.check(6001, "org-y")
        assert allowed2 is True  # still true because check doesn't consume
        # Now consume
        rl.consume(6001, "org-y")
        allowed3, _, _ = rl.check(6001, "org-y")
        assert allowed3 is False


class TestRateLimiterStats:
    """Stats and formatting."""

    def test_get_stats(self):
        rl = RateLimiter(daily_limit=5, exempt_orgs={"my-org"})
        rl.consume(7001, "external")
        rl.consume(7001, "external")
        stats = rl.get_stats()
        assert stats["daily_limit"] == 5
        assert "my-org" in stats["exempt_orgs"]
        assert 7001 in stats["active_today"]
        assert stats["active_today"][7001]["used"] == 2

    def test_format_limit_message(self):
        rl = RateLimiter(daily_limit=20)
        msg = rl.format_limit_message("acme-corp", 20, 20)
        assert "Rate Limit Reached" in msg
        assert "acme-corp" in msg
        assert "20/20" in msg
        assert "midnight UTC" in msg

    def test_exempt_org_not_tracked_in_stats(self):
        rl = RateLimiter(daily_limit=5, exempt_orgs={"agentic-trust-labs"})
        # Exempt orgs skip consume entirely (returns used=0), so no record is created
        allowed, used, _ = rl.consume(8001, "agentic-trust-labs")
        assert allowed is True
        assert used == 0  # exempt orgs always report 0 used


class TestRateLimiterEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_limit_blocks_everything(self):
        rl = RateLimiter(daily_limit=0, exempt_orgs=set())
        allowed, _, _ = rl.consume(9001, "any-org")
        assert allowed is False

    def test_zero_limit_exempt_still_passes(self):
        rl = RateLimiter(daily_limit=0, exempt_orgs={"vip-org"})
        allowed, _, _ = rl.consume(9002, "vip-org")
        assert allowed is True

    def test_empty_org_name(self):
        rl = RateLimiter(daily_limit=5, exempt_orgs=set())
        allowed, used, _ = rl.consume(9003, "")
        assert allowed is True and used == 1

    def test_multiple_exempt_orgs(self):
        rl = RateLimiter(daily_limit=1, exempt_orgs={"org-a", "org-b"})
        for _ in range(10):
            a, _, _ = rl.consume(10001, "org-a")
            b, _, _ = rl.consume(10002, "org-b")
            assert a is True
            assert b is True
