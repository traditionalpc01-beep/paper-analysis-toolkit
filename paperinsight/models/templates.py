"""
提取模板配置模块

支持多种研究领域的配置化提取模板，包括：
- OLED/LED/QLED 器件
- 太阳能电池 (Perovskite Solar Cells)
- 锂电池 (Li-ion Battery)
- 传感器 (Sensors)
- 自定义模板

支持动态模板生成（通过 LLM）。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, ConfigDict


class TemplateType(str, Enum):
    """模板类型枚举"""
    OLED = "oled"
    SOLAR_CELL = "solar_cell"
    BATTERY = "battery"
    SENSOR = "sensor"
    CUSTOM = "custom"
    DYNAMIC = "dynamic"


@dataclass
class FieldDefinition:
    """字段定义"""
    name: str
    description: str
    field_type: str = "string"
    required: bool = False
    unit: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    extraction_hints: List[str] = field(default_factory=list)


@dataclass
class DeviceFieldConfig:
    """器件字段配置"""
    fields: List[FieldDefinition]
    multi_device_support: bool = True
    max_devices: int = 6


@dataclass
class PaperFieldConfig:
    """论文字段配置"""
    fields: List[FieldDefinition]


@dataclass
class DataSourceFieldConfig:
    """数据溯源字段配置"""
    enabled: bool = True
    fields: List[str] = field(default_factory=list)


@dataclass
class ExtractionTemplate:
    """
    提取模板配置
    
    包含完整的领域提取配置：
    - 模板基本信息
    - 器件字段定义
    - 论文字段定义
    - Prompt 模板
    - 正则提取模式
    """
    template_id: str
    template_name: str
    template_type: TemplateType
    description: str
    device_config: DeviceFieldConfig
    paper_config: PaperFieldConfig
    data_source_config: DataSourceFieldConfig
    prompt_template: str
    regex_patterns: Dict[str, List[str]] = field(default_factory=dict)
    optimization_keywords: Dict[str, List[str]] = field(default_factory=dict)
    research_type_keywords: Dict[str, List[str]] = field(default_factory=dict)
    
    def get_device_field_names(self) -> List[str]:
        """获取器件字段名称列表"""
        return [f.name for f in self.device_config.fields]
    
    def get_paper_field_names(self) -> List[str]:
        """获取论文字段名称列表"""
        return [f.name for f in self.paper_config.fields]
    
    def get_field_description(self, field_name: str) -> Optional[str]:
        """获取字段描述"""
        for f in self.device_config.fields:
            if f.name == field_name:
                return f.description
        for f in self.paper_config.fields:
            if f.name == field_name:
                return f.description
        return None
    
    def to_json_schema(self) -> Dict[str, Any]:
        """生成 JSON Schema"""
        device_properties = {}
        for f in self.device_config.fields:
            device_properties[f.name] = {"type": ["string", "null"]}
            if f.description:
                device_properties[f.name]["description"] = f.description
        
        paper_properties = {}
        for f in self.paper_config.fields:
            paper_properties[f.name] = {"type": ["string", "null"]}
            if f.field_type == "integer":
                paper_properties[f.name]["type"] = ["integer", "null"]
            elif f.field_type == "number":
                paper_properties[f.name]["type"] = ["number", "null"]
            if f.description:
                paper_properties[f.name]["description"] = f.description
        
        data_source_properties = {}
        if self.data_source_config.enabled:
            for field_name in self.data_source_config.fields:
                data_source_properties[field_name] = {"type": ["string", "null"]}
        
        return {
            "type": "object",
            "properties": {
                "paper_info": {
                    "type": "object",
                    "properties": paper_properties,
                    "required": []
                },
                "devices": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": device_properties,
                        "required": []
                    }
                },
                "data_source": {
                    "type": "object",
                    "properties": data_source_properties,
                    "required": []
                }
            },
            "required": ["paper_info", "devices", "data_source"]
        }


OLED_TEMPLATE = ExtractionTemplate(
    template_id="oled",
    template_name="OLED/LED/QLED 器件",
    template_type=TemplateType.OLED,
    description="有机发光二极管、聚合物发光二极管、量子点发光二极管论文提取模板",
    device_config=DeviceFieldConfig(
        fields=[
            FieldDefinition(
                name="device_label",
                description="器件标签，如 'Control', 'Champion', 'Device A' 等",
                extraction_hints=["champion device", "best device", "optimized device", "control device"]
            ),
            FieldDefinition(
                name="structure",
                description="完整的器件结构，如 'ITO/PEDOT:PSS/EML/TPBi/LiF/Al'",
                extraction_hints=["device structure", "architecture", "ITO", "layer structure"]
            ),
            FieldDefinition(
                name="eqe",
                description="外量子效率，如 '22.5%' 或 '18.2% (max)'",
                unit="%",
                aliases=["EQE", "external quantum efficiency"],
                extraction_hints=["EQE", "external quantum efficiency", "max EQE"]
            ),
            FieldDefinition(
                name="cie",
                description="CIE 色坐标，如 '(0.21, 0.32)'",
                aliases=["CIE", "color coordinates", "chromaticity"],
                extraction_hints=["CIE", "color coordinates", "chromaticity coordinates"]
            ),
            FieldDefinition(
                name="lifetime",
                description="器件寿命，如 '150 h @ 1000 cd/m²' 或 'LT50 = 200 h'",
                unit="h",
                aliases=["LT50", "T50", "operational lifetime"],
                extraction_hints=["LT50", "T50", "lifetime", "operational stability"]
            ),
            FieldDefinition(
                name="luminance",
                description="亮度数据，如 '5000 cd/m²'",
                unit="cd/m²",
                aliases=["brightness", "luminance"],
                extraction_hints=["luminance", "brightness", "cd/m²"]
            ),
            FieldDefinition(
                name="current_efficiency",
                description="电流效率，如 '68 cd/A'",
                unit="cd/A",
                aliases=["CE", "current efficiency"],
                extraction_hints=["current efficiency", "CE", "cd/A"]
            ),
            FieldDefinition(
                name="power_efficiency",
                description="功率效率，如 '45 lm/W'",
                unit="lm/W",
                aliases=["PE", "power efficiency"],
                extraction_hints=["power efficiency", "PE", "lm/W"]
            ),
            FieldDefinition(
                name="notes",
                description="其他重要备注或实验条件"
            ),
        ],
        multi_device_support=True,
        max_devices=6
    ),
    paper_config=PaperFieldConfig(
        fields=[
            FieldDefinition(name="title", description="论文标题"),
            FieldDefinition(name="authors", description="作者列表，逗号分隔"),
            FieldDefinition(name="journal_name", description="期刊名称"),
            FieldDefinition(name="raw_journal_title", description="期刊原始标题"),
            FieldDefinition(name="raw_issn", description="原始 print ISSN"),
            FieldDefinition(name="raw_eissn", description="原始 electronic ISSN"),
            FieldDefinition(name="matched_journal_title", description="期刊匹配后的标准标题"),
            FieldDefinition(name="matched_issn", description="期刊匹配后的标准 ISSN"),
            FieldDefinition(name="match_method", description="期刊匹配方式"),
            FieldDefinition(name="journal_profile_url", description="期刊主页 URL"),
            FieldDefinition(name="impact_factor", description="影响因子", field_type="number"),
            FieldDefinition(name="impact_factor_year", description="影响因子年份", field_type="integer"),
            FieldDefinition(name="impact_factor_source", description="影响因子来源"),
            FieldDefinition(name="impact_factor_status", description="影响因子获取状态"),
            FieldDefinition(name="year", description="发表年份", field_type="integer"),
            FieldDefinition(name="optimization_strategy", description="论文的主要优化策略总结"),
            FieldDefinition(name="best_eqe", description="论文报道的最高 EQE 值"),
            FieldDefinition(name="research_type", description="研究类型，如 'OLED', 'PLED', 'QLED', 'PeLED'"),
            FieldDefinition(name="emitter_type", description="发光材料类型，如 'TADF', 'Phosphorescent', 'Fluorescent'"),
        ]
    ),
    data_source_config=DataSourceFieldConfig(
        enabled=True,
        fields=["eqe_source", "cie_source", "lifetime_source", "structure_source"]
    ),
    prompt_template="""你是一个学术论文数据提取专家。请从以下论文 Markdown 文本中提取结构化数据。

