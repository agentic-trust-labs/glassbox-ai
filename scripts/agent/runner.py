"""GlassBox Agent v0.3-beta - apply fix, syntax check, run tests."""

import subprocess

from .config import SOURCE_FILES
from .models import Fix


def sh(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


class Runner:
    """Apply code changes, verify syntax, run tests."""

    def apply_fix(self, fix: Fix, sources: dict[str, str]) -> tuple[bool, str]:
        """Apply code changes to disk. Returns (success, error_msg)."""
        for change in fix.changes:
            if change.file not in sources:
                return False, f"File `{change.file}` not found in source files."

            content = sources[change.file]
            if change.old not in content:
                return False, f"String not found in `{change.file}`:\n```\n{change.old}\n```"

            if change.replace_all:
                content = content.replace(change.old, change.new)
            else:
                content = content.replace(change.old, change.new, 1)

            with open(change.file, "w") as f:
                f.write(content)
            sources[change.file] = content

        # Append test
        if fix.test_code:
            with open("tests/test_glassbox.py", "a") as f:
                f.write("\n\n" + fix.test_code + "\n")
            with open("tests/test_glassbox.py") as f:
                sources["tests/test_glassbox.py"] = f.read()

        return True, ""

    def syntax_check(self) -> tuple[bool, str]:
        """Import-check all source modules. Catches SQL/Python boundary bugs."""
        for path in SOURCE_FILES:
            if path.startswith("tests/"):
                continue
            module = path.replace("/", ".").replace(".py", "").replace("src.", "")
            result = sh(f'PYTHONPATH=src python -c "import {module}"')
            if result.returncode != 0:
                err = result.stderr[-400:]
                return False, (
                    f"Import failed for `{path}`:\n```\n{err}\n```\n"
                    "Fix likely put a Python variable inside an SQL string or broke module-level code."
                )
        return True, ""

    def run_tests(self) -> tuple[bool, str, str]:
        """Run pytest. Returns (passed, output, test_count)."""
        result = sh("python -m pytest tests/test_glassbox.py -v --tb=short")
        output = result.stdout
        # Extract test count from last line
        lines = output.strip().split("\n")
        count_line = lines[-1] if lines else ""
        return result.returncode == 0, output, count_line
