# AGENTS.md — 贡献者与 AI 代理协作规则

## 数据规则

- **官方域名**：条目 `source_url` 必须命中 `sources.yml` 中某源的
  `official_domain`（host 相同或为其子域；形如 `github.com/anthropics` 的声明
  还要求路径以 `/anthropics` 开头）。GitHub releases 链接（`github.com`）一律
  视为官方。媒体报道、社交帖子只能作线索，不能作依据。
- **verified 语义**：`verified=true` 表示中文摘要已生成且 `source_url` 为官方
  域名。来源失效（404 / 403 / feed 为空）时把该源 `verified` 置 false（跳过），
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

内容 PR 由 bot 合并（不是用户手动合并），前提：CI `ci / Build & Test` 绿色 + review 完成 + 无未解决 P0/P1（P2 可选）+ editorial agent 批准。每日 crawl PR 始终带 `no-auto-merge` 标签——合并是编辑签字后的有意步骤，不自动合并。详见 [docs/MERGE_GATES.md](docs/MERGE_GATES.md)，内容口径见 [docs/editorial.md](docs/editorial.md)。