## 提取要求

### 1. 论文基本信息 (paper_info)
- title: 论文标题
- authors: 作者列表，逗号分隔
- journal_name: 期刊名称
- impact_factor: 影响因子（从论文首页或页眉提取，若无则为 null）
- year: 发表年份
- optimization_strategy: 主要优化策略的一句话总结，使用"中文总结 | English summary"的中英对照形式
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
- notes: 其他重要信息，优先使用"中文说明 | English note"的中英对照形式

### 3. 数据溯源 (data_source) - 必须填写
为每个关键参数提供原文引用句子，确保数据可追溯：
- eqe_source: EQE 数据的原文句子
- cie_source: CIE 数据的原文句子
- lifetime_source: 寿命数据的原文句子
- structure_source: 器件结构的原文句子

### 4. 优化详情 (optimization)
- level: 优化层面（如 "材料合成、界面工程、器件结构"）
- strategy: 具体优化策略描述，使用"中文说明 | English summary"的中英对照形式
- key_findings: 关键发现或创新点，使用"中文要点 | English finding"的中英对照形式

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
6. **双语输出**：对于总结类文本字段，尽量输出中英对照，格式为"中文 | English"

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出，不要添加任何额外说明。
""",
    regex_patterns={
        "eqe": [
            r'EQE[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'external quantum efficiency[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'max(?:imum)?\s+EQE[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
        ],
        "cie": [
            r'CIE[^0-9]*?\(([0-9]?\.[0-9]+)\s*[,，]\s*([0-9]?\.[0-9]+)\)',
            r'\(([0-9]?\.[0-9]+)\s*[,，]\s*([0-9]?\.[0-9]+)\)[^)]*CIE',
        ],
        "lifetime": [
            r'T[⑤5]0[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hr|hrs|hour|hours)',
            r'LT[⑤5]0[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hr|hrs|hour|hours)',
            r'lifetime[^0-9]*?([0-9]+\.?[0-9]*)\s*(h|hour|hours)',
        ],
        "structure": [
            r'((?:ITO|Glass)\s*/\s*[A-Za-z0-9:+()._\-\s]{1,40}(?:\s*/\s*[A-Za-z0-9:+()._\-\s]{1,40}){2,8})',
        ],
    },
    optimization_keywords={
        "材料合成": ["synthesis", "material design", "precursor"],
        "核壳结构": ["core-shell", "core/shell", "shell growth"],
        "表面处理": ["surface treatment", "surface modification", "passivation"],
        "配体工程": ["ligand engineering", "ligand exchange"],
        "器件结构": ["device architecture", "device structure"],
        "工艺优化": ["annealing", "thermal treatment"],
    },
    research_type_keywords={
        "OLED": [r'\bOLED\b', r'organic\s+light.emitting\s+diode'],
        "PLED": [r'\bPLED\b', r'polymer\s+light.emitting\s+diode'],
        "QLED": [r'\bQLED\b', r'quantum\s+dot\s+LED'],
        "PeLED": [r'\bPeLED\b', r'perovskite\s+LED'],
    }
)


SOLAR_CELL_TEMPLATE = ExtractionTemplate(
    template_id="solar_cell",
    template_name="太阳能电池 (Perovskite Solar Cells)",
    template_type=TemplateType.SOLAR_CELL,
    description="钙钛矿太阳能电池、有机太阳能电池等光伏器件论文提取模板",
    device_config=DeviceFieldConfig(
        fields=[
            FieldDefinition(
                name="device_label",
                description="器件标签，如 'Control', 'Champion', 'Device A' 等",
                extraction_hints=["champion device", "best device", "optimized device", "control device"]
            ),
            FieldDefinition(
                name="structure",
                description="完整的器件结构，如 'FTO/TiO2/Perovskite/Spiro-OMeTAD/Au'",
                extraction_hints=["device structure", "architecture", "FTO", "ITO", "layer structure"]
            ),
            FieldDefinition(
                name="pce",
                description="光电转换效率，如 '25.5%' 或 'PCE = 24.8%'",
                unit="%",
                aliases=["PCE", "power conversion efficiency", "efficiency"],
                extraction_hints=["PCE", "power conversion efficiency", "efficiency", "η"]
            ),
            FieldDefinition(
                name="jsc",
                description="短路电流密度，如 '25.5 mA/cm²'",
                unit="mA/cm²",
                aliases=["Jsc", "Jsc", "short-circuit current density"],
                extraction_hints=["Jsc", "Jsc", "short-circuit current", "mA/cm²"]
            ),
            FieldDefinition(
                name="voc",
                description="开路电压，如 '1.12 V'",
                unit="V",
                aliases=["Voc", "Voc", "open-circuit voltage"],
                extraction_hints=["Voc", "Voc", "open-circuit voltage", "V"]
            ),
            FieldDefinition(
                name="ff",
                description="填充因子，如 '0.78' 或 '78%'",
                unit="%",
                aliases=["FF", "fill factor"],
                extraction_hints=["FF", "fill factor"]
            ),
            FieldDefinition(
                name="jv_curve",
                description="J-V 曲线特征描述",
                extraction_hints=["J-V curve", "J-V characteristics"]
            ),
            FieldDefinition(
                name="stability",
                description="器件稳定性，如 'maintained 90% after 1000 h'",
                extraction_hints=["stability", "lifetime", "degradation"]
            ),
            FieldDefinition(
                name="hysteresis",
                description="迟滞效应描述",
                extraction_hints=["hysteresis", "hysteresis index"]
            ),
            FieldDefinition(
                name="notes",
                description="其他重要备注或实验条件"
            ),
        ],
        multi_device_support=True,
        max_devices=6
    ),
    paper_config=PaperFieldConfig(
        fields=[
            FieldDefinition(name="title", description="论文标题"),
            FieldDefinition(name="authors", description="作者列表，逗号分隔"),
            FieldDefinition(name="journal_name", description="期刊名称"),
            FieldDefinition(name="raw_journal_title", description="期刊原始标题"),
            FieldDefinition(name="raw_issn", description="原始 print ISSN"),
            FieldDefinition(name="raw_eissn", description="原始 electronic ISSN"),
            FieldDefinition(name="matched_journal_title", description="期刊匹配后的标准标题"),
            FieldDefinition(name="matched_issn", description="期刊匹配后的标准 ISSN"),
            FieldDefinition(name="match_method", description="期刊匹配方式"),
            FieldDefinition(name="journal_profile_url", description="期刊主页 URL"),
            FieldDefinition(name="impact_factor", description="影响因子", field_type="number"),
            FieldDefinition(name="impact_factor_year", description="影响因子年份", field_type="integer"),
            FieldDefinition(name="impact_factor_source", description="影响因子来源"),
            FieldDefinition(name="impact_factor_status", description="影响因子获取状态"),
            FieldDefinition(name="year", description="发表年份", field_type="integer"),
            FieldDefinition(name="optimization_strategy", description="论文的主要优化策略总结"),
            FieldDefinition(name="best_pce", description="论文报道的最高 PCE 值"),
            FieldDefinition(name="research_type", description="研究类型，如 'Perovskite SC', 'Organic SC', 'DSSC'"),
            FieldDefinition(name="perovskite_composition", description="钙钛矿组分，如 'MAPbI3', 'FAPbI3'"),
        ]
    ),
    data_source_config=DataSourceFieldConfig(
        enabled=True,
        fields=["pce_source", "jsc_source", "voc_source", "ff_source", "structure_source"]
    ),
    prompt_template="""你是一个学术论文数据提取专家，专注于太阳能电池领域。请从以下论文 Markdown 文本中提取结构化数据。

