# MERGE_GATES · 合并门禁

本仓默认自动合入；必需检查齐绿即合（含 crawl PR）。必需检查为 `ci / Build & Test`、`ci / Secret Scan`、`codex / Codex Review Gate`，且须无未解决 P0/P1；P2 不阻塞合并。勿等人卡、不必等钱浩再点。内容口径见 [editorial.md](editorial.md)。

## Check names after devflow-gates migration

本仓库的 CI / Codex / QA / Auto Merge 改为调用 `qianhaoq/devflow-gates` 的 reusable workflow（固定到 commit `fe7cf65`，即 fe7cf651ef515f165041738dc285b03ce3817bb9）。Check 名变为 `<caller job> / <called job>`，branch protection 与 `auto-merge.yml` 的 `required_checks` 必须使用以下名字：

- `ci / Build & Test`
- `ci / Secret Scan`
- `codex / Codex Review Gate`

`qa / QA Gate` 与 `editorial / QA Gate` 如仍运行仅为可选观察，不在 required_checks 或 branch protection、不挡合入。

旧的裸名 `Build & Test` / `Codex Review Gate` 在合入后不再产生，若仍为 required 会让所有 PR 永久挂起。

Codex 线程分级（共享实现）：显式 P0/P1 阻断；未标注线程一律阻断（`block_unlabeled: true`，默认，fail-closed）；显式 P2（Codex、Copilot 或人工）不阻断；P2 可回复 `P2: defer — <理由>` 后 Resolve。线程 Resolve 不会触发 Actions：由每 15 分钟的 Gate Refresh 重跑，或 `workflow_dispatch` 填 PR 号。

## editorial-approved 白名单（可选观察）

此签字与 Gate 仅为可选观察，不挡合入。

`editorial / QA Gate` 调用 devflow-gates QA Gate 的 `allowed_labelers`：通过 issue events/timeline API 读取 `editorial-approved` 的 `labeled` 事件，只有 actor 在白名单内的那次打标才计入（默认 `qianhaoq`，可用仓库变量 `EDITORIAL_LABELERS` 逗号分隔覆盖）。只看该标签**最后一次** `labeled` 事件的 actor；之后若有 `unlabeled` 则视为未签字。变量设置了但解析不出任何用户（如 `" "`、`","`）时 gate 直接失败。其他人（包括 PR 作者本人，除非其在白名单内）打的标签不算签字，gate 保持红色；每次 push 标签仍会被摘除。

## Branch protection

- Require status checks to pass，且 **Require branches to be up to date（strict）**
- 必需检查仅为：`ci / Build & Test`、`ci / Secret Scan`、`codex / Codex Review Gate`
- `required_approving_review_count` 等审批规则由主管维护（agent 不改 branch protection）
- qa / editorial 如仍运行仅为可选观察，不在 protection、不挡合入


## Acceptance Gate（M1，仅观察）

`.github/workflows/acceptance.yml` 调用 devflow-gates 的可复用验收门禁（固定到合并 SHA），配置在 `.github/acceptance.yml`。每个 PR 上会有一条置顶评论（原地更新）列出 7 项指标：测试与变更行覆盖率、改源码须改测试（`no-test-needed` 标签 + 正文写明理由可豁免）、ruff 新增问题、PR 规模（不计 `data/`、`_weekly/`）、新依赖漏洞/许可证、PR 正文的自测/验收小节、Codex 门禁结论；JSON 报告在 artifact `acceptance-report`。M1 只报告不拦截，`acceptance / Acceptance Gate` **不**加入 branch protection；它不加/不摘任何标签。crawl PR 现用仓库 secret `CRAWL_PR_TOKEN`（PAT）创建/推送，会正常触发 `pull_request` / `pull_request_target` 门禁。

## 流程

crawl（每日 07:17 北京时间）→ 开 PR（齐绿后自动合入，不打 `no-auto-merge`）→ 必需 CI/Codex 绿且无未解决 P0/P1 → squash 合入 → `pages.yml` 部署站点与 feed.xml。

初始脚手架是唯一的直接推送 main 的例外。

Copilot review：auto-merge 默认要求当前 head 有 Copilot review。若仓库未启用 Copilot（请求返回 422）或不想用它，把仓库变量 `DISABLE_COPILOT_REVIEW` 设为 `true`，会同时关闭请求与合并要求。

crawl PR 的必需检查：`crawl.yml` 使用仓库 secret `CRAWL_PR_TOKEN`（PAT）创建/推送 PR，正常触发 `pull_request` / `pull_request_target` 门禁；默认 `GITHUB_TOKEN` 开的 PR 不会正常触发这些门禁。更新 PR 时仍会摘掉旧的 `qa-passed` / `editorial-approved`，避免旧签字用于新 head；签字仅为可选观察，不挡合入。不再打 `no-auto-merge`，齐绿后自动合入。


## 自动修上限（2026-10-20）

- Gate 仍只挡 **P0/P1（及未标注）**；**不要求人类 approve**。
- **同类 P1** 自动修复超过 **3 轮**仍未清零（写死）：三轮上限**只**停自动修循环。**未 Resolve 的 P1 永远挡合入**；重试次数不改变严重度。开跟进 issue/PR 交给人/产品继续修。**严禁**因重试次数 observe / won't-fix / Resolve 放行。禁止为凑绿弱化测试。
