#!/usr/bin/env bash
# 講義イメージを起動。作業ディレクトリ(pai2026)をコンテナの ~/pai_work にマウント
# APIキーは環境変数 ANTHROPIC_API_KEY か、pai-final-task/.env (gitignore済) から読む
set -e
TASK_DIR="$(cd "$(dirname "$0")/.." && pwd)"      # pai-final-task
HOST_DIR="$(cd "${TASK_DIR}/.." && pwd)"           # pai2026
if [ -z "${ANTHROPIC_API_KEY}" ] && [ -f "${TASK_DIR}/.env" ]; then
  set -a; . "${TASK_DIR}/.env"; set +a
fi
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY を設定するか ${TASK_DIR}/.env に書いてください}"
docker run -d --name pai \
  -p 6080:80 --shm-size=512m \
  -v "${HOST_DIR}:/home/ubuntu/pai_work" \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  airobotbook/ros2-desktop-ai-robot-book-humble:latest
echo "http://localhost:6080 を開いてください。別ターミナル: docker exec -it pai bash"