## 提取要求

### 1. 论文基本信息 (paper_info)
- title: 论文标题
- authors: 作者列表，逗号分隔
- journal_name: 期刊名称
- impact_factor: 影响因子（从论文首页或页眉提取，若无则为 null）
- year: 发表年份
- optimization_strategy: 主要优化策略的一句话总结，使用"中文总结 | English summary"的中英对照形式
- best_pce: 论文报道的最高 PCE 值
- research_type: 研究类型（如 Perovskite SC, Organic SC, DSSC, CIGS）
- perovskite_composition: 钙钛矿组分（如适用）

### 2. 器件数据 (devices) - 重要：支持多器件
每个器件包含完整的性能参数，确保数据不跨器件错位：
- device_label: 器件标签（如 "Control", "Champion", "Device A"）
- structure: 完整器件结构（如 "FTO/TiO2/Perovskite/Spiro-OMeTAD/Au"）
- pce: 光电转换效率（如 "25.5%" 或 "PCE = 24.8%"）
- jsc: 短路电流密度（如 "25.5 mA/cm²"）
- voc: 开路电压（如 "1.12 V"）
- ff: 填充因子（如 "0.78" 或 "78%"）
- jv_curve: J-V 曲线特征描述
- stability: 器件稳定性描述
- hysteresis: 迟滞效应描述
- notes: 其他重要信息

