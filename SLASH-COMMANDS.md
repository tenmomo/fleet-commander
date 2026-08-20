# 全 harness slash commands 速查

本机舰队在用的四个 harness——**Claude Code** `claude` v2.1.232、**Pi** `pi`、**Codex** `codex` v0.147.0、**omp**——的 slash 命令全表。herdr 是 workspace 管理器,没有 slash,附在末尾作 CLI 动词对照。

**取数方法(2026-08-14 实测)**:探针 workspace `w4Q`(`--cwd /tmp`,四个裸 TUI,不派活、用完 `workspace close`)。Codex 全表 = 逐屏抄 `/` 补全菜单(45 条,菜单一屏 8 行,`up`/`down` 翻页,**send-keys 会丢键**——批量连发丢约一半,必须单键 + `sleep 0.15` 且以内容而非按键数判断到底)。Claude Code / Pi / omp 的菜单同样只显 4–8 行且 `/help` 的 "Browse default commands" 列表**用 `pagedown` 翻不动**(实测 6 次 pagedown 画面零位移),于是改从装机产物取全集再回屏抽验:
- Claude Code:`claude` 是编译二进制,但 JS bundle 完整嵌在里面,`strings` + 正则抓 `{type:"local|local-jsx|prompt",name:...,description:...}` 与 `nd({name:...,menuDescription:...})` 两种注册形态。**正例验响**:抓出的 `/add-dir…/desktop` 与屏上 `/help` 首屏逐条吻合;9 条描述有歧义的(`/diff` `/fast` `/exit` `/init` `/passes` `/run` `/terminal-setup` `/ultrareview` `/rewind`)已逐条回屏打 `/` 补全实测校正。
- Pi:`dist/core/slash-commands.js` 明文,内建 22 条。屏上菜单显示 `(1/77)`——**差额 55 条全是本机 skill/extension**(`~/.pi/agent/skills/` 约 50 个,菜单里带 `skill:` 前缀和 `[u]` 标记),不是 pi 内建,别抄进内建表。
- omp:Bun 编译二进制,`strings` 抓同 pi 的 `name/description` 形态。**omp 是多级命令**,扁平抓取会把子命令混进来;下表的顶层/子级划分是按 strings 里的分组顺序反推的,只抽验了 `/goal`(屏上 `/goal` 确实只出 `goal` + `guided-goal`,子命令 `set/pause/…` 不在顶层)——**其余分组未逐条实测**。

**未验出**:`/deep-research`(Claude Code 菜单里标 `(dynamic…)`,不在 bundle 静态表内,机制未查);Claude Code 隐藏/内部命令(`/stub` `/__remote-workflow` `/workflow-launch-exec` `/mcp__` `/pro-trial-expired` `/rate-limit-options`)存在但不列入下表。

---

## Claude Code(`claude`)—— 内建 103 条

技能(skill)与插件命令也以 `/name` 出现在同一个菜单里,数量随机器变,**不计入这 103 条**;`/skills` 列当前可用技能,`/skill-doctor` 查哪些技能白占 context。

### 会话与上下文(18)

| 命令 | 作用 | 参数 |
|---|---|---|
| `/clear` | 清空 context 开新会话,旧会话留盘可 `/resume`(别名 `reset` `new`) | `[name]` |
| `/compact` | 摘要压缩当前对话腾出 context | `[自定义摘要指令]` |
| `/autocompact` | 设自动压缩触发的窗口大小 | `[auto\|<tokens>]` |
| `/context` | 显示当前 context 用量 | — |
| `/explain-usage` | 用大白话讲这轮 token 花在哪 | — |
| `/rewind` | 把代码和/或对话回滚到之前某点 | — |
| `/branch` | 从当前点分叉出一条对话分支 | `[name]` |
| `/fork` | 起一个继承全部对话的后台 agent | `<directive>` |
| `/subtask` | 带全量 context 派个 subagent,结果回本会话 | `<task>` |
| `/btw` | 问个不打断主线的侧问题 | `[question]` |
| `/resume` | 恢复历史会话(别名 `continue`) | `[会话 id 或搜索词]` |
| `/rename` | 重命名当前会话(别名 `name`) | `[name]` |
| `/recap` | 立刻生成一行会话摘要 | — |
| `/export` | 导出对话到文件或剪贴板 | `[filename]` |
| `/copy` | 复制 Claude 最后一条回复(`/copy N` 取倒数第 N 条) | `[N]` |
| `/focus` | 切焦点视图:只留你的 prompt、摘要和回复 | — |
| `/brief` | 切 brief-only 模式 | — |
| `/diff` | 看未提交改动和每轮 diff | — |

