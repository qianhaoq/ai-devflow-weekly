# Copilot 协作指引（简版）

## 评审分级

- **P0 / P1 必须在合并前修复；P2 可选，不阻塞合并。**
  - P0：数据损坏、官方域名校验失效、密钥泄漏、CI/工作流红灯。
  - P1：Schema 或校验逻辑缺陷、未核实（verified=false）内容进入周刊、定价结论缺少快照对比。
  - P2：文案、样式、重构、性能与测试建议。

## 数据红线

- `source_url` 仅允许官方域名：命中 `sources.yml` 的 `official_domain`
  （host 或其子域；`github.com/<org>` 形式还要求路径前缀匹配）；`github.com` 只认 sources.yml 中官方源的 `/org/repo` 路径（含 `official_github_repos`），其他仓库与 www.github.com 等非规范 host 一律非官方。
- `category=pricing` 必须带 `price_snapshot`；涨/降价必须有同 vendor+plan 前后快照对比；
  仅月付/年付等计费周期变化只算「计费周期变化」，不算涨价或降价。
- `verified=false` 的条目不得进入周刊；beta / preview / 预览 必须标注。

## 提交前自检

```bash
pip install -r requirements.txt -q
python scripts/validate.py
pytest -q
```

不要自动改写 `sources.yml` 与 `docs/editorial.md` 的口径；如确需变更，在 PR 中说明理由。

## Merge gates
All PRs including crawl default to squash auto-merge once `ci / Build & Test`, `ci / Secret Scan`, `codex / Codex Review Gate`, and `qa / QA Gate` (`qa-passed`) are green, review is complete, and P0/P1 are cleared (P2 optional). Enable squash auto-merge on crawl/agent PRs. Crawl no longer defaults to `no-auto-merge` or manual merge; manually applying the label opts out. `editorial-approved` (allowlisted labelers only) / `editorial / QA Gate` are observation/optional sign-off only, outside auto-merge required checks. Use `CRAWL_PR_TOKEN` (PAT) to open/update crawl PRs so gates fire. The repository has `allow_auto_merge` enabled; branch protection/rules are managed by the supervisor, never agents. See docs/MERGE_GATES.md and docs/editorial.md.
