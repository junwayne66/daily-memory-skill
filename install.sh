#!/usr/bin/env bash
#
# daily-memory-skill plugin installer
#
# One-command install for OpenClaw and Hermes, similar to `/plugin install
# daily-memory-skill`. Keeps a single canonical skill copy in a shared
# directory and symlinks each platform's skills folder to it, so one
# `update` refreshes every agent.
#
# Quick start (inside the target container/host):
#
#   ./install.sh install              # install for all detected platforms
#   ./install.sh install openclaw     # only OpenClaw
#   ./install.sh install hermes       # only Hermes
#   ./install.sh status               # show install state
#   ./install.sh update               # refresh the canonical copy
#   ./install.sh uninstall            # remove platform links (data kept)
#
# Remote one-liner (no checkout needed; clones into the share dir):
#
#   curl -fsSL https://raw.githubusercontent.com/junwayne66/daily-memory-skill/main/install.sh | bash -s -- install
#
# Defaults match the standard container layout and can be overridden by
# flags or environment variables:
#
#   share dir      --share-dir      DAILY_MEMORY_SHARE_DIR   /workspace/share-skills (fallback ~/.agents/skills)
#   openclaw home  --openclaw-home  OPENCLAW_HOME            ~/.openclaw
#   hermes home    --hermes-home    HERMES_HOME              ~/.hermes
#   repo url       --repo           DAILY_MEMORY_REPO        https://github.com/junwayne66/daily-memory-skill
#   repo branch    --branch         DAILY_MEMORY_BRANCH      main

set -euo pipefail

SKILL_NAME="daily-memory-skill"
DEFAULT_REPO="${DAILY_MEMORY_REPO:-https://github.com/junwayne66/daily-memory-skill}"

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SHARE_DIR="${DAILY_MEMORY_SHARE_DIR:-}"
REPO_URL="$DEFAULT_REPO"
REPO_BRANCH="${DAILY_MEMORY_BRANCH:-main}"

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '2,30p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
    exit 0
}

# ---------------------------------------------------------------- helpers

default_share_dir() {
    if [ -n "$SHARE_DIR" ]; then
        echo "$SHARE_DIR"
    elif [ -d /workspace ] && [ -w /workspace ]; then
        echo "/workspace/share-skills"
    else
        echo "$HOME/.agents/skills"
    fi
}

# Directory of this script when run from a checkout; empty when piped.
source_dir() {
    local src="${BASH_SOURCE[0]:-}"
    if [ -n "$src" ] && [ -f "$src" ]; then
        local dir
        dir="$(cd "$(dirname "$src")" && pwd)"
        if [ -f "$dir/SKILL.md" ]; then
            echo "$dir"
            return 0
        fi
    fi
    echo ""
}

canonical_dir() { echo "$(default_share_dir)/$SKILL_NAME"; }

require_python() {
    command -v python3 >/dev/null 2>&1 || die "python3 is required (used by tools/memoryctl)."
}

# Copy the skill into the canonical share location (full replace, atomic-ish).
sync_canonical() {
    local src="$1" dest
    dest="$(canonical_dir)"
    if [ -n "$src" ] && [ "$src" = "$dest" ]; then
        log "Running from the canonical copy; skipping sync ($dest)"
        return 0
    fi
    mkdir -p "$(dirname "$dest")"
    if [ -z "$src" ]; then
        # Piped install: clone the repo into the share dir.
        command -v git >/dev/null 2>&1 || die "git is required for remote install."
        if [ -d "$dest/.git" ]; then
            log "Updating existing clone at $dest (branch $REPO_BRANCH)"
            git -C "$dest" fetch origin "$REPO_BRANCH"
            git -C "$dest" checkout "$REPO_BRANCH"
            git -C "$dest" pull --ff-only origin "$REPO_BRANCH"
        else
            [ -e "$dest" ] && die "$dest exists but is not a git clone; remove it or install from a checkout."
            log "Cloning $REPO_URL (branch $REPO_BRANCH) -> $dest"
            git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$dest"
        fi
        return 0
    fi
    log "Syncing skill: $src -> $dest"
    local staging
    staging="$(mktemp -d "$(dirname "$dest")/.${SKILL_NAME}.XXXXXX")"
    tar -C "$src" \
        --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' \
        --exclude='share-skills' --exclude='*.pyc' \
        -cf - . | tar -C "$staging" -xf -
    rm -rf "$dest"
    mv "$staging" "$dest"
}

link_skill() {
    local platform_home="$1" canonical="$2"
    mkdir -p "$platform_home/skills"
    ln -sfn "$canonical" "$platform_home/skills/$SKILL_NAME"
    log "Linked $platform_home/skills/$SKILL_NAME -> $canonical"
}