### 模型 · 推理档 · 用量(8)

| 命令 | 作用 | 参数 |
|---|---|---|
| `/model` | 设模型 | `<model>` |
| `/effort` | 设推理 effort 档 | — |
| `/fast` | 切 fast 模式(Opus 5,快而不降档) | — |
| `/advisor` | 开关「顾问」:关键节点让更强的模型参谋 | — |
| `/usage` | 看本会话花费、套餐用量、活动统计(别名 `cost` `stats`) | — |
| `/usage-credits` | 配置 usage credits / 向管理员申请(旧名 `/extra-usage`) | — |
| `/passes` | 送朋友一周 Claude Code 试用并赚 credits | — |
| `/upgrade` | 升 Max 换更高限额和更多 Opus | — |

### 目标 · 自动化 · 后台(11)

| 命令 | 作用 | 参数 |
|---|---|---|
| `/goal` | 设一个「停下来之前必须满足」的目标 | `[<condition>\|clear]` |
| `/plan` | 进 plan 模式,或看当前会话的 plan | `[open\|share\|<描述>]` |
| `/ultraplan` | 让云端 Claude Code 起草一份可编辑可批准的 plan | — |
| `/batch` | 规划大改动,再派 5–30 个隔离 worktree agent 各开一个 PR | — |
| `/workflows` | 浏览运行中与已完成的 workflow | — |
| `/loops` | 列出/新建/删除 loop(`/loop` 本身是 skill) | — |
| `/daemon` | 管后台服务与 routine | — |
| `/tasks` | 看和管所有后台在跑的东西(别名 `bashes`) | — |
| `/background` | 把当前会话丢后台,腾出终端(别名 `bg`) | `[prompt]` |
| `/stop` | 停掉这个后台会话,保留 transcript 和 worktree | — |
| `/run` | 起本项目的 app 看改动是否真的生效 | — |

### 配置 · 能力(23)

| 命令 | 作用 | 参数 |
|---|---|---|
| `/config` | 按 key 改设置(别名 `settings`) | `key=value` |
| `/permissions` | 管工具的 allow / deny 规则(别名 `allowed-tools`) | — |
| `/hooks` | 看工具事件的 hook 配置 | — |
| `/memory` | 编辑 CLAUDE.md 与 memory 设置 | — |
| `/pause-memory` | 本会话暂停 automemory(别名 `memory-pause` `toggle-memory`) | — |
| `/skills` | 列可用 skill | — |
| `/reload-skills` | 拾取会话中途在盘上新增/改动的 skill | — |
| `/skill-doctor` | 查哪些已加载 skill 没被用、在白烧 context | — |
| `/plugin` | 管插件(别名 `plugins` `marketplace`) | — |
| `/reload-plugins` | 让待生效的插件变更在当前会话生效 | `[--force]` |
| `/mcp` | 管 MCP server | `[reconnect\|enable\|disable [<server>\|all]]` |
| `/add-dir` | 加一个可访问的工作目录 | `<path>` |
| `/cd` | 把会话挪到新的工作目录 | `<path>` |
| `/ide` | 管 IDE 集成、看状态 | `[open]` |
| `/chrome` | 打开 Claude in Chrome 设置 | — |
| `/theme` | 换主题 | — |
| `/color` | 设本会话 prompt 条颜色 | — |
| `/statusline` | 配 status line UI | — |
| `/tui` | 设终端渲染器 | `[default\|fullscreen]` |
| `/keybindings` | 打开快捷键配置文件 | — |
| `/scroll-speed` | 调滚轮速度 | — |
| `/terminal-setup` | 检查终端设置(Ghostty 原生支持 Shift+Enter) | — |
| `/voice` | 切语音模式 | `[hold\|tap\|off]` |

