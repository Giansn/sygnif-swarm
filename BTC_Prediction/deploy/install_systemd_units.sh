#!/usr/bin/env bash
# Expand deploy/systemd/*.service.in → real units for any clone path.
#
# Usage:
#   ./install_systemd_units.sh                     # auto-detect bundle root (parent of BTC_Prediction)
#   ./install_systemd_units.sh /opt/myswarm        # absolute path to clone root (contains BTC_Prediction/)
#   ./install_systemd_units.sh /opt/myswarm /usr/bin/python3
#   ./install_systemd_units.sh --dry-run /tmp/u /opt/myswarm   # write *.service to /tmp/u only
#
# Optional env:
#   SERVICE_USER   (default: ubuntu)
#   SERVICE_GROUP  (default: same as SERVICE_USER)
set -euo pipefail

DRY_RUN=""
OUT_DIR=""
while [[ "${1:-}" == "--dry-run" ]]; do
  DRY_RUN=1
  OUT_DIR="${2:?--dry-run needs output directory}"
  shift 2
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# deploy/ → BTC_Prediction/ → repo root (directory that contains BTC_Prediction/)
AUTO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_ROOT="${1:-$AUTO_ROOT}"
PYTHON="${2:-$BUNDLE_ROOT/.venv/bin/python3}"
SERVICE_USER="${SERVICE_USER:-ubuntu}"
SERVICE_GROUP="${SERVICE_GROUP:-$SERVICE_USER}"

if [[ ! -d "$BUNDLE_ROOT/BTC_Prediction/scripts" ]]; then
  echo "error: BUNDLE_ROOT must contain BTC_Prediction/scripts (got: $BUNDLE_ROOT)" >&2
  exit 2
fi
if [[ ! -x "$PYTHON" && "$PYTHON" != *python* ]]; then
  : # allow non-executable path for dry documentation; still warn
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "warning: PYTHON is not executable: $PYTHON (set venv or pass second arg)" >&2
fi

substitute() {
  local in_path="$1" out_path="$2"
  python3 - <<'PY' "$in_path" "$out_path" "$BUNDLE_ROOT" "$PYTHON" "$SERVICE_USER" "$SERVICE_GROUP"
import pathlib, sys
src, dst, root, py, user, group = sys.argv[1:7]
text = pathlib.Path(src).read_text(encoding="utf-8")
repl = {
    "@@BUNDLE_ROOT@@": root,
    "@@PYTHON@@": py,
    "@@SERVICE_USER@@": user,
    "@@SERVICE_GROUP@@": group,
}
for k, v in repl.items():
    text = text.replace(k, v)
pathlib.Path(dst).write_text(text, encoding="utf-8", newline="\n")
PY
}

SYSTEMD_SRC="$SCRIPT_DIR/systemd"
UNITS=(sygnif-neurolinked.service sygnif-bybit-nl-feed.service sygnif-swarm-predict-loop.service)
for u in "${UNITS[@]}"; do
  template="$SYSTEMD_SRC/${u}.in"
  if [[ ! -f "$template" ]]; then
    echo "error: missing template $template" >&2
    exit 3
  fi
  if [[ -n "$DRY_RUN" ]]; then
    mkdir -p "$OUT_DIR"
    substitute "$template" "$OUT_DIR/$u"
    echo "wrote $OUT_DIR/$u"
  else
    tmp="$(mktemp)"
    substitute "$template" "$tmp"
    sudo install -m 0644 "$tmp" "/etc/systemd/system/$u"
    rm -f "$tmp"
    echo "installed /etc/systemd/system/$u"
  fi
done

if [[ -z "$DRY_RUN" ]]; then
  sudo systemctl daemon-reload
  echo "Run: sudo systemctl enable --now sygnif-neurolinked sygnif-bybit-nl-feed sygnif-swarm-predict-loop"
fi
