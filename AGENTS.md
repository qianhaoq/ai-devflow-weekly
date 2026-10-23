# AGENTS.md — 贡献者与 AI 代理协作规则

## 数据规则

- **官方域名**：条目 `source_url` 必须命中 `sources.yml` 中某源的
  `official_domain`（host 相同或为其子域；形如 `github.com/anthropics` 的声明
  还要求路径以 `/anthropics` 开头）。`github.com` 链接只认 `sources.yml` 中官方源的
  `/org/repo` 路径（含 `official_github_repos` 迁移别名），其他仓库一律非官方。媒体报道、社交帖子只能作线索，不能作依据。
- **verified 语义**：`verified=true` 只能由编辑审核后人工设置；`draft.py` 起草的条目一律 `verified=false`，`source_url` 必须属于已启用的官方
  源。来源失效（404 / 403 / feed 为空）时把该源 `verified` 置 false（跳过），
  复测通过后再恢复。`verified=false` 的条目一律不进周刊。
- **定价快照**：`category=pricing` 必须带 `price_snapshot`（plan / price /
  currency / billing_period / captured_at）。涨/降价结论必须有同 vendor+plan
  前后两次快照对比；价格与币种不变、仅月付/年付等计费周期变化时，只能标记
  「计费周期变化」，不算涨价或降价（`validate.py` 输出 WARNING）。
- **beta/预览**：标题或摘要中出现 beta / preview / 预览的功能必须标注。

## 评审规则

- **P0 / P1 必须在合并前修复**；**P2 可选**，不阻塞合并。
  - P0：数据损坏或丢失、官方域名校验失效、密钥泄漏、CI / 工作流红灯。
  - P1：Schema 或校验逻辑缺陷、未核实内容混入周刊、定价结论缺少快照对比、
    条目路径或 id 规则被破坏。
  - P2：文案与措辞、站点样式、重构与性能建议、测试补充。
- 评审时按上述分级标注（如 `P1：...`），不满足 P0/P1 清零的 PR 不得合并。

## 其他约定

- `sources.yml` 与 `docs/editorial.md` 是人工维护的口径文件：不要自动改写
  已核实源的 `url` / `official_domain` / `verified`，如需变更先在 PR 里说明理由。
- 脚本保持可独立运行（`python scripts/xxx.py`），公共逻辑放进
  `scripts/common.py`；`validate.py` 的 `validate_item` / `is_billing_switch`
  供测试复用，改名需同步 `tests/`。
- 提交前本地自检：`pip install -r requirements.txt -q && python scripts/validate.py && pytest -q`。
- 新增源时补 `tests/` 覆盖新的域名校验逻辑；`category: test` 暂无源属正常。

## MERGE_GATES（合并门禁）

普通内容 PR 由 bot 合并；每日 crawl PR 只在 `editorial / QA Gate` 绿色后人工合并（`editorial-approved` 仅白名单用户打标有效），前提：CI `ci / Build & Test` 绿色 + review 完成 + 无未解决 P0/P1（P2 可选）+ editorial agent 批准。每日 crawl PR 始终带 `no-auto-merge` 标签——合并是编辑签字后的有意步骤，不自动合并。详见 [docs/MERGE_GATES.md](docs/MERGE_GATES.md)，内容口径见 [docs/editorial.md](docs/editorial.md)。

每日 crawl PR 须用仓库 secret `CRAWL_PR_TOKEN`（PAT）开/更新；默认 `GITHUB_TOKEN` 开的 PR 不触发门禁。仍须带 `no-auto-merge`，禁止自动合并。

## Coding 工具顺序（2026-10-20 起）

**适用范围（写死）**：下列 Codex / `coding` / `/home/box/.../codex-quota.sh` 顺序**仅**适用于已预装这些工具的**本机或 `/home/box` 工作站**。Copilot cloud、仅 Node·npm 的云端 agent、以及任何未预装 Codex/`coding` 的环境：**必须按该环境已有工具执行**；**严禁**把本机/box 工具序、`codex`/`coding` 或 `/home/box` 路径当作云端硬性要求。

1. **（本机/box）默认用 Codex CLI**（ChatGPT 账号登录），模型 `gpt-6.1-sol`（`~/.codex/config.toml`）。
2. **周额度用完后继续用 credits** 跑 Codex；**credits 也用完**再切：`coding glm`（一般代码）/ `coding kimi`（前端/交互/UI）。
3. 查额度（仅本机/box）：`/home/box/.coding-plans/codex-quota.sh`（退出码 0=继续 Codex，1=切 glm/kimi，2=未知；`--json`、`--probe`），或 Codex TUI 内 `/status`。云端无此脚本时跳过。
4. 凭证 `~/.codex/auth.json` 及任何 API key **绝不打印、外传或提交**；`.codex/`、`auth.json` 已在 `.gitignore`。

## 测试与门禁（禁止弱化凑绿）

- **禁止**为过 CI / Gate 而弱化、删改断言，或用 `skip` / `xit` / `.only`、改 fixture、放宽阈值等方式凑绿；也禁止让测试迁就错误实现。
- 红灯时优先修产品代码，或按真实意图**加强**测试；若断言本身写错，须在 PR 写明「原断言为何错、新断言覆盖什么」再改测试。
- AI 同时写代码与测试时，须用独立评审（Codex Gate / 人工）或既有回归交叉验证，勿代码与测试互相迁就。


## PR 证据与自动修上限（2026-10-20）

- **不要求人类 approve**；Gate 仍只挡 **P0/P1（及未标注）**（纯 P2 不挡）。
- **PR 必须贴证据**：正文写清「跑了什么测试 + 关键输出」（命令与摘要即可）；口头 done / 只勾 checkbox 不算。
- **同类 P1 自动修超 3 轮仍未清（写死）**：三轮上限**只**停止自动修循环（不得继续盲推）。**未 Resolve 的 P1 永远挡合入**——重试次数不改变严重度、不降级门禁。交给人/产品开跟进 issue/PR 继续修。**严禁**因重试次数把 P1 标成 observe、won't-fix、或 Resolve 后放行合入。