### 3. 数据溯源 (data_source) - 必须填写
为每个关键参数提供原文引用句子：
- pce_source: PCE 数据的原文句子
- jsc_source: Jsc 数据的原文句子
- voc_source: Voc 数据的原文句子
- ff_source: FF 数据的原文句子
- structure_source: 器件结构的原文句子

### 4. 优化详情 (optimization)
- level: 优化层面（如 "界面工程、钝化层、组分调控"）
- strategy: 具体优化策略描述
- key_findings: 关键发现或创新点

## 输出格式

请严格按照以下 JSON Schema 输出：

```json
{schema}
```

## 重要规则

1. **多器件处理**：如果论文包含多个器件，每个器件的数据必须独立成一个完整的对象
2. **数据完整性**：每个器件的 PCE、Jsc、Voc、FF 等参数必须来自同一个器件
3. **数据溯源**：每个数值都必须附上原文出处
4. **空值处理**：如果某字段无法提取，使用 null
5. **单位保留**：保留原始单位，如 "%"、"mA/cm²"、"V"

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出。
""",
    regex_patterns={
        "pce": [
            r'PCE[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'power conversion efficiency[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'efficiency[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
            r'η[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
        ],
        "jsc": [
            r'Jsc[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:mA/cm²|mA cm⁻²|mA·cm⁻²)',
            r'short.circuit current[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:mA/cm²|mA cm⁻²)',
        ],
        "voc": [
            r'Voc[^0-9]*?([0-9]+\.?[0-9]*)\s*V',
            r'open.circuit voltage[^0-9]*?([0-9]+\.?[0-9]*)\s*V',
        ],
        "ff": [
            r'FF[^0-9]*?([0-9]+\.?[0-9]*)\s*%?',
            r'fill factor[^0-9]*?([0-9]+\.?[0-9]*)\s*%?',
        ],
        "structure": [
            r'((?:FTO|ITO|Glass)\s*/\s*[A-Za-z0-9:+()._\-\s]{1,50}(?:\s*/\s*[A-Za-z0-9:+()._\-\s]{1,50}){2,10})',
        ],
    },
    optimization_keywords={
        "界面工程": ["interface engineering", "interface modification", "interfacial layer"],
        "钝化层": ["passivation", "passivating", "defect passivation"],
        "组分调控": ["composition engineering", "composition tuning", "mixed cation"],
        "溶剂工程": ["solvent engineering", "antisolvent", "solvent treatment"],
        "退火处理": ["annealing", "thermal annealing", "post-treatment"],
        "添加剂工程": ["additive engineering", "additive"],
    },
    research_type_keywords={
        "Perovskite SC": [r'perovskite\s+solar\s+cell', r'PSC', r'perovskite\s+photovoltaic'],
        "Organic SC": [r'organic\s+solar\s+cell', r'OSC', r'organic\s+photovoltaic', r'OPV'],
        "DSSC": [r'dye.sensitized\s+solar\s+cell', r'DSSC', r'dye.sensitized'],
        "CIGS": [r'CIGS', r'Cu\(In,Ga\)Se2'],
    }
)


BATTERY_TEMPLATE = ExtractionTemplate(
    template_id="battery",
    template_name="锂电池 (Li-ion Battery)",
    template_type=TemplateType.BATTERY,
    description="锂离子电池、固态电池、锂硫电池等电池器件论文提取模板",
    device_config=DeviceFieldConfig(
        fields=[
            FieldDefinition(
                name="device_label",
                description="器件标签，如 'Control', 'Optimized', 'Sample A' 等",
                extraction_hints=["control", "optimized", "sample", "electrode"]
            ),
            FieldDefinition(
                name="configuration",
                description="电池配置，如 'LiFePO4/graphite', 'NMC811/Si-C'",
                extraction_hints=["cathode", "anode", "configuration", "full cell", "half cell"]
            ),
            FieldDefinition(
                name="capacity",
                description="比容量，如 '180 mAh/g' 或 '容量保持率 95%'",
                unit="mAh/g",
                aliases=["specific capacity", "capacity retention"],
                extraction_hints=["capacity", "mAh/g", "specific capacity"]
            ),
            FieldDefinition(
                name="cycling_stability",
                description="循环稳定性，如 '95% after 500 cycles'",
                extraction_hints=["cycling", "cycles", "retention", "stability"]
            ),
            FieldDefinition(
                name="energy_density",
                description="能量密度，如 '350 Wh/kg'",
                unit="Wh/kg",
                aliases=["energy density"],
                extraction_hints=["energy density", "Wh/kg", "Wh/L"]
            ),
            FieldDefinition(
                name="power_density",
                description="功率密度，如 '500 W/kg'",
                unit="W/kg",
                aliases=["power density"],
                extraction_hints=["power density", "W/kg"]
            ),
            FieldDefinition(
                name="coulombic_efficiency",
                description="库伦效率，如 '99.5%'",
                unit="%",
                aliases=["CE", "Coulombic efficiency"],
                extraction_hints=["Coulombic efficiency", "CE", "Coulombic"]
            ),
            FieldDefinition(
                name="rate_capability",
                description="倍率性能，如 '120 mAh/g @ 5C'",
                extraction_hints=["rate capability", "rate performance", "C-rate"]
            ),
            FieldDefinition(
                name="voltage",
                description="工作电压，如 '3.7 V'",
                unit="V",
                extraction_hints=["voltage", "working voltage", "platform"]
            ),
            FieldDefinition(
                name="notes",
                description="其他重要备注或实验条件"
            ),
        ],
        multi_device_support=True,
        max_devices=6
    ),
    paper_config=PaperFieldConfig(
        fields=[
            FieldDefinition(name="title", description="论文标题"),
            FieldDefinition(name="authors", description="作者列表，逗号分隔"),
            FieldDefinition(name="journal_name", description="期刊名称"),
            FieldDefinition(name="raw_journal_title", description="期刊原始标题"),
            FieldDefinition(name="raw_issn", description="原始 print ISSN"),
            FieldDefinition(name="raw_eissn", description="原始 electronic ISSN"),
            FieldDefinition(name="matched_journal_title", description="期刊匹配后的标准标题"),
            FieldDefinition(name="matched_issn", description="期刊匹配后的标准 ISSN"),
            FieldDefinition(name="match_method", description="期刊匹配方式"),
            FieldDefinition(name="journal_profile_url", description="期刊主页 URL"),
            FieldDefinition(name="impact_factor", description="影响因子", field_type="number"),
            FieldDefinition(name="impact_factor_year", description="影响因子年份", field_type="integer"),
            FieldDefinition(name="impact_factor_source", description="影响因子来源"),
            FieldDefinition(name="impact_factor_status", description="影响因子获取状态"),
            FieldDefinition(name="year", description="发表年份", field_type="integer"),
            FieldDefinition(name="optimization_strategy", description="论文的主要优化策略总结"),
            FieldDefinition(name="best_capacity", description="论文报道的最高容量"),
            FieldDefinition(name="research_type", description="研究类型，如 'Li-ion', 'Solid-state', 'Li-S'"),
            FieldDefinition(name="cathode_material", description="正极材料类型"),
            FieldDefinition(name="anode_material", description="负极材料类型"),
        ]
    ),
    data_source_config=DataSourceFieldConfig(
        enabled=True,
        fields=["capacity_source", "cycling_source", "energy_density_source", "configuration_source"]
    ),
    prompt_template="""你是一个学术论文数据提取专家，专注于锂电池领域。请从以下论文 Markdown 文本中提取结构化数据。

