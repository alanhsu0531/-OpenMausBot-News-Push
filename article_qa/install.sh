#!/bin/bash
# 在 Mac 安裝「文章問答」bot 的讀文工具到 ~/.article-qa
# 用法：bash install.sh            （從這個資料夾的 aqa.py 安裝）
#       BRANCH=main bash install.sh （沒有 repo 時，從 GitHub 下載）
set -euo pipefail

HOME_DIR="${AQA_HOME:-$HOME/.article-qa}"
BRANCH="${BRANCH:-main}"
RAW="https://raw.githubusercontent.com/alanhsu0531/-OpenMausBot-News-Push/${BRANCH}/article_qa"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

mkdir -p "$HOME_DIR/cache"

if [ -n "$HERE" ] && [ -f "$HERE/aqa.py" ]; then
  cp "$HERE/aqa.py" "$HOME_DIR/aqa.py"
  cp "$HERE/requirements.txt" "$HOME_DIR/requirements.txt"
else
  curl -fsSL "$RAW/aqa.py" -o "$HOME_DIR/aqa.py"
  curl -fsSL "$RAW/requirements.txt" -o "$HOME_DIR/requirements.txt"
fi

PY="$(command -v python3)"
if [ ! -x "$HOME_DIR/venv/bin/python" ]; then
  "$PY" -m venv "$HOME_DIR/venv"
fi
"$HOME_DIR/venv/bin/pip" install --quiet --upgrade pip
"$HOME_DIR/venv/bin/pip" install --quiet -r "$HOME_DIR/requirements.txt"

cat > "$HOME_DIR/aqa" <<EOF
#!/bin/bash
exec "$HOME_DIR/venv/bin/python" "$HOME_DIR/aqa.py" "\$@"
EOF
chmod +x "$HOME_DIR/aqa"

echo "安裝完成：$HOME_DIR/aqa"
"$HOME_DIR/aqa" --help | head -3