### 账号 · 平台 · 跨端(20)

| 命令 | 作用 | 参数 |
|---|---|---|
| `/login` / `/logout` | 登录 / 登出 Anthropic 账号 | — |
| `/status` | 版本、模型、账号、API 连通性、工具状态 | — |
| `/version` | 本会话版本(自动更新可能已有更新的) | — |
| `/update` | 换到最新版,对话继续(别名 `restart`) | — |
| `/install` | 装 native build | `[options]` |
| `/doctor` | 体检并修:安装、闲置扩展、重复/臃肿 memory 文件(别名 `checkup`) | — |
| `/debug` | 开 debug 日志并排查 | — |
| `/import` | 从别的 AI coding agent 导配置 | `[codex\|gemini] [--dry-run]` |
| `/teleport` | 把会话送上云,或从 claude.ai 拉回(别名 `tp`) | — |
| `/session` | 显示云会话 URL 和二维码(别名 `remote`) | — |
| `/remote-control` | 用手机 / claude.ai/code 控制本会话(别名 `rc`) | — |
| `/remote-env` | 选云 agent 的默认环境 | — |
| `/desktop` | 会话续到 Claude Desktop(别名 `app`) | — |
| `/mobile` | 出二维码下载手机 App(别名 `ios` `android`) | — |
| `/web-setup` | 用 GitHub 账号配 Claude Code on the web | — |
| `/install-github-app` | 给仓库配 Claude GitHub Actions | — |
| `/install-slack-app` | 装 Claude Slack app | — |
| `/setup-bedrock` / `/setup-vertex` | 重配 Bedrock / Vertex 认证、区域、模型 pin | — |

### 杂项(23)

| 命令 | 作用 | 参数 |
|---|---|---|
| `/help` | 帮助与命令总览(Tab 页 General / Commands / Custom commands) | — |
| `/init` | 生成带代码库说明的 CLAUDE.md | — |
| `/powerup` | 交互小课学被忽略的功能 | — |
| `/release-notes` | 看版本更新说明 | — |
| `/feedback` | 给 Anthropic 反馈或报 bug | `[report]` |
| `/bug` | 报 bug / 分享对话(别名 `share`) | `[report]` |
| `/insights` | 分析你的 Claude Code 会话出报告 | — |
| `/team-onboarding` | 用你的使用记录生成队友上手指南 | — |
| `/list-agents` | 列可 SendMessage 的 subagent 与其他 Claude 会话(别名 `peers`) | — |
| `/autofix-pr` | 盯当前 PR 的问题并自动修 | — |
| `/ultrareview` | 起云端 agent 找并验证本分支的 bug(= `/code-review ultra`,已废弃别名) | — |
| `/artifacts` | 浏览你发布的和别人分享给你的 Artifact | — |
| `/design` | 授予/收回 agent 对 Design 项目的访问 | `consent\|revoke` |
| `/design-login` | 给 `/design-sync` 授权 claude.ai 设计系统访问 | — |
| `/design-sync` | 把 React 设计系统推到 claude.ai/design | `[<项目提示>]` |
| `/privacy-settings` | 看和改隐私设置 | — |
| `/wellbeing` | 配休息提醒与安静时段 | — |
| `/auto-mode-setup` | 配 auto mode 的环境上下文与规则 | `[--request-id …] --propose\|--apply-file` |
| `/agents` | **已移除**——改让 Claude 建/管 subagent,或直接编辑 `.claude/agents/` | — |
| `/exit` | 退出 CLI(别名 `quit`) | — |
| `/heapdump` | 把 JS heap 转储到 ~/Desktop(排障用) | — |
| `/stickers` | 订 Claude Code 贴纸 | — |
| `/radio` | 听 Claude FM lo-fi 电台 | — |

