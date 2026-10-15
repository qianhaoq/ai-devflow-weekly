# Copilot 协作指引（简版）

## 评审分级

- **P0 / P1 必须在合并前修复；P2 可选，不阻塞合并。**
  - P0：数据损坏、官方域名校验失效、密钥泄漏、CI/工作流红灯。
  - P1：Schema 或校验逻辑缺陷、未核实（verified=false）内容进入周刊、定价结论缺少快照对比。
  - P2：文案、样式、重构、性能与测试建议。

## 数据红线

- `source_url` 仅允许官方域名：命中 `sources.yml` 的 `official_domain`
  （host 或其子域；`github.com/<org>` 形式还要求路径前缀匹配）；GitHub releases 链接视为官方。
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
Content PRs are merged by the bot only after: `Build & Test` green, review done, no unresolved P0/P1 (P2 optional), editorial agent approved. Crawl PRs keep the `no-auto-merge` label. See docs/MERGE_GATES.md and docs/editorial.md.
