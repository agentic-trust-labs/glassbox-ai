"""
GlassBox Coder — SWE-bench Inference Script

Clones each repo at base_commit, runs the coder agent, writes predictions.json.
Predictions format matches swebench 4.x harness expectations.

Usage:
    source .env
    .venv/bin/python src/glassbox/use_cases/coder/run_swebench.py \
        --dataset SWE-bench/SWE-bench_Verified \
        --split test \
        --max_instances 10 \
        --output predictions.json

Then evaluate with the harness:
    .venv/bin/python -m swebench.harness.run_evaluation \
        --dataset_name SWE-bench/SWE-bench_Verified \
        --predictions_path predictions.json \
        --max_workers 4 \
        --run_id glassbox_coder_v1
"""
import argparse, json, logging, os, shutil, subprocess, sys, tempfile, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[4] / "src"))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("glassbox.swebench")

from glassbox.core.engine import Engine
from glassbox.core.models import AgentContext
from glassbox.use_cases.coder.pipeline import build_pipeline
from glassbox.use_cases.coder.settings import load_settings
from glassbox.use_cases.coder.states import TRANSITIONS, PAUSE_STATES

MODEL_NAME = "glassbox-coder-v1"


def clone_repo(repo: str, base_commit: str, dest: str) -> bool:
    """Clone repo at base_commit into dest. Returns True on success."""
    url = f"https://github.com/{repo}.git"
    log.info("Cloning %s @ %s → %s", repo, base_commit[:8], dest)
    r = subprocess.run(["git", "clone", "--depth=50", url, dest],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log.error("Clone failed: %s", r.stderr[:200])
        return False
    r2 = subprocess.run(["git", "checkout", base_commit],
                        capture_output=True, text=True, cwd=dest, timeout=30)
    if r2.returncode != 0:
        log.warning("Shallow checkout failed, retrying full clone...")
        shutil.rmtree(dest, ignore_errors=True)
        subprocess.run(["git", "clone", url, dest], capture_output=True, timeout=300)
        subprocess.run(["git", "checkout", base_commit], cwd=dest, capture_output=True, timeout=30)
    log.info("Repo ready at %s", dest)
    return os.path.isdir(dest)


def solve_instance(instance: dict, repo_root: str) -> str:
    """Run the coder engine on one SWE-bench instance. Returns git diff patch."""
    config = load_settings(issue_body=instance.get("problem_statement", ""), repo_root=repo_root)
    config["human_response"] = "approved"  # auto-approve in benchmark mode

    ctx = AgentContext(issue_number=0, repo=instance.get("repo", ""),
                       state="received", config=config)
    engine = Engine(transitions=TRANSITIONS, pipeline=build_pipeline(), pause_states=PAUSE_STATES)

    state, _ = engine.run(ctx, state="received")
    if state == "reviewing":
        state, _ = engine.run(ctx, state="reviewing")

    return next(
        (e["result"].get("patch", "") for e in reversed(ctx.history) if "patch" in e.get("result", {})),
        "",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--max_instances", type=int, default=10)
    parser.add_argument("--output", default="predictions.json")
    parser.add_argument("--instance_ids", nargs="*")
    parser.add_argument("--repos_dir", default=None,
                        help="Reuse cloned repos from this dir (skip re-cloning)")
    args = parser.parse_args()

    from datasets import load_dataset
    print(f"Loading {args.dataset} ({args.split})")
    dataset = load_dataset(args.dataset, split=args.split)

    if args.instance_ids:
        instances = [i for i in dataset if i["instance_id"] in args.instance_ids]
    else:
        instances = list(dataset)[:args.max_instances]

    log.info("Running %d instances | model=%s", len(instances), os.environ.get("GLASSBOX_MODEL", "gpt-4o"))

    predictions = []
    tmpdir = tempfile.mkdtemp(prefix="glassbox_swe_") if not args.repos_dir else None

    try:
        for i, instance in enumerate(instances):
            iid = instance["instance_id"]
            log.info("━━━ [%d/%d] %s ━━━", i + 1, len(instances), iid)

            repo_root = os.path.join(args.repos_dir or tmpdir, iid)
            if not os.path.isdir(repo_root):
                if not clone_repo(instance["repo"], instance["base_commit"], repo_root):
                    log.error("Skipping %s — clone failed", iid)
                    predictions.append({"instance_id": iid, "model_patch": "", "model_name_or_path": MODEL_NAME})
                    continue

            try:
                patch = solve_instance(instance, repo_root)
                if patch:
                    log.info("✓ %s — patch produced (%d chars)", iid, len(patch))
                else:
                    log.warning("✗ %s — no patch produced", iid)
            except Exception:
                log.exception("✗ %s — unhandled exception", iid)
                patch = ""

            predictions.append({"instance_id": iid, "model_patch": patch, "model_name_or_path": MODEL_NAME})

    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    with open(args.output, "w") as f:
        json.dump(predictions, f, indent=2)

    solved = sum(1 for p in predictions if p["model_patch"])
    log.info("Done. Patches produced: %d/%d → %s", solved, len(predictions), args.output)


if __name__ == "__main__":
    main()
