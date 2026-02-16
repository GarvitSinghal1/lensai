#!/bin/bash
# Lens AI — Run Script
# Handles PYTHONPATH for local lib/ dependencies installed via pip --target

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${SCRIPT_DIR}/lib:${PYTHONPATH}"

echo "🔮 Lens AI — AI News Video Factory"
echo "=================================="
echo "Python: $(python3 --version)"
echo "Working dir: ${SCRIPT_DIR}"
echo ""

# Pass all arguments through to main.py
exec python3 "${SCRIPT_DIR}/main.py" "$@"