init_workspace() {
    local workdir="$1" canonical="$2"
    python3 "$canonical/tools/memoryctl.py" --workdir "$workdir" init >/dev/null
    mkdir -p "$workdir/runs"
    log "Workspace ready: $workdir"
}

write_if_missing() {
    local path="$1" content="$2"
    if [ ! -f "$path" ]; then
        printf '%s\n' "$content" > "$path"
        log "Wrote $path"
    fi
}

bootstrap_openclaw_workspace() {
    local ws="$1"
    write_if_missing "$ws/AGENTS.md" '# AGENTS.md - Daily Memory Agent

Use `$daily-memory-skill` for every scheduled archive run.

You are an orchestrator. Run guards first (run guard, auth verification, channel identity, source planning), then parallel sync loop workers per source family, then drain the loop pipeline with `memoryctl run --steps classify,graph,attention,index`, processing and committing each batch the engine issues. Finish with report composition, safety review, memory index verification, and delivery preparation.

Do not store raw transcripts in native long-term memory. Do not notify third parties or update Feishu/Base records without explicit user approval. Owner report delivery is allowed only when configured.'
    write_if_missing "$ws/MEMORY.md" '# Daily Memory Bootstrap

Canonical Daily Memory archive. Keep this root file short. The knowledge vault lives under `knowledge/`; raw evidence under `sources/`; loop engine state under `state/`; run control under `runs/`; reports under `reports/`.'
}

bootstrap_hermes_workspace() {
    local ws="$1"
    write_if_missing "$ws/MEMORY.md" '# Daily Memory Bootstrap

Canonical Daily Memory archive for Hermes. Raw evidence lives under `sources/`; the knowledge vault under `knowledge/`; loop engine state under `state/`; bridge notes at `knowledge/daily-memory-YYYY-MM-DD.md`; reports under `reports/`.'
}

# ---------------------------------------------------------------- platforms

detect_platforms() {
    local found=()
    [ -d "$OPENCLAW_HOME" ] && found+=(openclaw)
    [ -d "$HERMES_HOME" ] && found+=(hermes)
    echo "${found[*]:-}"
}

install_openclaw() {
    local canonical="$1" ws="$OPENCLAW_HOME/workspace-daily-memory"
    [ -d "$OPENCLAW_HOME" ] || warn "OpenClaw home $OPENCLAW_HOME did not exist; creating it."
    mkdir -p "$OPENCLAW_HOME"
    link_skill "$OPENCLAW_HOME" "$canonical"
    init_workspace "$ws" "$canonical"
    bootstrap_openclaw_workspace "$ws"
    cat <<EOF

  OpenClaw next steps (manual, see references/openclaw-auto-install.md):
    - Add a 'daily-memory' agent with workspace: $ws
    - Point main agent memorySearch.extraPaths at: $ws/knowledge
    - Schedule the nightly run: 0 22 * * * (Asia/Shanghai)
EOF
}

install_hermes() {
    local canonical="$1" ws="$HERMES_HOME/daily-memory"
    [ -d "$HERMES_HOME" ] || warn "Hermes home $HERMES_HOME did not exist; creating it."
    mkdir -p "$HERMES_HOME"
    link_skill "$HERMES_HOME" "$canonical"
    init_workspace "$ws" "$canonical"
    bootstrap_hermes_workspace "$ws"
    cat <<EOF

  Hermes next steps (manual, see references/hermes-auto-install.md):
    - Add a native memory pointer: "Daily Memory canonical root: $ws"
    - Schedule the nightly run via Hermes scheduler or cron: 0 22 * * *
EOF
}

uninstall_platform() {
    local platform_home="$1" name="$2"
    local link="$platform_home/skills/$SKILL_NAME"
    if [ -L "$link" ] || [ -e "$link" ]; then
        rm -rf "$link"
        log "Removed $link"
    else
        log "$name: not installed ($link missing)"
    fi
}

verify_platform() {
    local platform_home="$1" name="$2" ws="$3"
    local link="$platform_home/skills/$SKILL_NAME" ok=1
    if [ -f "$link/SKILL.md" ]; then
        log "OK  $name skill: $link -> $(readlink -f "$link")"
    else
        warn "FAIL $name skill link broken: $link"; ok=0
    fi
    if [ -d "$ws/knowledge" ] && [ -d "$ws/sources" ]; then
        log "OK  $name workspace: $ws"
    else
        warn "FAIL $name workspace not initialized: $ws"; ok=0
    fi
    return $((1 - ok))
}

