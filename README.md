# AI DevFlow Weekly

中文 AI 研发工作流新闻聚合器：每日定时抓取 Cursor、GitHub Copilot、Claude Code、
OpenAI Codex、Windsurf、通义灵码、智谱 GLM、豆包 MarsCode 等官方 changelog /
releases / 博客，生成结构化条目，用 LLM 起草中文摘要，经校验与人工核实后发布为
Jekyll 周刊站点。

**线上站点**：<https://qianhaoq.github.io/ai-devflow-weekly/>

## 目录结构

```
├── sources.yml              # 抓取源清单（官方一手来源；verified: false 的源跳过）
├── docs/editorial.md        # 编辑口径（官方源核实 / 定价快照 / 计费周期 / verified）
├── schema/item.schema.json  # 条目 JSON Schema（draft 2020-12）
├── data/
│   ├── items/YYYY/MM/<id>.json   # 条目；id = vendor-slug + '-' + sha1(source_url) 前 10 位
│   └── state/<vendor>.json       # page_diff 源的上次页面哈希
├── scripts/
│   ├── common.py            # 共享工具（sources / 条目读写 / id / 官方域名校验）
│   ├── fetch.py             # 抓取：rss / github_releases / page_diff（--limit 5 --since-days 30）
│   ├── draft.py             # LLM 中文摘要（仅依据官方原文）；AI 起草条目 verified 保持 false，待编辑审核
│   ├── validate.py          # schema + 唯一性 + 官方域名 + 路径 + 定价规则校验
│   ├── weekly.py            # 生成 _weekly/YYYY-Www.md（仅 verified 条目）
│   └── build_site_data.py   # 生成 _data/items.json 供 Jekyll 使用
├── _weekly/                 # Jekyll weekly 集合（周刊 Markdown）
├── _layouts/  index.html  _config.yml  Gemfile   # Jekyll 站点
├── tests/                   # pytest（校验与周刊逻辑）
└── .github/workflows/       # ci.yml / crawl.yml / pages.yml
```

## 日常流程

```bash
pip install -r requirements.txt

python scripts/fetch.py              # 抓取启用源（verified: false 的源跳过）
python scripts/draft.py              # 为 summary_zh 为空的条目生成中文摘要
python scripts/validate.py           # 全量校验；有错误时退出码 1
python scripts/weekly.py             # 生成当周 _weekly/YYYY-Www.md（--week 2026-W42 可指定）
python scripts/build_site_data.py    # 生成 _data/items.json
bundle exec jekyll serve             # 本地预览站点
```

## 环境变量 / Secrets

| 变量 | 用途 | 默认 |
| --- | --- | --- |
| `LLM_API_KEY` | DeepSeek API Key（OpenAI 兼容）；未设置时 `draft.py` 打印提示并退出 0（条目保持 `summary_zh=""`、`verified=false`） | 无 |
| `LLM_BASE_URL` | API Base URL | `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名 | `deepseek-flash`（默认值只定义在 `scripts/draft.py`） |
| `GITHUB_TOKEN` | `fetch.py` 调 GitHub releases API 提额（可选） | 无 |

GitHub Actions：`LLM_API_KEY` 配在 **Secrets**，`LLM_BASE_URL` / `LLM_MODEL` 配在
**Variables**。脚本不会打印 Key。

## 定价规则（重要）

- `category: pricing` 的条目**必须**带 `price_snapshot`（plan / price / currency /
  billing_period / captured_at，可选 note）。
- 判断「涨价 / 降价」必须对比同 vendor + plan 的**前后两次快照**，没有快照对比
  不得下结论（见 `docs/editorial.md`）。
- 价格与币种不变、仅月付/年付等**计费周期**变化时，只算「计费周期变化」，
  不算涨价或降价；`validate.py` 对此输出
  `WARNING: billing switch, not a price increase`（不视为错误）。

## 校验规则

`python scripts/validate.py` 检查：Schema（含 pricing 必须带快照）、`id` 与
`source_url` 唯一、`source_url` 命中 `sources.yml` 中某源的 `official_domain`
（host 相同或为其子域；形如 `github.com/anthropics` 的声明要求路径前缀匹配；
`github.com` 仅限 sources.yml 中官方 `/org/repo` 路径）、文件路径与 `date`/`id` 一致。

## CI / CD

- `ci.yml`：PR 与 push main 时安装依赖 → `validate.py` → `pytest -q`。
- `crawl.yml`：每日 07:17（北京时间，cron `17 23 * * *`）抓取 → 摘要 → 校验 →
  生成周刊，并用 `peter-evans/create-pull-request@v7` 向 `crawl/auto` 分支开
  PR（标签 `no-auto-merge`，人工复核后合并）。
- `pages.yml`：push main 后生成 `_data/items.json` → Jekyll 构建 → 部署到
  GitHub Pages。

## 内容口径

见 [`docs/editorial.md`](docs/editorial.md)：只用官方源核实、价格变化需快照对比、
计费周期变化单独标注、`verified=false` 不进周刊、beta/预览须标注。

## 测试

```bash
pytest -q
```

## MERGE_GATES（合并门禁）

普通内容 PR 由 bot 合并；每日 crawl PR 只在 `editorial / QA Gate` 绿色后人工合并（`editorial-approved` 仅白名单用户打标有效），前提：CI `ci / Build & Test` 绿色 + review 完成 + 无未解决 P0/P1（P2 可选）+ editorial agent 批准。每日 crawl PR 始终带 `no-auto-merge` 标签——合并是编辑签字后的有意步骤，不自动合并。详见 [docs/MERGE_GATES.md](docs/MERGE_GATES.md)，内容口径见 [docs/editorial.md](docs/editorial.md)。