---

## Pi(`pi`)—— 内建 22 条

菜单显 `(1/77)`,内建只占 22 条,其余是本机 skill/extension(前缀 `skill:`、标 `[u]`)。**Pi 没有内建 `/goal` 也没有 `/loop`**(实测打 `/g` 只出 skill),`/help` 同样不存在——找快捷键用 `/hotkeys`。

| 命令 | 作用 | 参数 |
|---|---|---|
| `/settings` | 打开设置菜单 | — |
| `/model` | 选模型(开选择器 UI) | `<provider/model>` |
| `/scoped-models` | 开关哪些模型进 Ctrl+P 循环 | — |
| `/export` | 导出会话(默认 HTML,可给 `.html`/`.jsonl` 路径) | `[path]` |
| `/import` | 从 JSONL 导入并恢复会话 | `<path>` |
| `/share` | 把会话分享为 secret GitHub gist | — |
| `/copy` | 复制最后一条 agent 消息到剪贴板 | — |
| `/name` | 设会话显示名 | `<name>` |
| `/session` | 看会话信息与统计 | — |
| `/changelog` | 看 changelog | — |
| `/hotkeys` | 列全部快捷键 | — |
| `/fork` | 从某条历史用户消息 fork 出新分支 | — |
| `/clone` | 在当前位置复制一份会话 | — |
| `/tree` | 会话树导航(切分支) | — |
| `/trust` | 保存本项目的 trust 决定供后续会话复用 | — |
| `/login` / `/logout` | 配置 / 移除 provider 认证 | — |
| `/new` | 开新会话 | — |
| `/compact` | 手动压缩会话 context | — |
| `/resume` | 恢复另一个会话 | — |
| `/reload` | 重载 keybindings、extension、skill、prompt、theme、context 文件 | — |
| `/quit` | 退出 | — |

---

## Codex(`codex` v0.147.0)—— 45 条(逐屏实测抄全)

菜单顺序即下表顺序。首启在新目录会先弹 trust 对话框(`1. Yes, continue` / `2. No, quit`),**这一屏 herdr 会报 `idle`**,别当启动完成。

| 命令 | 作用 | 参数 |
|---|---|---|
| `/model` | 选模型与 reasoning effort | — |
| `/fast` | 1.5 倍速,用量加成 | — |
| `/ide` | 把 IDE 里的选中/打开文件等上下文带进来 | — |
| `/permissions` | 选 Codex 被允许做什么 | — |
| `/keymap` | 重映射 TUI 快捷键 | — |
| `/vim` | 开关 composer 的 Vim 模式 | — |
| `/experimental` | 开关实验特性 | — |
| `/approve` | 对最近一次自动审查拒绝批准一次重试 | — |
| `/memories` | 配置记忆的使用与生成 | — |
| `/skills` | 用 skill 改善 Codex 在特定任务上的表现 | — |
| `/import` | 从 Claude Code 导入配置、本项目和近期会话 | — |
| `/hooks` | 看和管 lifecycle hook | — |
| `/review` | 审查当前改动找问题 | — |
| `/rename` | 重命名当前 thread | — |
| `/new` | 会话中途开新 chat | — |
| `/archive` | 归档本会话并退出 | — |
| `/delete` | 永久删除本会话并退出 | — |
| `/resume` | 恢复已保存的 chat | — |
| `/fork` | fork 当前 chat | — |
| `/app` | 会话续到桌面 App | — |
| `/init` | 生成 AGENTS.md | — |
| `/compact` | 摘要压缩以免撞 context 上限 | — |
| `/plan` | 切 Plan 模式 | — |
| `/goal` | 设或看长任务的 goal | — |
| `/agent` | 切当前 agent thread(与 `/subagents` 同义) | — |
| `/side` | 在临时 fork 里开侧线对话 | — |
| `/copy` | 以 markdown 复制最后一条回复 | — |
| `/raw` | 切 raw scrollback,方便终端选中复制 | — |
| `/diff` | 看 git diff(含未跟踪文件) | — |
| `/mention` | @ 一个文件 | — |
| `/status` | 当前会话配置与 token 用量 | — |
| `/usage` | 看账号用量;`reset` 花一次存下的重置额度 | `[reset]` |
| `/title` | 配终端标题里显示哪些项 | — |
| `/statusline` | 配状态行里显示哪些项 | — |
| `/theme` | 选语法高亮主题 | — |
| `/pets` | 选或隐藏终端宠物 | — |
| `/mcp` | 列已配 MCP 工具;`verbose` 出详情 | `[verbose]` |
| `/logout` | 登出 Codex | — |
| `/exit` | 退出 Codex | — |
| `/feedback` | 把日志发给维护者 | — |
| `/ps` | 列后台终端 | — |
| `/stop` | 停掉所有后台终端 | — |
| `/clear` | 清屏并开新 chat | — |
| `/personality` | 选 Codex 的沟通风格 | — |
| `/subagents` | 切当前 agent thread | — |