## 提取要求

### 1. 论文基本信息 (paper_info)
- title: 论文标题
- authors: 作者列表，逗号分隔
- journal_name: 期刊名称
- impact_factor: 影响因子（从论文首页或页眉提取，若无则为 null）
- year: 发表年份
- optimization_strategy: 主要优化策略的一句话总结
- best_capacity: 论文报道的最高容量
- research_type: 研究类型（如 Li-ion, Solid-state, Li-S, Na-ion）
- cathode_material: 正极材料类型
- anode_material: 负极材料类型

### 2. 器件数据 (devices) - 重要：支持多器件
每个器件包含完整的性能参数：
- device_label: 器件标签（如 "Control", "Optimized", "Sample A"）
- configuration: 电池配置（如 "LiFePO4/graphite"）
- capacity: 比容量（如 "180 mAh/g"）
- cycling_stability: 循环稳定性（如 "95% after 500 cycles"）
- energy_density: 能量密度（如 "350 Wh/kg"）
- power_density: 功率密度（如 "500 W/kg"）
- coulombic_efficiency: 库伦效率（如 "99.5%"）
- rate_capability: 倍率性能（如 "120 mAh/g @ 5C"）
- voltage: 工作电压（如 "3.7 V"）
- notes: 其他重要信息

### 3. 数据溯源 (data_source) - 必须填写
- capacity_source: 容量数据的原文句子
- cycling_source: 循环稳定性数据的原文句子
- energy_density_source: 能量密度数据的原文句子
- configuration_source: 电池配置的原文句子

### 4. 优化详情 (optimization)
- level: 优化层面（如 "材料改性、界面工程、电解质优化"）
- strategy: 具体优化策略描述
- key_findings: 关键发现或创新点

