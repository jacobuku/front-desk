#!/bin/sh
# scripts/check_secrets.sh — 提交前密钥检查（spec v1.2 §0 规矩 6、§8.2、§9）
#
# 扫描 git 索引（已暂存 + 已跟踪）的文件名和内容，命中任一规则就拒绝提交。
# 只输出 文件:行号 ← 规则名，绝不打印命中的明文，避免密钥进终端和日志。
# 正则一律只用 POSIX 字符类（[[:space:]] 等），不用 \s \d \w ——
# macOS 自带的 BSD grep 对这些 GNU 扩展支持不可靠。
# 所有规则都扫完再决定，便于核对"命中数 = 规则数"。

set -u

root=$(git rev-parse --show-toplevel) || exit 1
cd "$root" || exit 1

tmp=$(mktemp -t check_secrets.XXXXXX) || exit 1
trap 'rm -f "$tmp" "$tmp.u"' EXIT HUP INT TERM

# --- 内容规则（7 条）---
scan_content() {
  rule=$1
  pat=$2
  git grep --cached --color=never -I -n -i -E -e "$pat" -- . 2>/dev/null \
    | cut -d: -f1,2 \
    | awk -v r="$rule" '{ print $0 " ← " r }' >> "$tmp"
}

scan_content anthropic_key        'sk-ant-[A-Za-z0-9_-]{20,}'
scan_content telegram_token       '[0-9]{8,10}:[A-Za-z0-9_-]{35}'
scan_content google_api_key       'AIza[0-9A-Za-z_-]{35}'
scan_content google_client_secret 'GOCSPX-[A-Za-z0-9_-]{10,}'
scan_content aws_access_key       'AKIA[0-9A-Z]{16}'
scan_content private_key_block    '-----BEGIN [A-Z ]*PRIVATE KEY-----'
scan_content generic_assignment   "(api[_-]?key|apikey|secret|token|passwd|password)[\"']?[[:space:]]*[:=][[:space:]]*[\"'][A-Za-z0-9+/_=-]{16,}[\"']"

# --- 文件名规则（2 条）---
git ls-files --cached | while read -r f; do
  base=${f##*/}
  case "$base" in
    .env.example) : ;;
    .env|.env.*) printf '%s ← env_file\n' "$f" ;;
  esac
  case "$base" in
    credentials.json|*token*.json|*.db|*.sqlite|*.sqlite3|*.pem|*.p12)
      printf '%s ← credential_file\n' "$f" ;;
  esac
done >> "$tmp"

if [ -s "$tmp" ]; then
  sort -u "$tmp" > "$tmp.u"
  count=$(wc -l < "$tmp.u" | tr -d ' ')
  echo "check_secrets: 拒绝提交 —— 命中 $count 处疑似密钥或凭据："
  sed 's/^/  /' "$tmp.u"
  echo "check_secrets: 移除上述内容（改为从 .env 读取）后再提交。"
  exit 1
fi

exit 0