---

## omp —— 顶层 61 条(多级命令,子级内联)

omp 是 pi 的分支(footer 仍写 `pi`),但命令集完全不同且**分两级**:`/goal set`、`/mcp add`、`/security scan` 这种。下表列顶层,子命令写在作用栏里。顶层/子级的切分来自二进制 strings 的分组顺序反推,只 `/goal` 一组做了回屏实测。

| 命令 | 作用(子命令) |
|---|---|
| `/goal` | 开关 goal 模式(持久自主目标):`set` 设/换目标、`pause`、`resume`、`drop`、`budget` 调 token 预算 |
| `/guided-goal` | 让 agent 先在聊天里访谈你,再配 goal 模式 |
| `/loop` | 开关 loop 模式:开着时下一条 prompt 每次 yield 后自动重投,Esc 取消本轮 |
| `/vibe` | 开关 vibe 模式(直连持久 fast/good worker 会话,只读工具集) |
| `/queue` | 排一条消息,等 agent yield 后再发 |
| `/switch` | 本会话换模型(等价 alt+p) |
| `/fast` | 切优先服务档(OpenAI `service_tier=priority` / Anthropic `speed=fast`):`on`、`off` |
| `/prewalk` | 下一次动作切到快而便宜的模型(不带 `--prewalk` 也能用) |
| `/advisor` | 开关顾问模型(每轮点评并注入笔记):`dump` 拷顾问 transcript、`configure` 开配置 TUI |
| `/vision` | 管本会话的 `inspect_image` 视觉代理:`auto` 跟随 `inspect_image.mode` |
| `/agents` | 打开 agents hub(逐 agent 配模型、prewalk、advisor) |
| `/force` | 强制下一轮使用指定工具 |
| `/security` | OMP 原生安全扫描:`plan`(不可变扫描计划)、`scan`、`status`、`cancel`、`scans`、`show`、`import`(SARIF/Codex bundle)、`export`、`validate`、`compare`(跨扫描追踪 finding 血缘)、`disposition` |
| `/plan-review` | 重开最近一份 plan 的评审(仅 plan 模式) |
| `/compact` | 手动压缩:`soft` 本地模型压(不走远端)、`remote` 走远端/provider 原生压缩 |
| `/snapcompact` | 把历史存成稠密位图让模型读回,**不发 LLM 调用** |
| `/shake` | 从 context 里抖掉重内容:`elide` 剥工具结果+大块(默认)、`images` 剥图片块 |
| `/clear` | 原地清空对话 context,保留会话(别名 `reset`) |
| `/fresh` | 重置 provider 流状态,不动本地 transcript |
| `/new` | 开新会话 |
| `/handoff` | 把会话上下文交接给新会话 |
| `/btw` | 借当前上下文问个临时侧问题 |
| `/tan` | 起一个完整后台 agent 干旁支活 |
| `/omfg` | 从一句抱怨锻出一条 TTSR 规则,止住反复出现的行为 |
| `/retry` | 重试上一轮失败的 agent turn |
| `/todo` | 看/改 agent 的 todo:`edit`($EDITOR Markdown 往返)、`append`、`start`、`done`、`rm` |
| `/memory` | 记忆维护:`stats`、`diagnose`、`enqueue` 排队整合(别名 `rebuild`) |
| `/share` | 分享会话:加密链接/gist;`collab` 经 relay 实时协作、`view` 只读链接、`stop`、`join`、`leave` |
| `/copy` | 从对话里挑文本或代码复制 |
| `/browser` | 切浏览器 headless/可见:`headless`、`visible` |
| `/ssh` | 管 SSH 主机:`add`、`list`、`remove` |
| `/live` | 起 Codex 驱动的实时语音模式 |
| `/sd` `/sg` `/git` | 查找替换 / AST-grep / 版本控制 |
| `/marketplace` | 插件市场:`update`、`discover`、`install`、`uninstall`、`installed`、`upgrade` |
| `/plugins` | 管已装插件:`enable`、`disable` |
| `/reload-plugins` | 重载全部插件(skill、命令、hook、工具、agent、MCP) |
| `/mcp` | 管 MCP:`add`/`list`/`remove`/`test`/`reauth`/`unauth`/`reconnect`/`reload`/`resources`/`prompts`/`notifications`、`smithery-search`/`-login`/`-logout` |
| `/session` | 会话管理:`info`、`delete`、`pin`(把 provider 钉到某个 OAuth 账号) |
| `/branch` `/fork` `/tree` | 从历史消息建分支 / fork / 会话树导航 |
| `/rename` `/move` | 重命名会话 / 把会话挪到别的目录 |
| `/add-dir` `/remove-dir` `/dirs` | 多根 workspace 目录的增 / 删 / 列 |
| `/jobs` | 看异步后台作业状态 |
| `/usage` | 看 provider 用量与限额 |
| `/context` | 看 context 用量拆解 |
| `/tools` | 看 agent 当前可见的工具 |
| `/settings` `/providers` | 设置菜单 / 配登录与 web 搜索 provider |
| `/login` `/logout` | OAuth 登录 / 登出 |
| `/help` `/hotkeys` `/changelog` | 帮助 / 快捷键 / changelog(`full` 出完整) |
| `/debug` | 打开 debug 工具选择器 |
| `/exit` | 退出 |

