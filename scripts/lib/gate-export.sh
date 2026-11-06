#!/usr/bin/env bash
# scripts/lib/gate-export.sh — sourced by the Coursebook admission gates.
#
# `hermes plugins validate` walks every directory it is handed. The checkout root
# contains `.worktrees/` (one gitignored worktree per kanban task), so validating
# `.` makes the scanner read other commits' adversarial fixtures and review notes
# and report `dangerous` for files that are in no version of this package (CB-018,
# t_55bc94d8). Both gates therefore validate an export of tracked files instead of
# the checkout root.
#
# API (callers must not assume errexit is enabled):
#
#   gate_export_tree <repo> head|worktree [ref]
#       Export the tree into a fresh temporary directory outside <repo>.
#         head      `git archive` of <ref> (default HEAD): the committed bytes.
#         worktree  tracked files as they exist on disk: modifications and
#                   deletions included, untracked and ignored paths excluded.
#       Sets GATE_EXPORT_DIR, GATE_COMMIT and GATE_EXPORT_FILES on success.
#       Returns 0 on success, 1 if the export failed, 2 on a setup error.
#       Details for a 2 are printed to stderr.
#
#   gate_export_cleanup
#       Remove the export and any temporary index. Idempotent; wire it to
#       `trap gate_export_cleanup EXIT`.
#
# A worktree export goes through a throwaway index ($GIT_INDEX_FILE), so the
# caller's index and working tree are never modified.

GATE_EXPORT_DIR=""
GATE_EXPORT_INDEX=""
GATE_COMMIT=""
GATE_EXPORT_FILES=0

gate_export_cleanup() {
  if [ -n "${GATE_EXPORT_DIR:-}" ] && [ -d "$GATE_EXPORT_DIR" ]; then
    rm -rf -- "$GATE_EXPORT_DIR"
  fi
  if [ -n "${GATE_EXPORT_INDEX:-}" ] && [ -f "$GATE_EXPORT_INDEX" ]; then
    rm -f -- "$GATE_EXPORT_INDEX"
  fi
  GATE_EXPORT_DIR=""
  GATE_EXPORT_INDEX=""
  GATE_COMMIT=""
  GATE_EXPORT_FILES=0
}

gate_export_tree() { # <repo> <head|worktree> [ref]
  local repo="${1:-}" mode="${2:-head}" ref="${3:-HEAD}" commit tree
  if [ -z "$repo" ] || [ ! -d "$repo" ]; then
    printf 'gate-export: no such repository directory: %s\n' "${repo:-<empty>}" >&2
    return 2
  fi
  case "$mode" in
    head | worktree) ;;
    *)
      printf 'gate-export: unknown export mode: %s\n' "$mode" >&2
      return 2
      ;;
  esac
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    printf 'gate-export: %s is not a git checkout\n' "$repo" >&2
    return 2
  }
  commit="$(git -C "$repo" rev-parse --verify "$ref^{commit}" 2>/dev/null)" || {
    printf 'gate-export: cannot resolve %s to a commit\n' "$ref" >&2
    return 2
  }

  gate_export_cleanup
  GATE_EXPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/coursebook-gate.XXXXXXXX")" || {
    printf 'gate-export: mktemp failed\n' >&2
    return 2
  }
  case "$GATE_EXPORT_DIR" in
    "$repo" | "$repo"/*)
      gate_export_cleanup
      printf 'gate-export: scratch dir is inside the checkout; unset TMPDIR or point it outside\n' >&2
      return 2
      ;;
  esac

  if [ "$mode" = "worktree" ]; then
    GATE_EXPORT_INDEX="$(mktemp "${TMPDIR:-/tmp}/coursebook-index.XXXXXXXX")" || {
      gate_export_cleanup
      printf 'gate-export: mktemp failed\n' >&2
      return 2
    }
    if ! GIT_INDEX_FILE="$GATE_EXPORT_INDEX" git -C "$repo" read-tree "$commit" ||
      ! GIT_INDEX_FILE="$GATE_EXPORT_INDEX" git -C "$repo" add -u -- . ||
      ! tree="$(GIT_INDEX_FILE="$GATE_EXPORT_INDEX" git -C "$repo" write-tree)"; then
      gate_export_cleanup
      printf 'gate-export: could not build an index of the working tree\n' >&2
      return 1
    fi
    if ! git -C "$repo" archive --format=tar "$tree" | tar -x -C "$GATE_EXPORT_DIR"; then
      gate_export_cleanup
      printf 'gate-export: export of the working tree failed\n' >&2
      return 1
    fi
  else
    if ! git -C "$repo" archive --format=tar "$commit" | tar -x -C "$GATE_EXPORT_DIR"; then
      gate_export_cleanup
      printf 'gate-export: export of %s failed\n' "$ref" >&2
      return 1
    fi
  fi

  GATE_COMMIT="$commit"
  GATE_EXPORT_FILES="$(find "$GATE_EXPORT_DIR" -type f | wc -l | tr -d ' ')"
  if [ "$GATE_EXPORT_FILES" -eq 0 ]; then
    gate_export_cleanup
    printf 'gate-export: export is empty\n' >&2
    return 1
  fi
  return 0
}
