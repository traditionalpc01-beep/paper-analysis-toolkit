"""
Prompt 模板模块

v3.0 重构：
- 更新为嵌套式 JSON Schema
- 支持多器件数据提取
- 强制要求数据溯源引用
"""

import json
from typing import Dict, Any, Optional

# v3.0 论文信息提取 Prompt（嵌套式 JSON Schema）
EXTRACTION_PROMPT_V3 = """你是一个学术论文数据提取专家。请从以下论文 Markdown 文本中提取结构化数据。

## 提取要求

### 1. 论文基本信息 (paper_info)
- title: 论文标题
- authors: 作者列表，逗号分隔
- journal_name: 期刊名称
- impact_factor: 影响因子（从论文首页或页眉提取，若无则为 null）
- year: 发表年份
- optimization_strategy: 主要优化策略的一句话总结
- best_eqe: 论文报道的最高 EQE 值
- research_type: 研究类型（如 OLED, PLED, QLED, PeLED）
- emitter_type: 发光材料类型（如 TADF, Phosphorescent, Fluorescent）

### 2. 器件数据 (devices) - 重要：支持多器件
每个器件包含完整的性能参数，确保数据不跨器件错位：
- device_label: 器件标签（如 "Control", "Champion", "Device A"）
- structure: 完整器件结构（如 "ITO/PEDOT:PSS/EML/TPBi/LiF/Al"）
- eqe: 外量子效率（如 "22.5%" 或 "18.2% (max)"）
- cie: CIE 色坐标（如 "(0.21, 0.32)"）
- lifetime: 器件寿命（如 "150 h @ 1000 cd/m²" 或 "LT50 = 200 h"）
- luminance: 亮度数据
- current_efficiency: 电流效率
- power_efficiency: 功率效率
- notes: 其他重要信息

### 3. 数据溯源 (data_source) - 必须填写
为每个关键参数提供原文引用句子，确保数据可追溯：
- eqe_source: EQE 数据的原文句子
- cie_source: CIE 数据的原文句子
- lifetime_source: 寿命数据的原文句子
- structure_source: 器件结构的原文句子

### 4. 优化详情 (optimization)
- level: 优化层面（如 "材料合成、界面工程、器件结构"）
- strategy: 具体优化策略描述
- key_findings: 关键发现或创新点

## 输出格式

请严格按照以下 JSON Schema 输出，不要添加任何额外说明：

```json
{schema}
```

## 重要规则

1. **多器件处理**：如果论文包含多个器件，每个器件的数据必须独立成一个完整的对象，不要将不同器件的参数混在一起
2. **数据完整性**：每个器件的 EQE、CIE、寿命等参数必须来自同一个器件，不要张冠李戴
3. **数据溯源**：每个数值都必须附上原文出处，确保可验证
4. **空值处理**：如果某字段无法提取，使用 null 而非空字符串
5. **单位保留**：保留原始单位，如 "%"、"h"、"cd/m²"

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出，不要添加任何额外说明。
"""

# 期刊名称识别 Prompt
JOURNAL_EXTRACTION_PROMPT = """请从以下论文首页文本中识别期刊名称。

## 输出格式

```json
{{
  "journal_name": "期刊名称"
}}
```

## 论文首页文本

{paper_text}

请严格按照 JSON 格式输出。
"""

# 优化策略总结 Prompt
OPTIMIZATION_SUMMARY_PROMPT = """请从以下论文文本中总结优化方法和策略。

## 要求

1. 识别论文中提到的所有优化层级（如：材料合成、表面处理、配体工程、器件结构、工艺优化等）
2. 总结具体的优化策略（控制在300字左右）
3. 提炼关键发现或创新点

## 输出格式

```json
{{
  "level": "优化层级1、优化层级2、优化层级3",
  "strategy": "具体优化策略的简要描述...",
  "key_findings": "关键发现或创新点..."
}}
```

## 论文文本

{paper_text}

请严格按照 JSON 格式输出。
"""


def format_extraction_prompt_v3(
    paper_text: str,
    schema: Optional[Dict[str, Any]] = None,
) -> str:
    """
    格式化 v3.0 论文提取 Prompt

    Args:
        paper_text: 论文 Markdown 文本
        schema: JSON Schema（可选，使用默认 schema）

    Returns:
        格式化后的 Prompt
    """
    from paperinsight.models.schemas import PAPER_DATA_JSON_SCHEMA

    schema_str = json.dumps(schema or PAPER_DATA_JSON_SCHEMA, indent=2, ensure_ascii=False)
    return EXTRACTION_PROMPT_V3.format(
        paper_text=paper_text,
        schema=schema_str,
    )


def format_extraction_prompt(paper_text: str) -> str:
    """
    格式化论文提取 Prompt（兼容旧版）

    Args:
        paper_text: 论文文本

    Returns:
        格式化后的 Prompt
    """
    return format_extraction_prompt_v3(paper_text)


def format_journal_prompt(front_text: str) -> str:
    """
    格式化期刊识别 Prompt

    Args:
        front_text: 首页文本

    Returns:
        格式化后的 Prompt
    """
    return JOURNAL_EXTRACTION_PROMPT.format(paper_text=front_text)


def format_optimization_prompt(paper_text: str) -> str:
    """
    格式化优化策略 Prompt

    Args:
        paper_text: 论文文本

    Returns:
        格式化后的 Prompt
    """
    return OPTIMIZATION_SUMMARY_PROMPT.format(paper_text=paper_text)


def build_custom_prompt(
    paper_text: str,
    extraction_fields: Dict[str, str],
    output_schema: Dict[str, Any],
) -> str:
    """
    构建自定义提取 Prompt

    Args:
        paper_text: 论文文本
        extraction_fields: 提取字段及其描述
        output_schema: 输出 JSON Schema

    Returns:
        格式化后的 Prompt
    """
    # 构建字段说明
    field_descriptions = []
    for field_name, description in extraction_fields.items():
        field_descriptions.append(f"- {field_name}: {description}")

    fields_text = "\n".join(field_descriptions)
    schema_text = json.dumps(output_schema, indent=2, ensure_ascii=False)

    prompt = f"""请从以下论文文本中提取信息。

## 提取字段

{fields_text}

## 输出格式

请严格按照以下 JSON Schema 输出：

```json
{schema_text}
```

## 论文文本

{paper_text}

请严格按照 JSON 格式输出，不要添加任何额外说明。
"""
    return prompt