---

## 跨 harness 对照(同功能不同名)

| 功能 | Claude Code | Pi | Codex | omp |
|---|---|---|---|---|
| 设目标 | `/goal` | **无** | `/goal` | `/goal`(+`set`/`pause`/`resume`/`drop`/`budget`)、`/guided-goal` |
| 循环跑 | `/loop`(skill)、`/loops` 管 | **无** | **无** | `/loop` |
| 清空 context | `/clear` | `/new` | `/clear`、`/new` | `/clear`、`/new`、`/fresh` |
| 压缩 | `/compact`、`/autocompact` | `/compact` | `/compact` | `/compact soft\|remote`、`/snapcompact`、`/shake` |
| 换模型 | `/model` | `/model`、`/scoped-models` | `/model` | `/switch`、`/agents` |
| 推理档 | `/effort` | 随 `/model` 选 | `/model` 内选 | 随模型;`/prewalk` 降档 |
| 快速档 | `/fast` | **无** | `/fast` | `/fast on\|off` |
| 顾问模型 | `/advisor` | **无** | **无** | `/advisor`(+`dump`/`configure`) |
| 分支 / fork | `/branch`、`/fork` | `/fork`、`/clone`、`/tree` | `/fork`、`/resume` | `/branch`、`/fork`、`/tree` |
| 侧问 / 旁支 | `/btw`、`/subtask` | **无** | `/side` | `/btw`、`/tan` |
| 上下文用量 | `/context`、`/explain-usage`、`/usage`¹ | `/session` | `/status`、`/usage` | `/context`、`/usage` |

