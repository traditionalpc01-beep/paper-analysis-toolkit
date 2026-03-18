# AI 模型影响因子获取说明

> 状态说明：当前仓库中的这条路径是“实验性补充方案”。本文只描述 `paperinsight/web/ai_model_if_fetcher.py` 与 `paperinsight/core/pipeline.py` 里已经实现、且可以直接核查的逻辑。

## 1. 先说结论

当前实现不是浏览器自动化方案，也不是 Playwright 驱动网页对话框的方案。

当前真实代码路径是：

1. 如果没有期刊名，先用 Crossref 根据论文标题补推期刊名
2. 如果还是没有期刊名，再用一组标题关键词做简单推断
3. 先查本地硬编码 `JournalIFCache`
4. 再查 LetPub 搜索页
5. 再用通义千问 API 兜底
6. 最后用 Kimi API 兜底

补充：`XMOLFetcher` 类虽然存在，但当前 `AIModelImpactFactorFetcher.lookup()` 没有实际调用它。

## 2. 当前启用条件

`AnalysisPipeline` 只有在下面两个条件同时成立时，才会优先走这条路径：

```yaml
web_search:
  enabled: true
  use_ai_model_if: true
  ai_model_if:
    enabled: true
```

最小可用示例：

```yaml
web_search:
  enabled: true
  timeout: 30
  use_ai_model_if: true
  ai_model_if:
    enabled: true
    timeout: 60
    qianwen_api_key: ""
    kimi_api_key: ""
```

注意：

- 这些键现在已经包含在 `paperinsight/utils/config.py::DEFAULT_CONFIG` 中，但默认都是关闭态。
- `config/config.example.yaml` 与运行时默认结构保持一致。

## 3. 当前模块的真实依赖

### 代码里确实用到的依赖

- `requests`
- `bs4.BeautifulSoup`

当前 `requirements.txt` 与 `pyproject.toml` 已包含 `beautifulsoup4`。如果你是通过 `pip install -r requirements.txt` 或 `pip install -e .` 安装，通常不需要单独补装。

### 代码里没有用到的浏览器自动化

- `requirements.txt` 当前列出了 `playwright`
- 但 `paperinsight/web/ai_model_if_fetcher.py` 当前并没有导入或调用 Playwright
- 因此本文不再把“浏览器自动化查询”写成既成事实

## 4. 当前查询顺序细化

### 4.1 期刊名补推

如果传入 `journal_name` 为空：

- 先调用 `CrossrefFetcher.lookup_journal_by_title(paper_title)`
- 若仍为空，再调用 `_infer_journal_from_title()` 的关键词映射

### 4.2 本地缓存

`JournalIFCache` 内置了一小批常见期刊 IF，用于极快回填。它不是官方数据源，也不会自动更新。

### 4.3 LetPub 抓取

`LetPubFetcher` 会访问 LetPub 搜索页，尝试从表格或整页文本里提取数值型 IF。

### 4.4 通义千问 / Kimi API 兜底

- `QianwenAPIFetcher` 使用 DashScope 文本生成接口
- `KimiAPIFetcher` 使用 Moonshot chat completions 接口
- 两者都通过“只返回影响因子数值”的提示词让模型回答，再用正则提取数值

## 5. 当前局限

- LetPub 页面结构变化会直接影响解析结果。
- `JournalIFCache` 是硬编码缓存，不是实时数据。
- 通义千问 / Kimi 返回的只是模型回答，仍然需要人工抽样复核。
- `XMOLFetcher` 目前只是占位实现，不应视为已经落地的有效数据源。

## 6. 更稳妥的使用建议

建议顺序：

1. 先让默认 IF 补全链路工作（MJL / 搜索回退 / WOS）
2. 只在常规链路无法补全时，再手工开启 `use_ai_model_if`
3. 对 AI 路径补到的结果做抽样复核

## 可核查来源

### 仓库内

- `paperinsight/core/pipeline.py`
- `paperinsight/utils/config.py`
- `config/config.example.yaml`
- `paperinsight/web/ai_model_if_fetcher.py`
- `requirements.txt`

### 外部官方文档

- Crossref REST API：<https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
- 阿里云 DashScope OpenAI 兼容调用：<https://help.aliyun.com/zh/model-studio/developer-reference/compatibility-of-openai-with-dashscope>
- Moonshot AI Kimi API 快速开始：<https://platform.moonshot.cn/blog/posts/kimi-api-quick-start-guide>
- LetPub 首页：<https://www.letpub.com.cn/>
