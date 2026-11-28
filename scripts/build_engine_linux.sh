#!/usr/bin/env bash
# Build pvm-control-engine as a PyInstaller one-file Linux executable.
set -Eeuo pipefail

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

info() {
    printf '[plaivid build] %s\n' "$*"
}

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    cat <<'EOF'
Usage: scripts/build_engine_linux.sh

Builds pvm-control-engine as a PyInstaller --onefile executable at:
  pvm_control_engine/dist/pvm-control-engine

Requires Linux and Python 3.12+. Uses or creates the repository .venv and
installs PyInstaller into that environment if it is not already installed.
The executable still requires host-provided PVM tools such as sbell and
pvm-running-vms, plus compatible Linux system libraries.
EOF
    exit 0
fi
[[ $# -eq 0 ]] || fail "Unknown argument: $1"
[[ "$(uname -s)" == Linux ]] || fail 'This build script supports Linux only.'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
ENGINE="${ROOT}/pvm_control_engine"
[[ -f "${ENGINE}/pyproject.toml" && -d "${ENGINE}/src/pvm_control_engine" ]] \
    || fail "Could not find the Engine project under ${ENGINE}."

python_ok() {
    command -v "$1" >/dev/null 2>&1 \
        && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

VENV="${ROOT}/.venv"
VENV_PY="${VENV}/bin/python"
if [[ -L "$VENV" ]]; then
    fail "Refusing to use a symlink as the repository virtual environment: ${VENV}"
elif [[ -e "$VENV" ]]; then
    [[ -x "$VENV_PY" ]] || fail "Existing ${VENV} is incomplete; move it aside and rerun."
    python_ok "$VENV_PY" || fail "Existing ${VENV} must use Python 3.12+; move it aside and rerun."
else
    PYTHON="${PLAIVID_PYTHON:-}"
    if [[ -n "$PYTHON" ]]; then
        python_ok "$PYTHON" || fail "PLAIVID_PYTHON must be Python 3.12+: ${PYTHON}"
    else
        for candidate in python3.14 python3.13 python3.12 python3 python; do
            if python_ok "$candidate"; then
                PYTHON="$(command -v "$candidate")"
                break
            fi
        done
    fi
    [[ -n "$PYTHON" ]] || fail 'Python 3.12+ was not found. Install Python 3.12+ with venv/ensurepip support.'
    "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1 \
        || fail "${PYTHON} is missing venv or ensurepip support."
    info "Creating ${VENV} with $($PYTHON --version 2>&1)"
    "$PYTHON" -m venv "$VENV"
fi

if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    info 'Bootstrapping pip with ensurepip'
    "$VENV_PY" -m ensurepip --upgrade
fi
if ! "$VENV_PY" -c 'import PyInstaller' >/dev/null 2>&1; then
    info 'Installing PyInstaller in the repository virtual environment'
    "$VENV_PY" -m pip install --upgrade pyinstaller
fi

ENTRYPOINT="$(mktemp "${TMPDIR:-/tmp}/pvm-control-engine-entry.XXXXXX.py")"
trap 'rm -f "$ENTRYPOINT"' EXIT
cat > "$ENTRYPOINT" <<'PY'
from pvm_control_engine.bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
PY

OUTPUT_DIR="${ENGINE}/dist"
WORK_DIR="${ENGINE}/build/pyinstaller"
SPEC_DIR="${ENGINE}/build"
mkdir -p "$OUTPUT_DIR" "$WORK_DIR" "$SPEC_DIR"
info 'Building one-file executable; this only analyzes/packages the Engine and does not contact PVM.'
"$VENV_PY" -m PyInstaller \
    --clean --noconfirm --onefile --console \
    --name pvm-control-engine \
    --paths "${ENGINE}/src" \
    --collect-submodules pvm_control_engine \
    --distpath "$OUTPUT_DIR" \
    --workpath "$WORK_DIR" \
    --specpath "$SPEC_DIR" \
    "$ENTRYPOINT"

BINARY="${OUTPUT_DIR}/pvm-control-engine"
[[ -x "$BINARY" ]] || fail "PyInstaller did not produce an executable at ${BINARY}."
info 'Smoke-checking CLI help (no authentication or PVM command is run)'
"$BINARY" --help >/dev/null
printf '\nBuild complete: %s\n' "$BINARY"
printf 'Copy this file to a compatible Linux host. The host must still provide its configured PVM commands and system libraries.\n'
