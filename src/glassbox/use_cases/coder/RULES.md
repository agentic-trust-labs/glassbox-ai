# Learned Rules

## Investigation
- Before fixing a bug, read the ENTIRE function or class containing the bug, not just the error line.
- When a method is broken, search for how other methods in the same class handle the same feature - compare the broken path to a working path.
- Before fixing a bug in a subclass or specialized writer, check how the base class or a working sibling handles the same feature.
- Explore the codebase structure BEFORE proposing any fix. Use find and grep to understand the directory layout and related files.
- When the issue mentions a specific output format (HTML, CSV, RST), create a reproduction that tests that exact format.
- If you encounter an import error in your reproduction script, check how the repo's existing tests import that module and copy their pattern.
- Read at least 20 lines of context above and below the target code before deciding on a fix. Do not edit blind.

## Editing
- Before calling str_replace, use grep to verify the target string appears exactly once in the file. If it appears multiple times, include more surrounding context to make it unique.
- Batch related edits together. Do not make many tiny patches to the same file - read enough context and make one coherent edit.
- After every edit, view the changed region to confirm the change looks correct. Do not assume the edit succeeded without verifying.
- Never create multiple versions of the same file (file_test.py, file_fix.py, file_v2.py). Always modify the original file directly.
- Follow existing code patterns, naming conventions, and import styles in the repo. If the repo uses single quotes, use single quotes. If it uses snake_case, use snake_case.
- Search for existing helper functions before writing new ones. The repo likely already has a utility that does what you need.
- If the fix involves calling a method, verify the method exists and check its signature by reading its definition first. Do not guess signatures.

## Debugging
- When command output is long, the most useful information is at the beginning (command echo) and end (stack traces, error messages). Read both carefully.
- When tests fail after your fix, read the FULL test output. The assertion message contains expected vs actual values - this tells you exactly what is wrong.
- If stuck after 3 attempts at the same approach, stop. List 5 different possible root causes, assess each, and try the most likely one you have not tried yet.
- If you find yourself re-reading or re-editing the same files without making progress, stop. Summarize what you know, what you have tried, and what remains unclear.
- Do not add broad try/except blocks to mask errors. Propagate or surface errors explicitly - silent failures are worse than crashes.
- When modifying string formatting or output code, test with edge cases: empty input, single item, and multiple items.

## Verification
- After implementing a fix, ALWAYS run the reproduction script again to confirm the bug is actually fixed. Do not skip this step.
- Run the specific test file or test class related to your change, not the entire test suite. This is faster and shows relevant failures.
- If tests pass but you are not confident, write a small additional test case that exercises the exact edge case from the issue.
- After all tests pass, do a final review: re-read the issue description, re-read your diff, and confirm every aspect of the issue is addressed.
- Check that your fix does not introduce new imports that conflict with the repo's existing dependencies.
- If the issue includes a traceback, verify that the exact same code path no longer raises that exception.
- Before calling complete, make sure there are no leftover debug prints, temporary files, or commented-out code from your debugging.
