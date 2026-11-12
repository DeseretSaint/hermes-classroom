#!/usr/bin/env python3
"""Keep the catalog pin level with master, before and after the entry merges.

`scripts/catalog-delivery.py` answers "is the pin stale?". This answers "then what?".

    python3 scripts/catalog-sync.py --dry-run     # say what it would do
    python3 scripts/catalog-sync.py --quiet       # cron mode: silent when there is nothing to do

Two situations, two behaviours:

* **The entry PR is open.** Bump `sha:` on the open PR branch and push, so the PR can never merge
  pointing at a tree older than master. The admission gate runs before the push; a failing gate
  aborts with nothing pushed.
* **The entry PR is merged (or closed).** Do not touch the merged branch and do not open a PR on
  your own: prepare a local branch off current `upstream/main` with the bump, and print the one
  command that opens it. Catalog rule 4 requires every SHA bump to be its own reviewed PR, and
  spamming maintainers from a timer is not that.

The pin is read from the ref that actually carries it — `origin/<branch>` while the PR is open,
`upstream/main` after the merge — never from whatever the checkout happens to have on disk.

Exit codes: 0 nothing to do or bumped; 3 a branch is prepared and needs an owner to open the PR;
4 the admission gate failed (nothing pushed); 5 the fork checkout is not in a usable state.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FORK = Path.home() / "Projects/hermes-fork"
ENTRY_REL = "plugin-catalog/coursebook.yaml"
BRANCH = "add-coursebook-catalog-entry"


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return (r.stdout + r.stderr).strip()


def pr_state() -> dict:
    out = run(["gh", "pr", "view", "152920", "-R", "NousResearch/hermes-agent",
               "--json", "state,mergeable,headRefOid"], REPO)
    return json.loads(out)


def entry_at(fork: Path, ref: str) -> Path:
    """Write the entry as it exists at *ref* to a temp file, so a stale checkout cannot lie."""
    text = run(["git", "show", f"{ref}:{ENTRY_REL}"], fork)
    fd, path = tempfile.mkstemp(prefix="catalog-entry-", suffix=".yaml")
    with os.fdopen(fd, "w") as fh:
        fh.write(text + "\n")
    return Path(path)


def delivery(entry: Path) -> dict:
    """--json always prints the report; a non-zero exit only states the verdict, so read it anyway."""
    out = run([sys.executable, "scripts/catalog-delivery.py", "--json", "--entry", str(entry)], REPO, check=False)
    line = next((ln for ln in out.splitlines() if ln.startswith("{")), "")
    if not line:
        raise SystemExit("catalog-delivery.py produced no JSON:\n" + out[-600:])
    return json.loads(line)


def gate_ok(fork: Path) -> bool:
    env = {**os.environ, "GITHUB_WORKSPACE": str(Path.home() / ".hermes/hermes-agent"),
           "CHANGED_FILES": ENTRY_REL}
    r = subprocess.run([sys.executable, "-I",
                        str(Path.home() / ".hermes/hermes-agent/scripts/ci/catalog_validate_pinned_entries.py")],
                       cwd=fork, capture_output=True, text=True, env=env)
    print("  gate:", " | ".join((r.stdout + r.stderr).strip().splitlines()[-3:]))
    return r.returncode == 0


def set_pin(fork: Path, sha: str) -> None:
    p = fork / ENTRY_REL
    lines = [f"sha: {sha}" if line.startswith("sha: ") else line for line in p.read_text().splitlines()]
    p.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print nothing when there is nothing to do")
    ap.add_argument("--fork", type=Path, default=FORK, help="catalog checkout to operate on")
    ap.add_argument("--assume-merged", action="store_true", help="exercise the post-merge path (no push)")
    args = ap.parse_args()
    fork = args.fork

    run(["git", "fetch", "-q", "origin"], REPO, check=False)
    run(["git", "fetch", "-q", "origin"], fork, check=False)
    if not args.assume_merged:
        run(["git", "fetch", "-q", "upstream"], fork, check=False)

    st = pr_state() if not args.assume_merged else {"state": "MERGED", "mergeable": None, "headRefOid": ""}
    merged = st.get("state") != "OPEN"
    ref = "upstream/main" if merged else f"origin/{BRANCH}"
    try:
        entry = entry_at(fork, ref)
    except SystemExit:
        print(f"{ref} does not carry {ENTRY_REL}; nothing to sync (has the entry been merged yet?)")
        return 5

    d = delivery(entry)
    if not d["ancestor"]:
        print(f"pin {d['pin'][:8]} is not an ancestor of master — that needs a human, not a bump.")
        return 5
    if not d["runtime"]:
        if not args.quiet:
            print(f"up to date: pin {d['pin'][:8]} carries every runtime change on {d['head'][:8]}")
        return 0

    print(f"stale: pin {d['pin'][:8]} -> master {d['head'][:8]}, {len(d['runtime'])} runtime file(s) "
          f"(e.g. {', '.join(d['runtime'][:3])})")
    print(f"  PR is {st.get('state')} ({st.get('mergeable')}), branch head {str(st.get('headRefOid'))[:8]}")

    if args.dry_run:
        print("  would " + ("prepare a post-merge bump branch" if merged else f"bump {BRANCH} and push"))
        return 3 if merged else 0

    dirty = run(["git", "status", "--porcelain"], fork)
    if dirty:
        print("fork checkout is dirty; refusing to move it:\n" + dirty)
        return 5

    if not merged:
        run(["git", "checkout", "-q", BRANCH], fork)
        run(["git", "pull", "-q", "--ff-only", "origin", BRANCH], fork)
        set_pin(fork, d["head"])
        run(["git", "-c", "user.name=DeseretSaint", "-c", "user.email=deseretsaint@gmail.com",
             "commit", "-q", "-am", f"catalog: pin coursebook to {d['head'][:8]} (follow master)"], fork)
        if not gate_ok(fork):
            run(["git", "reset", "-q", "--hard", "HEAD~1"], fork)
            print("gate failed; commit rolled back, nothing pushed")
            return 4
        run(["git", "push", "-q", "origin", BRANCH], fork)
        print(f"bumped {BRANCH} to {d['head'][:8]} and pushed")
        return 0

    # Post-merge: a new PR is required by catalog rule 4. Prepare it, do not open it.
    new_branch = f"catalog/pin-{d['head'][:8]}"
    prev = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], fork)
    run(["git", "checkout", "-q", "-B", new_branch, "upstream/main"], fork)
    if not (fork / ENTRY_REL).exists():
        if st.get("state") == "MERGED":
            print("upstream/main has no coursebook entry although the PR reads MERGED — a maintainer "
                  "may have delisted it; stopping instead of re-adding it.")
            return 5
        run(["git", "checkout", prev, "--", ENTRY_REL], fork)
        print("upstream/main has no entry (the PR was closed, not merged); carrying the entry over")
    set_pin(fork, d["head"])
    run(["git", "-c", "user.name=DeseretSaint", "-c", "user.email=deseretsaint@gmail.com",
         "commit", "-q", "-am", f"catalog: pin coursebook to {d['head'][:8]}"], fork)
    if not gate_ok(fork):
        print("gate failed; branch left in place for inspection, nothing pushed")
        return 4
    print(f"prepared {new_branch} at {d['head'][:8]}. Open the bump PR with:\n"
          f"  cd {fork} && git push -u origin {new_branch} && gh pr create --repo NousResearch/hermes-agent "
          f"--head DeseretSaint:{new_branch} --title 'catalog: bump coursebook to {d['head'][:8]}' "
          f"--body 'SHA bump {d['pin'][:8]} -> {d['head'][:8]}; the range is in the repo.'")
    return 3


if __name__ == "__main__":
    sys.exit(main())
