# MERGE_GATES · 合并门禁

普通内容 PR 由 auto-merge bot 合并；每日 crawl PR（带 `no-auto-merge`）**只能人工合并，且须 `editorial / QA Gate` 为绿色之后**。合并前必须同时满足：

1. **CI 通过**：必需检查 `ci / Build & Test`（validate.py + pytest）为绿色。
2. **Review 完成**：代码/内容 review 已完成。
3. **无未解决的 P0/P1**：P0/P1 问题必须修复后才能合并；P2 为可选建议，不阻塞合并。
4. **编辑 agent 已批准**：editorial agent 已按 [editorial.md](editorial.md) 口径签字（官方源核实、价格快照对比、计费周期切换不算涨降价、verified 规则）。


## Check names after devflow-gates migration

本仓库的 CI / Codex / QA / Auto Merge 改为调用 `qianhaoq/devflow-gates` 的 reusable workflow（固定到 commit `fe7cf65`，即 fe7cf651ef515f165041738dc285b03ce3817bb9）。Check 名变为 `<caller job> / <called job>`，branch protection 与 `auto-merge.yml` 的 `required_checks` 必须使用以下名字：

- `ci / Build & Test`
- `ci / Secret Scan`
- `codex / Codex Review Gate`
- `qa / QA Gate`（label `qa-passed`，见 `QA.md`）
- `editorial / QA Gate`（label `editorial-approved`，editorial agent 签字；每次 push 自动摘除）

旧的裸名 `Build & Test` / `Codex Review Gate` 在合入后不再产生，若仍为 required 会让所有 PR 永久挂起。

Codex 线程分级（共享实现）：显式 P0/P1 阻断；未标注线程一律阻断（`block_unlabeled: true`，默认，fail-closed）；显式 P2（Codex、Copilot 或人工）不阻断；P2 可回复 `P2: defer — <理由>` 后 Resolve。线程 Resolve 不会触发 Actions：由每 15 分钟的 Gate Refresh 重跑，或 `workflow_dispatch` 填 PR 号。

## no-auto-merge 标签：crawl PR 人工合并

`crawl.yml` 创建的 PR 一律带 `no-auto-merge` 标签，auto-merge 永不合入它们。**crawl PR 只能人工合并**，且只能在 `editorial / QA Gate` 为绿色之后（同时其余必需检查也须为绿色）。保留此标签，不要移除。

## editorial-approved 只认白名单用户

`editorial / QA Gate` 调用 devflow-gates QA Gate 的 `allowed_labelers`：通过 issue events/timeline API 读取 `editorial-approved` 的 `labeled` 事件，只有 actor 在白名单内的那次打标才计入（默认 `qianhaoq`，可用仓库变量 `EDITORIAL_LABELERS` 逗号分隔覆盖）。只看该标签**最后一次** `labeled` 事件的 actor；之后若有 `unlabeled` 则视为未签字。变量设置了但解析不出任何用户（如 `" "`、`","`）时 gate 直接失败。其他人（包括 PR 作者本人，除非其在白名单内）打的标签不算签字，gate 保持红色；每次 push 标签仍会被摘除。

## Branch protection（#2 合入后启用）

#2 合入 main 之后再为 main 开启 branch protection（不在 #2 合入前开，以免旧检查名卡住 PR）：

- Require status checks to pass，且 **Require branches to be up to date（strict）**
- 必需检查：`ci / Build & Test`、`ci / Secret Scan`、`codex / Codex Review Gate`、`editorial / QA Gate`

## Acceptance Gate（M1，仅观察）

`.github/workflows/acceptance.yml` 调用 devflow-gates 的可复用验收门禁（固定到合并 SHA），配置在 `.github/acceptance.yml`。每个 PR 上会有一条置顶评论（原地更新）列出 7 项指标：测试与变更行覆盖率、改源码须改测试（`no-test-needed` 标签 + 正文写明理由可豁免）、ruff 新增问题、PR 规模（不计 `data/`、`_weekly/`）、新依赖漏洞/许可证、PR 正文的自测/验收小节、Codex 门禁结论；JSON 报告在 artifact `acceptance-report`。M1 只报告不拦截，`acceptance / Acceptance Gate` **不**加入 branch protection；它不加/不摘任何标签。crawl PR 由 `GITHUB_TOKEN` 创建，其 `pull_request` 运行同样需要人工批准，编辑打标签时会正常触发。

## 流程

crawl（每日 07:17 北京时间）→ 开 PR（`no-auto-merge`）→ CI `ci / Build & Test` → review（处理 P0/P1）→ editorial（白名单用户打 `editorial-approved`）→ `editorial / QA Gate` 绿色后人工合并 → `pages.yml` 部署站点与 feed.xml。

初始脚手架是唯一的直接推送 main 的例外。

Copilot review：auto-merge 默认要求当前 head 有 Copilot review。若仓库未启用 Copilot（请求返回 422）或不想用它，把仓库变量 `DISABLE_COPILOT_REVIEW` 设为 `true`，会同时关闭请求与合并要求。

crawl PR 的必需检查：crawl 用 `GITHUB_TOKEN` 创建/推送 PR，GitHub 不会为它正常运行 `pull_request` / `pull_request_target`（`pull_request` 运行停在 action_required 等待批准），`workflow_dispatch` 运行的检查也不计入 PR。因此 crawl PR 的检查由编辑的 `editorial-approved` 打标（人工事件）触发：`ci.yml` 监听 `labeled`，gate 监听 `pull_request_target` labeled。随后在 PR 上评论 `@codex review`（Codex 不会自动审 bot 开的 PR）；Codex 完成后，每 15 分钟的 Gate Refresh 会重跑失败的 `codex / Codex Review Gate`。`crawl.yml` 更新 PR 时仍会摘掉旧的 `qa-passed` / `editorial-approved`。

## 自动修上限（2026-10-20）

- Gate 仍只挡 **P0/P1（及未标注）**；**不要求人类 approve**。
- **同类 P1** 自动修复超过 **3 轮**仍未清零（写死）：三轮上限**只**停自动修循环。**未 Resolve 的 P1 永远挡合入**；重试次数不改变严重度。开跟进 issue/PR 交给人/产品继续修。**严禁**因重试次数 observe / won't-fix / Resolve 放行。禁止为凑绿弱化测试。
