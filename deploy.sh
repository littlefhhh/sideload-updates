#!/usr/bin/env bash
# 一键绑定远程仓库、按真实 Pages 地址重新生成源并推送
# 用法: ./deploy.sh <GitHub用户名>/<仓库名>
set -euo pipefail

REPO="${1:-}"
if [ -z "$REPO" ] || [[ "$REPO" != */* ]]; then
  echo "用法: ./deploy.sh <GitHub用户名>/<仓库名>"
  echo "例如: ./deploy.sh liguofang/sideload-updates"
  exit 1
fi

OWNER="${REPO%%/*}"
NAME="${REPO##*/}"
BASE="https://${OWNER}.github.io/${NAME}"

cd "$(dirname "$0")"

echo "→ 订阅地址将生成: ${BASE}/source.json"
echo "→ 重新抓取上游最新版本…"
python3 gen_source.py --base-url "$BASE"

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${REPO}.git"

git add -A
git commit -m "chore: 绑定 Pages 地址 ${BASE}" >/dev/null 2>&1 || echo "→ 内容无变化，跳过提交"

echo "→ 推送到 ${REPO}…"
git push -u origin main

cat <<EOF

推送完成。剩下两步手动操作：

1. 打开 https://github.com/${REPO}/settings/pages
   Source 选「Deploy from a branch」，分支 main、目录 /docs，保存。
   等 1～2 分钟，访问 ${BASE}/ 应能看到列表页。

2. 打开 https://github.com/${REPO}/actions/workflows/update-source.yml
   点「Run workflow」跑一次，确认能自动提交。

手机端订阅地址：
   ${BASE}/source.json
EOF
