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
- optimization_strategy: 主要优化策略的一句话总结，使用“中文总结 | English summary”的中英对照形式
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
- notes: 其他重要信息，优先使用“中文说明 | English note”的中英对照形式

### 3. 数据溯源 (data_source) - 必须填写
为每个关键参数提供原文引用句子，确保数据可追溯：
- eqe_source: EQE 数据的原文句子
- cie_source: CIE 数据的原文句子
- lifetime_source: 寿命数据的原文句子
- structure_source: 器件结构的原文句子

### 4. 优化详情 (optimization)
- level: 优化层面（如 "材料合成、界面工程、器件结构"）
- strategy: 具体优化策略描述，使用“中文说明 | English summary”的中英对照形式
- key_findings: 关键发现或创新点，使用“中文要点 | English finding”的中英对照形式

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
6. **双语输出**：对于总结类文本字段（optimization_strategy、optimization.strategy、optimization.key_findings、notes），尽量输出中英对照，格式为“中文 | English”

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出，不要添加任何额外说明。
"""


BILINGUAL_POSTPROCESS_PROMPT = """你将收到一份已经提取好的论文结构化 JSON。请在不改变 JSON 结构、字段名、字段数量的前提下，对导出报表中从“论文标题”列开始向后的自然语言文本字段进行中英对照补全。

## 输出目标

1. 仅改写自然语言文本字段，输出格式固定为两行：
   第一行：`中文：...`
   第二行：`English: ...`
2. 如果原文是英文，第一行输出中文翻译，第二行保留原始英文
3. 如果原文是中文，第一行保留原始中文，第二行输出英文翻译
4. 如果字段已经是中英对照形式，统一改写为上述两行格式，保持原意但不要重复翻译
5. 如果字段为空、null、或无法可靠翻译，保留 null

## 必须处理中英对照的字段

- paper_info.title
- paper_info.optimization_strategy
- devices[].device_label（仅当其为自然语言标签时）
- devices[].notes
- data_source.eqe_source
- data_source.cie_source
- data_source.lifetime_source
- data_source.structure_source
- optimization.level
- optimization.strategy
- optimization.key_findings

## 必须保持原样的字段

- authors
- journal_name
- impact_factor
- year
- best_eqe
- devices[].structure
- devices[].eqe
- devices[].cie
- devices[].lifetime
- devices[].luminance
- devices[].current_efficiency
- devices[].power_efficiency
- 任何纯数字、百分比、单位值、公式、材料缩写、器件堆叠结构、坐标、文件路径、URL

## 重要规则

1. 不要删除任何字段，也不要新增解释性字段
2. 保持 JSON 可被直接解析
3. 不要把结构化数据改写成长段落
4. 对 data_source 中的原文引用，保留原句含义，输出为两行中英对照
5. 对技术缩写（如 OLED、EQE、CIE、TADF、ITO 等）在中英文两侧都保持原缩写

## 当前 JSON Schema

```json
{schema}
```

## 待处理 JSON

```json
{paper_json}
```

请严格输出处理后的 JSON，不要添加任何额外说明。
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


def format_bilingual_postprocess_prompt(
    paper_data: Dict[str, Any],
    schema: Optional[Dict[str, Any]] = None,
) -> str:
    """
    格式化中英对照后处理 Prompt

    Args:
        paper_data: 已提取的结构化论文数据
        schema: JSON Schema（可选，使用默认 schema）

    Returns:
        格式化后的 Prompt
    """
    from paperinsight.models.schemas import PAPER_DATA_JSON_SCHEMA

    schema_str = json.dumps(schema or PAPER_DATA_JSON_SCHEMA, indent=2, ensure_ascii=False)
    paper_json = json.dumps(paper_data, indent=2, ensure_ascii=False)
    return BILINGUAL_POSTPROCESS_PROMPT.format(
        schema=schema_str,
        paper_json=paper_json,
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
