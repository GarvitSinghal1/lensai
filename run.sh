#!/bin/bash
# Lens AI — Run Script
# Activates the project venv and runs main.py

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

export PYTHONDONTWRITEBYTECODE=1

# Activate virtual environment
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
else
    echo "❌ Virtual environment not found at ${VENV_DIR}"
    echo "   Create it with: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Check .env permissions (Google Drive sync lock workaround)
if [ -f ".env" ]; then
    if ! [ -r ".env" ]; then
        echo "⚠️  WARNING: .env file exists but is not readable (Google Drive sync lock?)"
        echo "   Try: xattr -d com.apple.quarantine .env"
        echo "   Or export HF_TOKEN manually."
    else
        # Try to export vars to help python finding them if load_dotenv fails
        set -a
        source .env 2>/dev/null
        set +a
    fi
fi

echo "🔮 Lens AI — AI News Video Factory"
echo "=================================="
echo "Python: $(python3 --version)"
echo "Working dir: ${SCRIPT_DIR}"
echo ""

# Pass all arguments through to main.py
exec python3 "${SCRIPT_DIR}/main.py" "$@"