## 输出格式

请严格按照以下 JSON Schema 输出：

```json
{schema}
```

## 重要规则

1. **多器件处理**：每个器件的数据必须独立成一个完整的对象
2. **数据完整性**：每个器件的容量、循环稳定性等参数必须来自同一个器件
3. **数据溯源**：每个数值都必须附上原文出处
4. **空值处理**：如果某字段无法提取，使用 null
5. **单位保留**：保留原始单位，如 "mAh/g"、"Wh/kg"、"V"

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出。
""",
    regex_patterns={
        "capacity": [
            r'([0-9]+\.?[0-9]*)\s*(?:mAh/g|mAh\s*g⁻¹|mAh·g⁻¹)',
            r'capacity[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:mAh/g|mAh\s*g⁻¹)',
            r'specific capacity[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:mAh/g|mAh\s*g⁻¹)',
        ],
        "cycling_stability": [
            r'([0-9]+\.?[0-9]*)\s*%\s*(?:after|for)\s*([0-9]+)\s*cycles?',
            r'([0-9]+)\s*cycles?[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
            r'capacity retention[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
        ],
        "energy_density": [
            r'([0-9]+\.?[0-9]*)\s*(?:Wh/kg|Wh\s*kg⁻¹|Wh·kg⁻¹)',
            r'energy density[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:Wh/kg|Wh\s*kg⁻¹)',
        ],
        "coulombic_efficiency": [
            r'Coulombic efficiency[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
            r'CE[^0-9]*?([0-9]+\.?[0-9]*)\s*%',
        ],
    },
    optimization_keywords={
        "材料改性": ["material modification", "doping", "coating", "surface modification"],
        "界面工程": ["interface engineering", "SEI", "interphase", "interface layer"],
        "电解质优化": ["electrolyte optimization", "electrolyte additive", "solid electrolyte"],
        "结构设计": ["structure design", "nanostructure", "hierarchical structure"],
        "粘结剂优化": ["binder optimization", "binder design"],
    },
    research_type_keywords={
        "Li-ion": [r'Li.ion\s+battery', r'lithium.ion\s+battery', r'LIB'],
        "Solid-state": [r'solid.state\s+battery', r'solid\s+electrolyte', r'all.solid.state'],
        "Li-S": [r'lithium.sulfur', r'Li.S\s+battery'],
        "Na-ion": [r'sodium.ion', r'Na.ion\s+battery'],
    }
)


SENSOR_TEMPLATE = ExtractionTemplate(
    template_id="sensor",
    template_name="传感器 (Sensors)",
    template_type=TemplateType.SENSOR,
    description="化学传感器、生物传感器、气体传感器等传感器器件论文提取模板",
    device_config=DeviceFieldConfig(
        fields=[
            FieldDefinition(
                name="device_label",
                description="器件标签，如 'Sensor A', 'Optimized sensor' 等",
                extraction_hints=["sensor", "device", "electrode"]
            ),
            FieldDefinition(
                name="sensor_type",
                description="传感器类型，如 'Electrochemical', 'Optical', 'Piezoelectric'",
                extraction_hints=["electrochemical", "optical", "piezoelectric", "resistive"]
            ),
            FieldDefinition(
                name="target_analyte",
                description="目标分析物，如 'Glucose', 'H2O2', 'Heavy metals'",
                extraction_hints=["target", "analyte", "detection", "sensing"]
            ),
            FieldDefinition(
                name="sensitivity",
                description="灵敏度，如 '150 μA/mM·cm²' 或 '0.5 V/pH'",
                extraction_hints=["sensitivity", "response", "slope"]
            ),
            FieldDefinition(
                name="detection_limit",
                description="检测限，如 '10 nM' 或 'LOD = 5 ppb'",
                aliases=["LOD", "limit of detection"],
                extraction_hints=["LOD", "limit of detection", "detection limit"]
            ),
            FieldDefinition(
                name="linear_range",
                description="线性范围，如 '0.1-100 μM'",
                extraction_hints=["linear range", "linear detection range", "dynamic range"]
            ),
            FieldDefinition(
                name="selectivity",
                description="选择性描述，如 'High selectivity against interferents'",
                extraction_hints=["selectivity", "interference", "specificity"]
            ),
            FieldDefinition(
                name="response_time",
                description="响应时间，如 '< 5 s' 或 '3 s'",
                unit="s",
                extraction_hints=["response time", "response", "recovery time"]
            ),
            FieldDefinition(
                name="stability",
                description="稳定性，如 '95% after 30 days'",
                extraction_hints=["stability", "storage stability", "reproducibility"]
            ),
            FieldDefinition(
                name="reproducibility",
                description="重现性，如 'RSD = 3.5%'",
                extraction_hints=["reproducibility", "RSD", "repeatability"]
            ),
            FieldDefinition(
                name="notes",
                description="其他重要备注或实验条件"
            ),
        ],
        multi_device_support=True,
        max_devices=6
    ),
    paper_config=PaperFieldConfig(
        fields=[
            FieldDefinition(name="title", description="论文标题"),
            FieldDefinition(name="authors", description="作者列表，逗号分隔"),
            FieldDefinition(name="journal_name", description="期刊名称"),
            FieldDefinition(name="raw_journal_title", description="期刊原始标题"),
            FieldDefinition(name="raw_issn", description="原始 print ISSN"),
            FieldDefinition(name="raw_eissn", description="原始 electronic ISSN"),
            FieldDefinition(name="matched_journal_title", description="期刊匹配后的标准标题"),
            FieldDefinition(name="matched_issn", description="期刊匹配后的标准 ISSN"),
            FieldDefinition(name="match_method", description="期刊匹配方式"),
            FieldDefinition(name="journal_profile_url", description="期刊主页 URL"),
            FieldDefinition(name="impact_factor", description="影响因子", field_type="number"),
            FieldDefinition(name="impact_factor_year", description="影响因子年份", field_type="integer"),
            FieldDefinition(name="impact_factor_source", description="影响因子来源"),
            FieldDefinition(name="impact_factor_status", description="影响因子获取状态"),
            FieldDefinition(name="year", description="发表年份", field_type="integer"),
            FieldDefinition(name="optimization_strategy", description="论文的主要优化策略总结"),
            FieldDefinition(name="research_type", description="研究类型，如 'Electrochemical', 'Optical', 'Biosensor'"),
            FieldDefinition(name="sensing_material", description="传感材料类型"),
        ]
    ),
    data_source_config=DataSourceFieldConfig(
        enabled=True,
        fields=["sensitivity_source", "detection_limit_source", "selectivity_source", "target_analyte_source"]
    ),
    prompt_template="""你是一个学术论文数据提取专家，专注于传感器领域。请从以下论文 Markdown 文本中提取结构化数据。