¹ **配额水位的无头读法**:`~/.claude/skills/fleet-commander/scripts/usage.sh`(`--json` 给脚本)——Keychain 取 Claude Code 的 OAuth token 打官方 `api.anthropic.com/api/oauth/usage`,与 /usage 面板同源(5h/周全模型/周 Fable 三池)。commander 管烧量节奏、守卫报水位都用它,别再往空闲席注 `/usage` 抄屏(2026-08-14 实测立)。token 只进内存,脚本任何分支不得打印它。
| MCP | `/mcp` | 走 `/settings` | `/mcp [verbose]` | `/mcp add\|list\|test\|…` |
| 权限 / 信任 | `/permissions` | `/trust` | `/permissions`、`/approve` | 走 `/settings` |
| 技能 | `/skills`、`/reload-skills`、`/skill-doctor` | 菜单里 `skill:<名>` | `/skills` | `/plugins`、`/reload-plugins` |
| Hook | `/hooks` | **无**(用 extension) | `/hooks` | **无**(用 plugin) |
| 代码审查 | `/code-review`(skill)、`/ultrareview` | `skill:code-review` | `/review` | `/security scan` |
| 后台作业 | `/tasks`、`/background`、`/workflows` | **无** | `/ps`、`/stop` | `/jobs`、`/tan` |
| 快捷键 | `/keybindings` | `/hotkeys` | `/keymap` | `/hotkeys` |
| 退出 | `/exit`(别名 `quit`) | `/quit` | `/exit` | `/exit` |
| 初始化上下文文件 | `/init` → CLAUDE.md | **无** | `/init` → AGENTS.md | **无** |

## herdr(无 slash,CLI 动词对照)

`herdr <名词> <动词>`,全部走 socket API、输出 JSON:`workspace` / `tab` / `pane` / `agent`(各有 list get create focus rename close)、`worktree`、`session`、`notification`、`integration`、`config`、`channel`、`api`、`server`。指挥常用的三条读屏面:`pane read <pane_id> [--lines N] [--source visible|recent|recent-unwrapped|detection] [--format text|ansi]`、`pane process-info --pane <pane_id>`、`agent list`。写通道:`pane send-text` / `pane send-keys`(对没起 agent 的裸 TUI 也有效)、`agent prompt <pane> '<文本>' --wait --until working`。

**注入 slash 就是指挥手段**:slash 只是 prompt 文本,`herdr agent prompt <pane> '/goal …'` 能给 worker 设目标、`'/loop 15m …'` 能给它上循环,也能对自己发。两个坑见 `HERDR-WORKERS.md` §注入 slash 命令(绕过 job 文件就绕过了 Session Init 抑制句;`--wait --until working` 对已在 working 的席位必超时,那不等于没送达)。

## 驱动裸 TUI 抄菜单的三个坑(本次实测)

1. **`pane send-keys` 会丢键。** 一次连发 18 个 `down` 实际只走了约一半;要单键发 + `sleep 0.15`,并且**用画面内容而不是按键次数**判断是否到底(连发 60 个 `down` 仍停在列表中段)。
2. **`pagedown` 在 Claude Code 的 `/help` 命令列表里完全无效**——连按 6 次画面零位移,只有 `down` 会动。菜单类 UI 别假设翻页键存在。
3. **`esc` 只关补全菜单,不清输入框。** 输入框里残留的 `/a` 让接着送的 `/help` 变成 `/a/help`,被当普通 prompt 发给模型,白烧了 30k context。清输入用 `ctrl+u`,清完再打下一条。
