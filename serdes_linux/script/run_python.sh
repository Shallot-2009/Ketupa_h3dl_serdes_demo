#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$ROOT/script/extractors/cds_env"

resolve_runtime() {
    candidate=${PYTHON_EXE:-}
    if [ -n "$candidate" ]; then
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
        resolved=$(command -v -- "$candidate" 2>/dev/null || true)
        if [ -n "$resolved" ] && [ -x "$resolved" ]; then
            printf '%s\n' "$resolved"
            return 0
        fi
    fi

    if [ -f "$ENV_FILE" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            case "$line" in
                PYTHON_EXE=*)
                    candidate=${line#PYTHON_EXE=}
                    if [ -x "$candidate" ]; then
                        printf '%s\n' "$candidate"
                        return 0
                    fi
                    resolved=$(command -v -- "$candidate" 2>/dev/null || true)
                    if [ -n "$resolved" ] && [ -x "$resolved" ]; then
                        printf '%s\n' "$resolved"
                        return 0
                    fi
                    ;;
            esac
        done < "$ENV_FILE"
    fi
    return 1
}

RUNTIME=$(resolve_runtime) || {
    echo "OpenKetupa runtime is unavailable. Configure executable PYTHON_EXE in script/extractors/cds_env." >&2
    exit 127
}

export PYTHON_EXE="$RUNTIME"
export PYTHONUNBUFFERED=1
exec "$RUNTIME" "$@"
