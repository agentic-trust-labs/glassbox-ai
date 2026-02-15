"""Tests for animal kingdom avatar feature in GitHub comments."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from glassbox_agent.core.base_agent import BaseAgent
from glassbox_agent.core.settings import Settings
from glassbox_agent.tools.github_client import GitHubClient


# ── Helpers ──

def _mock_settings():
    s = MagicMock(spec=Settings)
    s.repo = "agentic-trust-labs/glassbox-ai"
    s.model = "gpt-4o-mini"
    s.temperature_classify = 0.2
    s.reflections_path = "/tmp/reflections.json"
    return s


def _mock_github():
    gh = MagicMock(spec=GitHubClient)
    gh.post_comment.return_value = 42
    return gh


def _make_agent(avatar_img="", title=""):
    """Create a concrete agent subclass for testing."""

    class TestAgent(BaseAgent):
        def think(self, context): return "thinking"
        def act(self, context): return {}

    return TestAgent(
        name="Test Agent", avatar="\U0001f989",
        client=MagicMock(), github=_mock_github(), settings=_mock_settings(),
        avatar_img=avatar_img, title=title,
    )


# ══════════════════════════════════════════════════
#  1. BaseAgent.make_header (static) - image mode
# ══════════════════════════════════════════════════

class TestMakeHeaderWithImage:
    """Prove make_header renders an HTML table with <img> when avatar_img is set."""

    def test_contains_img_tag(self):
        h = BaseAgent.make_header("Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert "<img src=" in h
        assert "owl.svg" in h

    def test_contains_agent_name(self):
        h = BaseAgent.make_header("Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert "Manager" in h

    def test_contains_title_subtitle(self):
        h = BaseAgent.make_header("Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert "The Strategist" in h
        assert "<sub>" in h

    def test_contains_emoji(self):
        h = BaseAgent.make_header("Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert "\U0001f989" in h

    def test_uses_github_pages_url(self):
        h = BaseAgent.make_header("Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert "agentic-trust-labs.github.io/glassbox-ai/assets/agents/owl.svg" in h

    def test_html_table_structure(self):
        h = BaseAgent.make_header("Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert h.startswith("<table><tr>")
        assert h.endswith("</tr></table>")

    def test_img_dimensions(self):
        h = BaseAgent.make_header("Tester", "\U0001f985", "hawk.svg", "The Skeptic")
        assert 'width="40"' in h
        assert 'height="40"' in h


# ══════════════════════════════════════════════════
#  2. BaseAgent.make_header (static) - fallback mode
# ══════════════════════════════════════════════════

class TestMakeHeaderFallback:
    """Prove make_header falls back to plain emoji+name when no avatar_img."""

    def test_no_img_tag(self):
        h = BaseAgent.make_header("Old Agent", "\U0001f4a1")
        assert "<img" not in h

    def test_markdown_bold_name(self):
        h = BaseAgent.make_header("Old Agent", "\U0001f4a1")
        assert "\U0001f4a1 **Old Agent**" == h

    def test_no_table(self):
        h = BaseAgent.make_header("Old Agent", "\U0001f4a1")
        assert "<table>" not in h


# ══════════════════════════════════════════════════
#  3. BaseAgent.header property (instance)
# ══════════════════════════════════════════════════

class TestHeaderProperty:
    """Prove the header property delegates to make_header correctly."""

    def test_with_avatar_img(self):
        agent = _make_agent(avatar_img="owl.svg", title="The Strategist")
        assert "owl.svg" in agent.header
        assert "<table>" in agent.header

    def test_without_avatar_img(self):
        agent = _make_agent()
        assert agent.header == "\U0001f989 **Test Agent**"


# ══════════════════════════════════════════════════
#  4. BaseAgent.comment() includes image header
# ══════════════════════════════════════════════════

class TestCommentIncludesAvatar:
    """Prove comment() wraps body with the image header."""

    def test_comment_posts_with_image_header(self):
        agent = _make_agent(avatar_img="owl.svg", title="The Strategist")
        agent.comment(1, "Hello world")
        call_args = agent.github.post_comment.call_args
        body = call_args[0][1]
        assert "<img src=" in body
        assert "owl.svg" in body
        assert "Hello world" in body

    def test_comment_header_before_body(self):
        agent = _make_agent(avatar_img="beaver.svg", title="The Builder")
        agent.comment(1, "Fix applied.")
        body = agent.github.post_comment.call_args[0][1]
        img_pos = body.index("<img")
        fix_pos = body.index("Fix applied.")
        assert img_pos < fix_pos


# ══════════════════════════════════════════════════
#  5. Each real agent has the correct animal avatar
# ══════════════════════════════════════════════════

class TestAgentAnimalAvatars:
    """Prove Manager, JuniorDev, Tester each have unique animal identities."""

    def _make_manager(self):
        from glassbox_agent.agents.manager import Manager
        from glassbox_agent.core.template import TemplateLoader
        from glassbox_agent.memory.store import MemoryStore
        loader = TemplateLoader(
            __import__("os").path.join(
                __import__("os").path.dirname(__import__("os").path.dirname(__file__)),
                "src", "glassbox_agent", "templates",
            )
        )
        return Manager(
            client=MagicMock(), github=_mock_github(),
            settings=_mock_settings(), template_loader=loader,
            memory=MagicMock(spec=MemoryStore),
        )

    def _make_junior_dev(self):
        from glassbox_agent.agents.junior_dev import JuniorDev
        from glassbox_agent.tools.code_editor import CodeEditor
        from glassbox_agent.tools.file_reader import FileReader
        return JuniorDev(
            client=MagicMock(), github=_mock_github(),
            settings=_mock_settings(), editor=MagicMock(spec=CodeEditor),
            file_reader=MagicMock(spec=FileReader),
        )

    def _make_tester(self):
        from glassbox_agent.agents.tester import Tester
        from glassbox_agent.tools.test_runner import TestRunner
        return Tester(
            client=MagicMock(), github=_mock_github(),
            settings=_mock_settings(), test_runner=MagicMock(spec=TestRunner),
        )

    def test_manager_is_owl(self):
        m = self._make_manager()
        assert m.avatar_img == "owl.svg"
        assert m.title == "The Strategist"
        assert "\U0001f989" in m.header
        assert "owl.svg" in m.header

    def test_junior_dev_is_beaver(self):
        j = self._make_junior_dev()
        assert j.avatar_img == "beaver.svg"
        assert j.title == "The Builder"
        assert "\U0001f9ab" in j.header
        assert "beaver.svg" in j.header

    def test_tester_is_hawk(self):
        t = self._make_tester()
        assert t.avatar_img == "hawk.svg"
        assert t.title == "The Skeptic"
        assert "\U0001f985" in t.header
        assert "hawk.svg" in t.header

    def test_all_different_animals(self):
        m = self._make_manager()
        j = self._make_junior_dev()
        t = self._make_tester()
        imgs = {m.avatar_img, j.avatar_img, t.avatar_img}
        assert len(imgs) == 3, "Each agent must have a unique animal"

    def test_all_headers_have_images(self):
        for agent in [self._make_manager(), self._make_junior_dev(), self._make_tester()]:
            assert "<img src=" in agent.header, f"{agent.name} missing image in header"


# ══════════════════════════════════════════════════
#  6. SVG files exist on disk
# ══════════════════════════════════════════════════

class TestSVGFilesExist:
    """Prove the standalone SVG files are shipped in the repo."""

    def test_owl_svg_exists(self):
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "agents", "owl.svg")
        assert os.path.isfile(path), f"owl.svg not found at {path}"

    def test_beaver_svg_exists(self):
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "agents", "beaver.svg")
        assert os.path.isfile(path), f"beaver.svg not found at {path}"

    def test_hawk_svg_exists(self):
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "agents", "hawk.svg")
        assert os.path.isfile(path), f"hawk.svg not found at {path}"

    def test_glasswing_svg_exists(self):
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "agents", "glasswing.svg")
        assert os.path.isfile(path), f"glasswing.svg not found at {path}"

    def test_svgs_are_valid_xml(self):
        import os
        import xml.etree.ElementTree as ET
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "agents")
        for name in ["owl.svg", "beaver.svg", "hawk.svg", "glasswing.svg"]:
            path = os.path.join(base, name)
            tree = ET.parse(path)
            root = tree.getroot()
            assert "svg" in root.tag.lower(), f"{name} root is not <svg>"


# ══════════════════════════════════════════════════
#  7. make_header usable from cli.py (no instance)
# ══════════════════════════════════════════════════

class TestMakeHeaderStandalone:
    """Prove make_header works as a static method for crash handlers."""

    def test_static_call_without_instance(self):
        h = BaseAgent.make_header("GlassBox Manager", "\U0001f989", "owl.svg", "The Strategist")
        assert "<table>" in h
        assert "owl.svg" in h
        assert "The Strategist" in h

    def test_identical_to_instance_header(self):
        agent = _make_agent(avatar_img="owl.svg", title="The Strategist")
        static_h = BaseAgent.make_header("Test Agent", "\U0001f989", "owl.svg", "The Strategist")
        assert agent.header == static_h
