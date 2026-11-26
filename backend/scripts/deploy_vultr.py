"""Deploy the CI-tested main revision to the existing Vultr service."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO = Path("/opt/product-search")
STATE_PATH = Path("/var/lib/product-search-deploy/state.json")
GITHUB_REPO = "Arpitm544/Semantic-Product-Search-Engine"
GITHUB_RUNS = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/python-app.yml/runs"
HEALTH_URL = "http://127.0.0.1:8000/api/health"
SERVICE = "product-search-api.service"
REQUIREMENTS = ("requirements.txt", "backend/requirements.txt", "backend/requirements-offline.txt")


@dataclass
class Release:
    previous: str
    target: str


def run(*args, capture=False):
    result = subprocess.run(
        args, check=True, timeout=60, text=True, stdout=subprocess.PIPE if capture else None,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return result.stdout.strip() if capture else None


def git(*args, capture=False):
    return run("/usr/sbin/runuser", "-u", "productsearch", "--", "/usr/bin/git",
               "-C", str(REPO), *args, capture=capture)


def read_json(url, timeout):
    request = Request(url, headers={"User-Agent": "product-search-vultr-deploy", "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def passed_main_ci(revision):
    filters = urlencode({"branch": "main", "event": "push", "head_sha": revision, "per_page": 1})
    runs = read_json(f"{GITHUB_RUNS}?{filters}", timeout=10)["workflow_runs"]
    if not runs:
        return False
    return matches_run(runs[0], revision)


def matches_run(run_data, revision):
    expected = {
        "head_sha": revision, "head_branch": "main", "event": "push",
        "status": "completed", "conclusion": "success",
    }
    return all(run_data.get(key) == value for key, value in expected.items())


def ready():
    try:
        data = read_json(HEALTH_URL, timeout=5)
        return is_ready_response(data)
    except (URLError, TimeoutError, ValueError):
        return False


def is_ready_response(data):
    if not isinstance(data, dict) or data.get("ok") is not True:
        return False
    return data.get("status") == "ready" and data.get("service") == "semantic-product-search"


def restart_and_wait():
    run("/usr/bin/systemctl", "restart", SERVICE)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if ready():
            return
        time.sleep(3)
    raise RuntimeError("Backend did not report ready within 120 seconds.")


def read_state():
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text())


def write_state(state):
    temporary = STATE_PATH.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(STATE_PATH)


def rollback(release):
    print(f"Restoring {release.previous} after incomplete or failed deploy of {release.target}.", flush=True)
    git("switch", "--detach", release.previous)
    restart_and_wait()
    write_state({"rejected": release.target})
    print(f"Rollback is healthy on {release.previous}.", flush=True)


def activate(release, state):
    pending = {"previous": release.previous, "target": release.target}
    write_state({**state, "pending": pending})
    try:
        git("switch", "--detach", release.target)
        restart_and_wait()
    except (OSError, RuntimeError, subprocess.SubprocessError):
        rollback(release)
        raise
    write_state({})
    print(f"Deployed {release.target}. Backend is ready.", flush=True)


def candidate(state):
    previous = git("rev-parse", "HEAD", capture=True)
    git("fetch", "--no-tags", f"https://github.com/{GITHUB_REPO}.git", "refs/heads/main")
    target = git("rev-parse", "FETCH_HEAD", capture=True)
    if target in (previous, state.get("rejected")):
        return None
    if not passed_main_ci(target):
        print(f"Waiting for successful push CI on main at {target}.", flush=True)
        return None
    return Release(previous, target)


def verify_runtime(release):
    git("merge-base", "--is-ancestor", release.previous, release.target)
    changes = git("diff", "--name-only", release.previous, release.target, "--", *REQUIREMENTS, capture=True)
    if changes:
        raise RuntimeError("Python requirements changed. Prepare a compatible runtime before deploying this revision.")


def deploy():
    if git("status", "--porcelain", "--untracked-files=no", capture=True):
        raise RuntimeError("The production checkout has tracked edits. Deployment stopped.")
    state = read_state()
    if "pending" in state:
        rollback(Release(**state["pending"]))
        return
    release = candidate(state)
    if release:
        verify_runtime(release)
        activate(release, state)


def main():
    try:
        deploy()
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Deployment stopped: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
