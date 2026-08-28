#!/usr/bin/env bash
# ==============================================================================
# LinguaFlow — chạy song song Backend (FastAPI) và Frontend (Next.js).
#
#   ./run.sh              # chạy cả hai
#   ./run.sh backend      # chỉ backend
#   ./run.sh frontend     # chỉ frontend
#   SKIP_MIGRATE=1 ./run.sh
#
# Frontend là `frontend/` (bản đang phát triển, có màn Calendar + Google OAuth).
# `frontend-v1/` là bản cũ, KHÔNG chạy ở đây.
# ==============================================================================

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Mọi log và mọi lệnh Python đều phải in được tiếng Việt / CJK / Thái / Ả Rập.
# Console Windows mặc định là cp1252 nên thiếu dòng này là UnicodeEncodeError.
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

BE_PID=""
FE_PID=""

# Git Bash trên Windows không có setsid. Ở đó chỉ chạy trực tiếp và giết theo
# từng PID; trên Linux/macOS dùng setsid để giết được cả nhóm tiến trình con
# (Next.js sinh thêm tiến trình và sẽ giữ cổng 3000 nếu chỉ giết tiến trình cha).
if command -v setsid >/dev/null 2>&1; then
    run_detached() { setsid "$@" & }
else
    run_detached() { "$@" & }
fi

cleanup() {
    trap - INT TERM EXIT
    echo ""
    echo "=================================================="
    echo " 🛑 Đang dừng Backend và Frontend..."
    echo "=================================================="
    # Next.js sinh tiến trình con; giết cả nhóm để không sót cái nào giữ cổng.
    for pid in "$FE_PID" "$BE_PID"; do
        [ -n "$pid" ] || continue
        kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo " ✅ Đã dừng xong."
}
trap cleanup INT TERM EXIT

echo "=================================================="
echo " 🚀 LinguaFlow — môi trường phát triển"
echo "=================================================="

# ─── 1. Tìm trình thông dịch Python ────────────────────────────────────────
# Repo không có .venv riêng (xem CLAUDE.md); môi trường thật nằm ở D:/Python/.venv.
pick_python() {
    local candidates=(
        "$ROOT_DIR/.venv/bin/python"
        "$ROOT_DIR/.venv/Scripts/python.exe"
        "${VIRTUAL_ENV:-}/bin/python"
        "${VIRTUAL_ENV:-}/Scripts/python.exe"
        "/d/Python/.venv/Scripts/python.exe"
        "D:/Python/.venv/Scripts/python.exe"
        "/mnt/d/Python/.venv/Scripts/python.exe"
    )
    for candidate in "${candidates[@]}"; do
        if [ -x "$candidate" ] || [ -f "$candidate" ]; then echo "$candidate"; return 0; fi
    done
    command -v python3 || command -v python || return 1
}

PYTHON="$(pick_python)" || {
    echo "❌ Không tìm thấy Python. Hãy tạo .venv hoặc đặt VIRTUAL_ENV." >&2
    exit 1
}
echo "🐍 Python: $PYTHON"

if ! "$PYTHON" -c "import uvicorn, langgraph" 2>/dev/null; then
    echo "❌ Môi trường Python thiếu dependency. Chạy: $PYTHON -m pip install -r requirements.txt" >&2
    exit 1
fi

# ─── 2. PostgreSQL ─────────────────────────────────────────────────────────
# Docker Engine chạy trong WSL2 trên máy này, và VM tự ngủ sau ~60s idle — kéo
# theo Postgres. Kiểm tra trước còn hơn để lỗi nổ giữa lúc migrate.
DB_PORT="$(grep -oP '(?<=@localhost:)\d+' .env 2>/dev/null | head -1 | tr -d '\r')"
DB_PORT="${DB_PORT:-5433}"
if ! "$PYTHON" -c "import socket, sys; s = socket.socket(); s.connect(('127.0.0.1', int(sys.argv[1]))); s.close()" "$DB_PORT"; then
    echo "⚠️  Không kết nối được PostgreSQL ở localhost:$DB_PORT."
    echo "    Từ WSL chạy: docker compose up -d postgres"
    exit 1
fi
echo "🐘 PostgreSQL: localhost:$DB_PORT — OK"

# ─── 3. Migration ──────────────────────────────────────────────────────────
# Alembic sở hữu schema (ADR-06); app không tự tạo bảng lúc khởi động.
run_backend() {
    if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
        echo "📦 alembic upgrade head ..."
        "$PYTHON" -m alembic upgrade head || {
            echo "❌ Migration thất bại — dừng lại." >&2
            exit 1
        }
    fi

    echo "⚡ Backend: http://localhost:$BACKEND_PORT (docs: /docs)"
    # Một tiến trình duy nhất, không --workers: ConnectionManager giữ socket
    # trong bộ nhớ tiến trình (ADR-18).
    nohup "$PYTHON" -m uvicorn src.main:app --host 0.0.0.0 --port "$BACKEND_PORT" > "$ROOT_DIR/backend.log" 2>&1 &
    BE_PID=$!
}

# ─── 4. Frontend ───────────────────────────────────────────────────────────
run_frontend() {
    [ -d "$FRONTEND_DIR" ] || { echo "❌ Không thấy $FRONTEND_DIR" >&2; exit 1; }

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo "📥 Cài dependency frontend (npm install) ..."
        (cd "$FRONTEND_DIR" && npm install) || exit 1
    fi

    # Không có .env.local thì NEXT_PUBLIC_API_URL rỗng và mọi lời gọi API
    # trỏ về chính origin của Next — lỗi 404 rất khó đoán.
    if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
        echo "⚠️  Thiếu frontend/.env.local — tạo từ .env.example."
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
        echo "    (Điền NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID nếu cần Google Sign-In.)"
    fi

    echo "🎨 Frontend: http://localhost:$FRONTEND_PORT"
    ( cd "$FRONTEND_DIR" && nohup npm run dev -- --port "$FRONTEND_PORT" > "$ROOT_DIR/frontend.log" 2>&1 & )
    FE_PID=$!
}

# ─── 5. Điều phối ──────────────────────────────────────────────────────────
case "${1:-all}" in
    backend|be)  run_backend ;;
    frontend|fe) run_frontend ;;
    all|"")      run_backend; sleep 2; run_frontend ;;
    *)           echo "Dùng: ./run.sh [all|backend|frontend]" >&2; exit 2 ;;
esac

echo ""
echo "=================================================="
[ -n "$BE_PID" ] && echo "    Backend  : http://localhost:$BACKEND_PORT/docs"
[ -n "$FE_PID" ] && echo "    Frontend : http://localhost:$FRONTEND_PORT"
echo " 💡 Ctrl+C để dừng tất cả."
echo "=================================================="
echo ""

wait