## 提取要求

### 1. 论文基本信息 (paper_info)
- title: 论文标题
- authors: 作者列表，逗号分隔
- journal_name: 期刊名称
- impact_factor: 影响因子（从论文首页或页眉提取，若无则为 null）
- year: 发表年份
- optimization_strategy: 主要优化策略的一句话总结
- research_type: 研究类型（如 Electrochemical, Optical, Biosensor, Gas sensor）
- sensing_material: 传感材料类型

### 2. 器件数据 (devices) - 重要：支持多器件
每个器件包含完整的性能参数：
- device_label: 器件标签（如 "Sensor A", "Optimized sensor"）
- sensor_type: 传感器类型（如 "Electrochemical", "Optical"）
- target_analyte: 目标分析物（如 "Glucose", "H2O2"）
- sensitivity: 灵敏度（如 "150 μA/mM·cm²"）
- detection_limit: 检测限（如 "10 nM" 或 "LOD = 5 ppb"）
- linear_range: 线性范围（如 "0.1-100 μM"）
- selectivity: 选择性描述
- response_time: 响应时间（如 "< 5 s"）
- stability: 稳定性（如 "95% after 30 days"）
- reproducibility: 重现性（如 "RSD = 3.5%"）
- notes: 其他重要信息

### 3. 数据溯源 (data_source) - 必须填写
- sensitivity_source: 灵敏度数据的原文句子
- detection_limit_source: 检测限数据的原文句子
- selectivity_source: 选择性数据的原文句子
- target_analyte_source: 目标分析物的原文句子

### 4. 优化详情 (optimization)
- level: 优化层面（如 "材料选择、表面修饰、信号放大"）
- strategy: 具体优化策略描述
- key_findings: 关键发现或创新点

## 输出格式

请严格按照以下 JSON Schema 输出：

```json
{schema}
```

## 重要规则

