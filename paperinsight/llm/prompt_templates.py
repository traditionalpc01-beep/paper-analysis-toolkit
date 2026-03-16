"""
Prompt 模板模块
功能: 定义论文信息提取的 Prompt 模板
"""

# 论文信息提取 Prompt
EXTRACTION_PROMPT = """你是一个学术论文信息提取专家。请从以下论文文本中提取关键信息,以 JSON 格式输出。

## 提取字段说明

1. **期刊名称**: 从首页或页眉页脚提取期刊名
2. **影响因子 (IF)**: 优先从论文首页、页眉页脚或文中显式提到的 impact factor / IF 信息中提取; 如果没有则输出 0
3. **论文标题**: 识别第一页最大字号文本
4. **作者**: 识别署名,列出所有作者名字,格式如 "张三, 李四, 王五, 张六, 李七"
5. **器件结构**: 识别层级堆叠结构,如 ITO/PEDOT:PSS/EML/ZnO/Al
6. **实验参数**: 
   - EQE(外量子效率): 提取所有器件的数值,多个数值以换行符分隔
   - CIE(色度坐标): 提取所有器件的坐标,格式如 (0.21, 0.32),多个以换行符分隔
   - 寿命(T50/LT50): 提取所有器件的寿命数值和单位,多个以换行符分隔
7. **数据溯源**: 提取数值时,附带原文出处句子
8. **优化层级和策略**: 总结论文中的优化方法,包括优化层级和具体策略,约100字

## 输出格式要求

请严格按照以下 JSON 格式输出,不要添加任何额外说明:

```json
{{
  "journal_name": "期刊名称",
  "影响因子": 0,
  "title": "论文标题",
  "authors": "作者1, 作者2, 作者3",
  "device_structure": "ITO/PEDOT:PSS/EML/ZnO/Al",
  "experimental_params": {{
    "eqe": ["20.5%", "18.3%"],
    "cie": ["(0.21, 0.32)", "(0.25, 0.35)"],
    "lifetime": ["150 h", "120 h"]
  }},
  "data_source": {{
    "eqe_source": "原文句子: ...max EQE of 20.5%...",
    "cie_source": "原文句子: ...CIE coordinates of (0.21, 0.32)...",
    "lifetime_source": "原文句子: ...T50 of 150 h..."
  }},
  "optimization": {{
    "level": "材料合成、表面处理、配体工程",
    "strategy": "采用核壳结构设计,通过表面配体工程优化界面性能,实现了高效率和高稳定性的发光器件。"
  }}
}}
```

## 重要说明

1. 如果某字段无法从文本中提取,请设为空字符串 ""、空数组 [] 或数值 0
2. 多个器件的参数值必须分别列出,不要合并
3. 数据溯源字段要包含原文中的完整句子
4. 优化策略描述要简洁,控制在300字左右

## 论文文本

{paper_text}

请严格按照 JSON 格式输出,不要添加任何额外说明。
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

1. 识别论文中提到的所有优化层级(如:材料合成、表面处理、配体工程、器件结构、工艺优化等)
2. 总结具体的优化策略(控制在300字左右)

## 输出格式

```json
{{
  "level": "优化层级1、优化层级2、优化层级3",
  "strategy": "具体优化策略的简要描述..."
}}
```

## 论文文本

{paper_text}

请严格按照 JSON 格式输出。
"""


def format_extraction_prompt(paper_text: str) -> str:
    """
    格式化论文提取 Prompt
    
    Args:
        paper_text: 论文文本
    
    Returns:
        格式化后的 Prompt
    """
    return EXTRACTION_PROMPT.format(paper_text=paper_text)


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
