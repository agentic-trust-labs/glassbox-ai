# Runs

Outputs from SWE-bench evaluation runs. Each file represents one batch of agent predictions evaluated against the SWE-bench Verified dataset.

```
runs/
  predictions_*.json    Agent patch predictions (input to swebench harness)
  glassbox-coder-*.json Named run snapshots
  logs/                 Per-instance evaluation logs (patch.diff, test_output.txt, report.json)
  reports/              SWE-bench CLI summary reports
```

These are kept here intentionally — they show what the agent produced, what failed, and what corrections were captured.
