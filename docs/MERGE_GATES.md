# MERGE_GATES · 合并门禁

内容 PR（含每日 crawl PR）**由本仓库的 bot 合并，不由用户手动合并**。必须同时满足以下条件，bot 才会执行合并：

1. **CI 通过**：必需检查 `ci / Build & Test`（validate.py + pytest）为绿色。
2. **Review 完成**：代码/内容 review 已完成。
3. **无未解决的 P0/P1**：P0/P1 问题必须修复后才能合并；P2 为可选建议，不阻塞合并。
4. **编辑 agent 已批准**：editorial agent 已按 [editorial.md](editorial.md) 口径签字（官方源核实、价格快照对比、计费周期切换不算涨降价、verified 规则）。

## no-auto-merge 标签

`crawl.yml` 创建的 PR 一律带 `no-auto-merge` 标签：禁止任何自动合并机制直接合入。合并是编辑签字之后由 bot **有意识执行的一步**，而不是 CI 变绿即自动合并。保留此标签，不要移除。

## 流程

crawl（每日 07:17 北京时间）→ 开 PR（`no-auto-merge`）→ CI `ci / Build & Test` → review（处理 P0/P1）→ editorial agent 批准 → bot 合并 → `pages.yml` 部署站点与 feed.xml。

初始脚手架是唯一的直接推送 main 的例外。
