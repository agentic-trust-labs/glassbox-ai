"""Episode store - append-only JSONL for HITL correction episodes."""
import json, logging, re, time
from collections import Counter
from pathlib import Path

log = logging.getLogger("glassbox.coder.memory")
_PATH = Path(__file__).parent / "episodes.jsonl"


def append(instance_id: str, summary: str, correction: str, path: Path = _PATH) -> dict:
    """Write one correction episode. Returns the episode dict."""
    ep = {"id": f"ep-{int(time.time()*1000)}", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "instance_id": instance_id, "summary": summary, "correction": correction}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(ep) + "\n")
    log.info("[episodes] Stored %s", ep["id"])
    return ep


def search(query: str, top_k: int = 3, path: Path = _PATH) -> list[dict]:
    """BM25-style keyword search. Returns top_k most relevant episodes."""
    if not path.exists():
        return []
    tok = lambda t: re.findall(r"[a-z0-9]+", t.lower())
    qtok = Counter(tok(query))
    scored = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ep = json.loads(line)
        except json.JSONDecodeError:
            continue
        dtok = Counter(tok(ep.get("summary", "") + " " + ep.get("correction", "")))
        score = sum(qtok[t] * dtok[t] for t in qtok if t in dtok)
        if score > 0:
            scored.append((score, ep))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:top_k]]
