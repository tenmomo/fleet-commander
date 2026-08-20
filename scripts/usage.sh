#!/bin/zsh
# Claude 用量水位一键读(官方 oauth/usage API;token 取自 Keychain,不落盘不落屏)
# 用法: bin/usage.sh          → 三行水位
#       bin/usage.sh --json   → 原始 JSON(给脚本/守卫消费)
# 归属: fleet-commander/scripts(owner ruling 08-14 裁)。/usage TUI 面板的无头等价物,任何 commander 管烧量节奏用。
# 出处: 2026-08-14 实测;三读法排序见 SLASH-COMMANDS.md /usage 行注。
# ⚠ token 只进 shell 变量;本脚本任何分支都不得 echo $tok。
set -u
tok=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null \
      | python3 -c "import json,sys;print(json.load(sys.stdin)['claudeAiOauth']['accessToken'])" 2>/dev/null)
[ -z "${tok:-}" ] && { echo "FATAL: Keychain 里取不到 Claude Code-credentials"; exit 1; }
resp=$(curl -s -m 20 "https://api.anthropic.com/api/oauth/usage" \
       -H "Authorization: Bearer $tok" -H "anthropic-beta: oauth-2025-04-20")
[ -z "$resp" ] && { echo "FATAL: usage API 无响应"; exit 1; }
if [ "${1:-}" = "--json" ]; then printf '%s\n' "$resp"; exit 0; fi
printf '%s' "$resp" | python3 -c "
import json,sys
d=json.load(sys.stdin)
def line(name,o):
    if not o: return
    print(f\"{name:<22}{o.get('percent',o.get('utilization','?'))}%  重置 {o.get('resets_at','—')}\")
line('5h session', d.get('five_hour') and {'percent':d['five_hour']['utilization'],'resets_at':d['five_hour']['resets_at']})
for l in d.get('limits',[]):
    line(f\"{l.get('kind','?')}\", l)
"
