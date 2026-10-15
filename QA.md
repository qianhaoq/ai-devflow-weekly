# QA 验收单 / QA Sign-off Checklist

> 用法 / Usage: 复制本模板到 PR 描述或 issue，逐项勾选后，在**最新 head commit** 上完成验证，
> 再给 PR 打 `qa-passed` 标签。新的 push 会自动移除该标签，必须重新走一遍本单。
> Copy this template into the PR description or an issue, check every item
> against the **latest head commit**, then apply the `qa-passed` label.
> Any new push removes the label automatically — redo this checklist.

PR: #___
被验收的 head commit / Verified head commit: `<COMMIT_SHA>`
验收人 / Reviewer: @___
日期 / Date: ___

## 测试点 / Test Points

- [ ] 核心用户路径可用 / Main user path works end to end
- [ ] 本 PR 变更的行为按预期生效 / Behavior changed in this PR matches expectations
- [ ] 回归：相邻功能未被破坏 / Regression: adjacent features unbroken
- [ ] 错误与边界情况（空输入、无效输入、网络失败）/ Errors and edge cases (empty input, invalid input, network failure)
- [ ] 权限与可见性正确 / Permissions and visibility are correct
- [ ] 移动端 / 小屏表现正常（如适用）/ Mobile or narrow viewport looks right (if applicable)
- [ ] 控制台无新增错误、警告 / No new console errors or warnings

## 黄金样例 / Golden Samples

> 用真实输入/输出对固定行为，防止悄悄漂移。
> Use real input/output pairs to pin behavior against silent drift.

| # | 场景 Scenario | 输入 Input | 期望输出 Expected output | 实际 Actual | 通过 Pass |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  | ☐ |
| 2 |  |  |  |  | ☐ |
| 3 |  |  |  |  | ☐ |

## 回滚命令 / Rollback Command

> 上线出问题时第一时间执行的命令（部署回退、功能开关、数据修复）。
> The first command to run when the release goes wrong (deploy revert,
> feature flag, data repair).

```bash
# GitHub Pages 回滚：revert 出问题的合并提交，经门禁合入 main，再手动重跑 pages.yml
PR=<出问题的PR号>
BAD_SHA=$(gh pr view "$PR" --repo qianhaoq/ai-devflow-weekly --json mergeCommit -q .mergeCommit.oid)
git fetch origin main && git switch -c "revert/pr-$PR" origin/main
git revert --no-edit "$BAD_SHA"            # squash merge = 单父提交；若为 merge commit 加 -m 1
git push -u origin HEAD
gh pr create --repo qianhaoq/ai-devflow-weekly --base main --fill --title "revert: PR #$PR"
# revert PR 合入后（bot 合并不触发 push）重新部署并确认：
gh workflow run pages.yml --repo qianhaoq/ai-devflow-weekly --ref main
gh run watch --repo qianhaoq/ai-devflow-weekly "$(gh run list --repo qianhaoq/ai-devflow-weekly --workflow pages.yml -L1 --json databaseId -q '.[0].databaseId')"
```

## 签署 / Sign-off

- [ ] 我在上述 head commit 上完成了全部测试点与黄金样例 / I verified all test points and golden samples on the head commit above
- [ ] 回滚命令已演练或在预发验证过 / The rollback command was rehearsed or verified in staging
- [ ] 现在给 PR 打 `qa-passed` 标签 / Apply the `qa-passed` label to the PR now

> 注意 / Note: 打标签时间必须晚于最后一次 push —— 否则 QA Gate 会以
> "label predates the latest push" 拒绝。push 新提交后标签被自动移除，
> 需重新验收并再次打标。
> The label must be applied AFTER the last push — otherwise the QA Gate
> rejects with "label predates the latest push". A new push removes the
> label; re-verify and re-apply it.