1. **多器件处理**：每个器件的数据必须独立成一个完整的对象
2. **数据完整性**：每个器件的灵敏度、检测限等参数必须来自同一个器件
3. **数据溯源**：每个数值都必须附上原文出处
4. **空值处理**：如果某字段无法提取，使用 null
5. **单位保留**：保留原始单位

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出。
""",
    regex_patterns={
        "sensitivity": [
            r'sensitivity[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:μA/mM|μA\s*mM⁻¹|mA/mM|V/pH)',
            r'([0-9]+\.?[0-9]*)\s*(?:μA/mM|μA\s*mM⁻¹|mA/mM|V/pH)\s*(?:cm⁻²|cm²)?',
        ],
        "detection_limit": [
            r'LOD[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:nM|μM|mM|ppb|ppm)',
            r'limit of detection[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:nM|μM|mM|ppb|ppm)',
            r'detection limit[^0-9]*?([0-9]+\.?[0-9]*)\s*(?:nM|μM|mM|ppb|ppm)',
        ],
        "linear_range": [
            r'linear range[^0-9]*?([0-9]+\.?[0-9]*)\s*[-–]\s*([0-9]+\.?[0-9]*)\s*(?:nM|μM|mM|M)',
            r'([0-9]+\.?[0-9]*)\s*[-–]\s*([0-9]+\.?[0-9]*)\s*(?:nM|μM|mM|M)',
        ],
        "response_time": [
            r'response time[^0-9]*?([0-9]+\.?[0-9]*)\s*s',
            r'([0-9]+\.?[0-9]*)\s*s\s*response',
        ],
    },
    optimization_keywords={
        "材料选择": ["material selection", "sensing material", "recognition element"],
        "表面修饰": ["surface modification", "surface functionalization", "coating"],
        "信号放大": ["signal amplification", "amplification strategy", "enhancement"],
        "纳米材料": ["nanomaterial", "nanoparticle", "nanocomposite"],
        "生物识别": ["biorecognition", "enzyme", "antibody", "aptamer"],
    },
    research_type_keywords={
        "Electrochemical": [r'electrochemical\s+sensor', r'amperometric', r'potentiometric', r'voltammetric'],
        "Optical": [r'optical\s+sensor', r'fluorescence', r'colorimetric', r'surface plasmon'],
        "Biosensor": [r'biosensor', r'biological\s+sensor', r'enzyme\s+sensor'],
        "Gas sensor": [r'gas\s+sensor', r'chemiresistor', r'MOX\s+sensor'],
    }
)


DEFAULT_TEMPLATE = OLED_TEMPLATE

TEMPLATE_REGISTRY: Dict[str, ExtractionTemplate] = {
    "oled": OLED_TEMPLATE,
    "solar_cell": SOLAR_CELL_TEMPLATE,
    "battery": BATTERY_TEMPLATE,
    "sensor": SENSOR_TEMPLATE,
}


def get_template(template_id: str) -> Optional[ExtractionTemplate]:
    """
    获取提取模板
    
    Args:
        template_id: 模板ID
        
    Returns:
        提取模板，如果不存在则返回 None
    """
    return TEMPLATE_REGISTRY.get(template_id)


def get_default_template() -> ExtractionTemplate:
    """获取默认模板（OLED）"""
    return DEFAULT_TEMPLATE


def list_templates() -> List[Dict[str, str]]:
    """
    列出所有可用模板
    
    Returns:
        模板信息列表
    """
    return [
        {
            "id": template.template_id,
            "name": template.template_name,
            "description": template.description,
            "type": template.template_type.value,
        }
        for template in TEMPLATE_REGISTRY.values()
    ]


def register_template(template: ExtractionTemplate) -> None:
    """
    注册自定义模板
    
    Args:
        template: 提取模板
    """
    TEMPLATE_REGISTRY[template.template_id] = template


class DynamicTemplateGenerator:
    """
    动态模板生成器
    
    通过 LLM 根据用户输入的研究领域动态生成提取模板。
    这是预留的扩展接口，支持用户自定义研究领域。
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化动态模板生成器
        
        Args:
            llm_client: LLM 客户端实例
        """
        self.llm_client = llm_client
    
    def generate_template(
        self,
        research_field: str,
        keywords: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
        excel_template: Optional[str] = None,
    ) -> Optional[ExtractionTemplate]:
        """
        根据研究领域动态生成提取模板
        
        Args:
            research_field: 研究领域描述
            keywords: 关键词列表
            metrics: 关键指标列表
            excel_template: Excel 模板路径或内容
            
        Returns:
            生成的提取模板
        """
        if self.llm_client is None:
            return None
        
        prompt = self._build_generation_prompt(research_field, keywords, metrics, excel_template)
        
        try:
            response = self.llm_client.generate_json(prompt, temperature=0.3)
            return self._parse_template_response(response, research_field)
        except Exception:
            return None
    
    def _build_generation_prompt(
        self,
        research_field: str,
        keywords: Optional[List[str]],
        metrics: Optional[List[str]],
        excel_template: Optional[str],
    ) -> str:
        """构建模板生成 Prompt"""
        prompt = f"""你是一个学术论文数据提取专家。请根据以下信息生成一个结构化的提取模板。

研究领域：{research_field}
"""
        if keywords:
            prompt += f"\n关键词：{', '.join(keywords)}"
        
        if metrics:
            prompt += f"\n关键指标：{', '.join(metrics)}"
        
        if excel_template:
            prompt += f"\n\nExcel 模板参考：\n{excel_template[:2000]}"
        
        prompt += """

请生成一个 JSON 格式的提取模板，包含以下内容：

1. template_id: 模板唯一标识（小写字母和下划线）
2. template_name: 模板名称
3. description: 模板描述
4. device_fields: 器件/实验数据字段列表，每个字段包含：
   - name: 字段名
   - description: 字段描述
   - unit: 单位（如有）
   - aliases: 别名列表
   - extraction_hints: 提取提示词
5. paper_fields: 论文基本信息字段列表
6. data_source_fields: 数据溯源字段列表

请严格按照 JSON 格式输出。
"""
        return prompt
    
    def _parse_template_response(
        self,
        response: Dict[str, Any],
        research_field: str
    ) -> Optional[ExtractionTemplate]:
        """解析 LLM 响应为模板对象"""
        try:
            device_fields = [
                FieldDefinition(
                    name=f.get("name", ""),
                    description=f.get("description", ""),
                    unit=f.get("unit"),
                    aliases=f.get("aliases", []),
                    extraction_hints=f.get("extraction_hints", []),
                )
                for f in response.get("device_fields", [])
            ]
            
            paper_fields = [
                FieldDefinition(
                    name=f.get("name", ""),
                    description=f.get("description", ""),
                )
                for f in response.get("paper_fields", [])
            ]
            
            return ExtractionTemplate(
                template_id=response.get("template_id", "custom"),
                template_name=response.get("template_name", research_field),
                template_type=TemplateType.DYNAMIC,
                description=response.get("description", f"动态生成的 {research_field} 模板"),
                device_config=DeviceFieldConfig(fields=device_fields),
                paper_config=PaperFieldConfig(fields=paper_fields),
                data_source_config=DataSourceFieldConfig(
                    enabled=True,
                    fields=response.get("data_source_fields", [])
                ),
                prompt_template="",
            )
        except Exception:
            return None