status_platform() {
    local platform_home="$1" name="$2" ws="$3"
    local link="$platform_home/skills/$SKILL_NAME"
    if [ -f "$link/SKILL.md" ]; then
        echo "  $name: installed"
        echo "    skill link : $link -> $(readlink -f "$link")"
    else
        echo "  $name: not installed (home: $platform_home)"
        return 0
    fi
    if [ -d "$ws/knowledge" ]; then
        echo "    workspace  : $ws"
        python3 "$link/tools/memoryctl.py" --workdir "$ws" status 2>/dev/null \
            | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    for name, s in d["loops"].items():
        if s.get("kind") == "llm":
            print("    loop {:<9}: processed={} pending={}".format(name, s["processed"], s["pending"]))
except Exception:
    pass' || true
    else
        echo "    workspace  : $ws (not initialized)"
    fi
}

# ---------------------------------------------------------------- commands

cmd_install() {
    local targets=("$@")
    require_python
    local src canonical
    src="$(source_dir)"
    sync_canonical "$src"
    canonical="$(canonical_dir)"
    [ -f "$canonical/SKILL.md" ] || die "canonical copy missing at $canonical"

    if [ ${#targets[@]} -eq 0 ] || [ -z "${targets[0]:-}" ] || [ "${targets[0]}" = "all" ]; then
        read -r -a targets <<< "$(detect_platforms)"
        [ ${#targets[@]} -gt 0 ] && [ -n "${targets[0]:-}" ] \
            || die "no platform detected at $OPENCLAW_HOME or $HERMES_HOME; pass 'openclaw' and/or 'hermes' explicitly."
        log "Detected platforms: ${targets[*]}"
    fi

    local failed=0
    for t in "${targets[@]}"; do
        case "$t" in
            openclaw) install_openclaw "$canonical" ;;
            hermes)   install_hermes "$canonical" ;;
            *) die "unknown platform '$t' (expected: openclaw, hermes, all)" ;;
        esac
    done

    log "Verifying..."
    for t in "${targets[@]}"; do
        case "$t" in
            openclaw) verify_platform "$OPENCLAW_HOME" openclaw "$OPENCLAW_HOME/workspace-daily-memory" || failed=1 ;;
            hermes)   verify_platform "$HERMES_HOME" hermes "$HERMES_HOME/daily-memory" || failed=1 ;;
        esac
    done
    [ "$failed" -eq 0 ] || die "verification failed"
    log "Done. Run '$(canonical_dir)/install.sh status' anytime to inspect the install."
}

cmd_update() {
    require_python
    local src
    src="$(source_dir)"
    sync_canonical "$src"
    log "Canonical copy refreshed at $(canonical_dir). Platform links pick it up automatically."
}

cmd_status() {
    echo "daily-memory-skill install status"
    echo "  share dir : $(default_share_dir)"
    if [ -f "$(canonical_dir)/SKILL.md" ]; then
        echo "  canonical : $(canonical_dir) (present)"
    else
        echo "  canonical : $(canonical_dir) (missing)"
    fi
    status_platform "$OPENCLAW_HOME" openclaw "$OPENCLAW_HOME/workspace-daily-memory"
    status_platform "$HERMES_HOME" hermes "$HERMES_HOME/daily-memory"
}

cmd_uninstall() {
    local targets=("$@") purge=0 filtered=()
    for t in "${targets[@]:-}"; do
        [ "$t" = "--purge" ] && purge=1 || filtered+=("$t")
    done
    targets=("${filtered[@]:-}")
    if [ ${#targets[@]} -eq 0 ] || [ -z "${targets[0]:-}" ] || [ "${targets[0]}" = "all" ]; then
        targets=(openclaw hermes)
    fi
    for t in "${targets[@]}"; do
        case "$t" in
            openclaw) uninstall_platform "$OPENCLAW_HOME" openclaw ;;
            hermes)   uninstall_platform "$HERMES_HOME" hermes ;;
            *) die "unknown platform '$t'" ;;
        esac
    done
    if [ "$purge" -eq 1 ]; then
        rm -rf "$(canonical_dir)"
        log "Removed canonical copy $(canonical_dir)"
    fi
    log "Workspaces (sources/knowledge/reports) were kept. Remove them manually if desired."
}

# ---------------------------------------------------------------- main

main() {
    local cmd="" args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --share-dir)     SHARE_DIR="$2"; shift 2 ;;
            --openclaw-home) OPENCLAW_HOME="$2"; shift 2 ;;
            --hermes-home)   HERMES_HOME="$2"; shift 2 ;;
            --repo)          REPO_URL="$2"; shift 2 ;;
            --branch)        REPO_BRANCH="$2"; shift 2 ;;
            -h|--help)       usage ;;
            install|update|status|uninstall)
                cmd="$1"; shift ;;
            *) args+=("$1"); shift ;;
        esac
    done
    [ -n "$cmd" ] || cmd="install"
    case "$cmd" in
        install)   cmd_install "${args[@]:-}" ;;
        update)    cmd_update ;;
        status)    cmd_status ;;
        uninstall) cmd_uninstall "${args[@]:-}" ;;
    esac
}

main "$@"
