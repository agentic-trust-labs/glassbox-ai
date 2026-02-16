"""Integration tests - validate rate limiter through the full dispatch chain.

Tests the actual handler dispatch with real webhook payloads, verifying:
1. Non-exempt org gets blocked after N runs
2. Exempt org never blocked
3. Rate limit comment is posted on the issue when blocked
4. Different installations tracked independently
5. Health endpoint shows usage stats
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rate_limiter import RateLimiter
from app import handlers


def _make_issue_payload(
    installation_id: int = 99999,
    org: str = "external-corp",
    repo: str = "external-corp/some-repo",
    issue_number: int = 42,
    label: str = "glassbox-agent",
) -> dict:
    """Build a realistic GitHub webhook payload for an issue labeled event."""
    return {
        "action": "labeled",
        "label": {"name": label},
        "issue": {
            "number": issue_number,
            "title": f"Bug: test issue #{issue_number}",
        },
        "repository": {
            "full_name": repo,
            "owner": {"login": org},
        },
        "organization": {"login": org},
        "installation": {"id": installation_id},
        "sender": {"login": "some-user"},
    }


def _make_comment_payload(
    installation_id: int = 99999,
    org: str = "external-corp",
    repo: str = "external-corp/some-repo",
    issue_number: int = 42,
) -> dict:
    """Build a realistic GitHub webhook payload for a comment mention."""
    return {
        "action": "created",
        "comment": {
            "id": 12345,
            "body": "Hey @glassbox-agent please fix this",
        },
        "issue": {
            "number": issue_number,
            "title": f"Bug: test issue #{issue_number}",
        },
        "repository": {
            "full_name": repo,
            "owner": {"login": org},
        },
        "organization": {"login": org},
        "installation": {"id": installation_id},
        "sender": {"login": "some-user"},
    }


class TestDispatchRateLimiting:
    """Test rate limiting through the handlers.dispatch() function."""

    def setup_method(self):
        """Wire up handlers with a mock runner and a real rate limiter."""
        self.mock_runner = AsyncMock()
        self.mock_post_comment = AsyncMock()
        self.rate_limiter = RateLimiter(daily_limit=3, exempt_orgs={"agentic-trust-labs"})
        handlers.configure(
            run_agent_fn=self.mock_runner,
            rate_limiter=self.rate_limiter,
            post_comment_fn=self.mock_post_comment,
        )

    def _dispatch(self, event, payload):
        """Run dispatch synchronously for testing."""
        bg = MagicMock()
        bg.add_task = MagicMock()
        return asyncio.get_event_loop().run_until_complete(
            handlers.dispatch(event, payload, bg)
        ), bg

    def test_external_org_allowed_then_blocked(self):
        """Non-exempt org should be allowed up to limit, then blocked."""
        results = []
        for i in range(5):
            payload = _make_issue_payload(
                installation_id=50001, org="external-corp", issue_number=100 + i
            )
            result, bg = self._dispatch("issues", payload)
            results.append(result["status"])

        assert results == ["queued", "queued", "queued", "rate_limited", "rate_limited"]

    def test_exempt_org_never_blocked(self):
        """Exempt org should never be rate limited."""
        for i in range(10):
            payload = _make_issue_payload(
                installation_id=50002, org="agentic-trust-labs", issue_number=200 + i
            )
            result, bg = self._dispatch("issues", payload)
            assert result["status"] == "queued", f"Exempt org blocked on run {i+1}"

    def test_rate_limit_comment_posted(self):
        """When rate limited, a comment should be posted on the issue."""
        # Exhaust the limit
        for i in range(3):
            payload = _make_issue_payload(
                installation_id=50003, org="acme-inc", repo="acme-inc/some-repo", issue_number=300 + i
            )
            self._dispatch("issues", payload)

        # This one should be blocked AND trigger a comment
        payload = _make_issue_payload(
            installation_id=50003, org="acme-inc", repo="acme-inc/some-repo", issue_number=303
        )
        result, bg = self._dispatch("issues", payload)

        assert result["status"] == "rate_limited"
        assert result["used"] == 3
        assert result["limit"] == 3

        # Verify comment was posted
        self.mock_post_comment.assert_called_once()
        call_args = self.mock_post_comment.call_args
        assert call_args[0][0] == 50003  # installation_id
        assert call_args[0][1] == "acme-inc/some-repo"  # repo
        assert call_args[0][2] == 303  # issue_number
        assert "Rate Limit Reached" in call_args[0][3]  # body

    def test_different_installations_independent(self):
        """Two different external orgs should have separate quotas."""
        # Org A uses all 3
        for i in range(3):
            payload = _make_issue_payload(
                installation_id=50004, org="org-a", repo="org-a/repo", issue_number=400 + i
            )
            result, _ = self._dispatch("issues", payload)
            assert result["status"] == "queued"

        # Org A is now blocked
        payload = _make_issue_payload(
            installation_id=50004, org="org-a", repo="org-a/repo", issue_number=403
        )
        result, _ = self._dispatch("issues", payload)
        assert result["status"] == "rate_limited"

        # Org B still has its own fresh quota
        payload = _make_issue_payload(
            installation_id=50005, org="org-b", repo="org-b/repo", issue_number=500
        )
        result, _ = self._dispatch("issues", payload)
        assert result["status"] == "queued"

    def test_comment_event_also_rate_limited(self):
        """Rate limiting should also apply to @mention comments, not just labels."""
        # Exhaust limit via label events
        for i in range(3):
            payload = _make_issue_payload(
                installation_id=50006, org="comment-org", repo="comment-org/repo", issue_number=600 + i
            )
            self._dispatch("issues", payload)

        # Now try a comment mention - should be blocked
        payload = _make_comment_payload(
            installation_id=50006, org="comment-org", repo="comment-org/repo", issue_number=603
        )
        result, _ = self._dispatch("issue_comment", payload)
        assert result["status"] == "rate_limited"

    def test_agent_not_invoked_when_blocked(self):
        """When rate limited, the agent runner should NOT be called."""
        runner_call_count_before = self.mock_runner.call_count

        # Exhaust limit
        for i in range(3):
            payload = _make_issue_payload(
                installation_id=50007, org="blocked-org", issue_number=700 + i
            )
            self._dispatch("issues", payload)

        runner_calls_during_allowed = self.mock_runner.call_count - runner_call_count_before
        # Agent was not called directly - it's added as background task via bg.add_task
        # But we can verify the blocked one doesn't add a task
        payload = _make_issue_payload(
            installation_id=50007, org="blocked-org", issue_number=703
        )
        result, bg = self._dispatch("issues", payload)
        assert result["status"] == "rate_limited"
        bg.add_task.assert_not_called()

    def test_wrong_label_not_rate_limited(self):
        """Events with wrong labels shouldn't consume rate limit quota."""
        for i in range(5):
            payload = _make_issue_payload(
                installation_id=50008, org="safe-org", label="bug", issue_number=800 + i
            )
            result, _ = self._dispatch("issues", payload)
            assert result["status"] == "ignored"

        # Now the real label - should still have full quota
        payload = _make_issue_payload(
            installation_id=50008, org="safe-org", label="glassbox-agent", issue_number=805
        )
        result, _ = self._dispatch("issues", payload)
        assert result["status"] == "queued"

    def test_response_includes_usage_info(self):
        """Rate limited response should include used and limit counts."""
        # Use up quota
        for i in range(3):
            payload = _make_issue_payload(
                installation_id=50009, org="info-org", issue_number=900 + i
            )
            self._dispatch("issues", payload)

        # Blocked response
        payload = _make_issue_payload(
            installation_id=50009, org="info-org", issue_number=903
        )
        result, _ = self._dispatch("issues", payload)
        assert result["status"] == "rate_limited"
        assert result["used"] == 3
        assert result["limit"] == 3
        assert result["issue"] == 903


class TestHealthEndpointStats:
    """Verify rate limiter stats are properly exposed."""

    def test_stats_reflect_usage(self):
        rl = RateLimiter(daily_limit=10, exempt_orgs={"agentic-trust-labs"})
        rl.consume(60001, "ext-org")
        rl.consume(60001, "ext-org")
        rl.consume(60002, "another-org")

        stats = rl.get_stats()
        assert stats["daily_limit"] == 10
        assert "agentic-trust-labs" in stats["exempt_orgs"]
        assert stats["active_today"][60001]["used"] == 2
        assert stats["active_today"][60001]["org"] == "ext-org"
        assert stats["active_today"][60002]["used"] == 1
