"""
Prompt 模板模块 v4.0

v4.0 重构：
- 结构化 Prompt 模板（清晰的章节划分）
- Few-shot 示例库（支持多领域）
- 动态 Prompt 组装逻辑
- 多轮对话验证机制

支持领域：
- OLED/LED/QLED 器件
- 太阳能电池 (Perovskite Solar Cells)
- 锂电池 (Li-ion Battery)
- 传感器 (Sensors)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic

T = TypeVar('T')


class PromptSection(Enum):
    """Prompt 章节枚举"""
    TASK_DESCRIPTION = "task_description"
    FIELD_DEFINITIONS = "field_definitions"
    OUTPUT_FORMAT = "output_format"
    RULES = "rules"
    FEW_SHOT_EXAMPLES = "few_shot_examples"
    CURRENT_TASK = "current_task"


@dataclass
class FewShotExample:
    """Few-shot 示例数据结构"""
    input_text: str
    expected_output: Dict[str, Any]
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_prompt_text(self, include_output: bool = True) -> str:
        """转换为 Prompt 文本格式"""
        lines = []
        if self.description:
            lines.append(f"### 示例：{self.description}")
        lines.append("#### 输入文本片段：")
        lines.append(self.input_text[:500] + ("..." if len(self.input_text) > 500 else ""))
        if include_output:
            lines.append("#### 期望输出：")
            lines.append("```json")
            lines.append(json.dumps(self.expected_output, indent=2, ensure_ascii=False))
            lines.append("```")
        return "\n".join(lines)


@dataclass
class StructuredPromptTemplate:
    """结构化 Prompt 模板"""
    template_id: str
    template_name: str
    task_description: str
    field_definitions: Dict[str, str]
    output_format: str
    rules: List[str]
    few_shot_examples: List[FewShotExample] = field(default_factory=list)
    bilingual_fields: List[str] = field(default_factory=list)

    def render(
        self,
        paper_text: str,
        schema: Optional[Dict[str, Any]] = None,
        num_examples: int = 2,
        include_rules: bool = True,
    ) -> str:
        """
        渲染完整的 Prompt

        Args:
            paper_text: 论文文本
            schema: JSON Schema
            num_examples: 包含的 Few-shot 示例数量
            include_rules: 是否包含规则章节

        Returns:
            完整的 Prompt 字符串
        """
        sections = []

        sections.append(self._render_task_description())
        sections.append(self._render_field_definitions())
        sections.append(self._render_output_format(schema))

        if include_rules:
            sections.append(self._render_rules())

        if num_examples > 0 and self.few_shot_examples:
            sections.append(self._render_few_shot_examples(num_examples))

        sections.append(self._render_current_task(paper_text))

        return "\n\n".join(sections)

    def _render_task_description(self) -> str:
        """渲染任务描述章节"""
        return f"## 任务说明\n\n{self.task_description}"

    def _render_field_definitions(self) -> str:
        """渲染字段定义章节"""
        lines = ["## 字段定义\n"]
        for field_name, description in self.field_definitions.items():
            lines.append(f"- **{field_name}**: {description}")
        return "\n".join(lines)

    def _render_output_format(self, schema: Optional[Dict[str, Any]] = None) -> str:
        """渲染输出格式章节"""
        lines = ["## 输出格式\n"]
        lines.append("请严格按照以下 JSON Schema 输出，不要添加任何额外说明：\n")
        lines.append("```json")
        if schema:
            lines.append(json.dumps(schema, indent=2, ensure_ascii=False))
        else:
            lines.append("{schema}")
        lines.append("```")
        return "\n".join(lines)

    def _render_rules(self) -> str:
        """渲染规则章节"""
        lines = ["## 重要规则\n"]
        for i, rule in enumerate(self.rules, 1):
            lines.append(f"{i}. {rule}")
        return "\n".join(lines)

    def _render_few_shot_examples(self, num_examples: int) -> str:
        """渲染 Few-shot 示例章节"""
        lines = ["## 示例参考\n"]
        lines.append("以下是一些典型的提取示例，供参考：\n")

        selected_examples = self.few_shot_examples[:num_examples]
        for i, example in enumerate(selected_examples, 1):
            lines.append(f"### 示例 {i}")
            lines.append(example.to_prompt_text())
            lines.append("")

        return "\n".join(lines)

    def _render_current_task(self, paper_text: str) -> str:
        """渲染当前任务章节"""
        return f"## 当前任务\n\n请从以下论文文本中提取结构化数据：\n\n{paper_text}"


class FewShotExampleLibrary:
    """Few-shot 示例库"""

    _examples: Dict[str, List[FewShotExample]] = {}

    @classmethod
    def register(cls, domain: str, examples: List[FewShotExample]) -> None:
        """注册领域示例"""
        if domain not in cls._examples:
            cls._examples[domain] = []
        cls._examples[domain].extend(examples)

    @classmethod
    def get_examples(cls, domain: str, tags: Optional[List[str]] = None) -> List[FewShotExample]:
        """获取领域示例"""
        examples = cls._examples.get(domain, [])
        if tags:
            examples = [e for e in examples if any(t in e.tags for t in tags)]
        return examples

    @classmethod
    def get_random_examples(cls, domain: str, num: int = 2) -> List[FewShotExample]:
        """获取随机示例（按顺序取前 N 个）"""
        examples = cls._examples.get(domain, [])
        return examples[:num]

    @classmethod
    def list_domains(cls) -> List[str]:
        """列出所有已注册的领域"""
        return list(cls._examples.keys())


OLED_FEW_SHOT_EXAMPLES = [
    FewShotExample(
        input_text="""
The champion device exhibited a maximum external quantum efficiency (EQE) of 23.5%
with CIE coordinates of (0.21, 0.42). The device structure was ITO/PEDOT:PSS/EML/TPBi/LiF/Al.
The operational lifetime (LT50) reached 280 hours at an initial luminance of 1000 cd/m².
The optimized device showed significant improvement through ligand engineering approach.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "配体工程优化 | Ligand engineering optimization",
                "best_eqe": "23.5%"
            },
            "devices": [
                {
                    "device_label": "Champion",
                    "structure": "ITO/PEDOT:PSS/EML/TPBi/LiF/Al",
                    "eqe": "23.5%",
                    "cie": "(0.21, 0.42)",
                    "lifetime": "280 h @ 1000 cd/m²"
                }
            ],
            "data_source": {
                "eqe_source": "The champion device exhibited a maximum external quantum efficiency (EQE) of 23.5%",
                "cie_source": "CIE coordinates of (0.21, 0.42)",
                "lifetime_source": "The operational lifetime (LT50) reached 280 hours at an initial luminance of 1000 cd/m²",
                "structure_source": "The device structure was ITO/PEDOT:PSS/EML/TPBi/LiF/Al"
            }
        },
        description="OLED 器件典型提取示例 - 单器件高效率",
        tags=["high_efficiency", "single_device"]
    ),
    FewShotExample(
        input_text="""
Device A (control) showed an EQE of 15.2% with CIE (0.32, 0.35).
Device B (optimized with core-shell structure) achieved an EQE of 28.3% with CIE (0.30, 0.33).
The T50 lifetime for Device B was 450 hours at 1000 cd/m², significantly improved compared to
Device A's 120 hours. The device architecture was ITO/NiOx/Quantum Dots/ZnO/Al.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "核壳结构优化 | Core-shell structure optimization",
                "best_eqe": "28.3%"
            },
            "devices": [
                {
                    "device_label": "Device A (control)",
                    "structure": "ITO/NiOx/Quantum Dots/ZnO/Al",
                    "eqe": "15.2%",
                    "cie": "(0.32, 0.35)",
                    "lifetime": "120 h @ 1000 cd/m²"
                },
                {
                    "device_label": "Device B (optimized)",
                    "structure": "ITO/NiOx/Quantum Dots/ZnO/Al",
                    "eqe": "28.3%",
                    "cie": "(0.30, 0.33)",
                    "lifetime": "450 h @ 1000 cd/m²"
                }
            ],
            "data_source": {
                "eqe_source": "Device B (optimized with core-shell structure) achieved an EQE of 28.3%",
                "cie_source": "CIE (0.30, 0.33)",
                "lifetime_source": "The T50 lifetime for Device B was 450 hours at 1000 cd/m²",
                "structure_source": "The device architecture was ITO/NiOx/Quantum Dots/ZnO/Al"
            }
        },
        description="QLED 多器件对比示例 - 控制组与优化组",
        tags=["multi_device", "comparison", "QLED"]
    ),
    FewShotExample(
        input_text="""
A TADF emitter was synthesized and incorporated into OLED devices. The best device
demonstrated a maximum EQE of 32.1% with CIE coordinates of (0.26, 0.54).
The device configuration: ITO (100 nm)/PEDOT:PSS (40 nm)/mCP (10 nm)/EML (30 nm)/TPBi (40 nm)/LiF (1 nm)/Al (100 nm).
The device achieved a maximum luminance of 15,000 cd/m² and current efficiency of 78 cd/A.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "TADF 发光材料设计 | TADF emitter design",
                "best_eqe": "32.1%"
            },
            "devices": [
                {
                    "device_label": "Best device",
                    "structure": "ITO/PEDOT:PSS/mCP/EML/TPBi/LiF/Al",
                    "eqe": "32.1%",
                    "cie": "(0.26, 0.54)",
                    "luminance": "15000 cd/m²",
                    "current_efficiency": "78 cd/A"
                }
            ],
            "data_source": {
                "eqe_source": "The best device demonstrated a maximum EQE of 32.1%",
                "cie_source": "CIE coordinates of (0.26, 0.54)",
                "structure_source": "ITO (100 nm)/PEDOT:PSS (40 nm)/mCP (10 nm)/EML (30 nm)/TPBi (40 nm)/LiF (1 nm)/Al (100 nm)",
                "luminance_source": "The device achieved a maximum luminance of 15,000 cd/m²"
            }
        },
        description="TADF-OLED 高效率示例 - 完整参数提取",
        tags=["TADF", "high_efficiency", "complete_params"]
    ),
]

SOLAR_CELL_FEW_SHOT_EXAMPLES = [
    FewShotExample(
        input_text="""
The champion perovskite solar cell achieved a power conversion efficiency (PCE) of 25.6%
with a Jsc of 25.8 mA/cm², Voc of 1.18 V, and fill factor (FF) of 84.2%.
The device structure was FTO/TiO2/Perovskite/Spiro-OMeTAD/Au.
The device showed excellent stability, maintaining 95% of initial efficiency after 1000 hours under continuous illumination.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "钙钛矿组分优化与界面工程 | Perovskite composition and interface engineering",
                "best_pce": "25.6%"
            },
            "devices": [
                {
                    "device_label": "Champion",
                    "structure": "FTO/TiO2/Perovskite/Spiro-OMeTAD/Au",
                    "pce": "25.6%",
                    "jsc": "25.8 mA/cm²",
                    "voc": "1.18 V",
                    "ff": "84.2%",
                    "stability": "95% after 1000 h"
                }
            ],
            "data_source": {
                "pce_source": "The champion perovskite solar cell achieved a power conversion efficiency (PCE) of 25.6%",
                "jsc_source": "Jsc of 25.8 mA/cm²",
                "voc_source": "Voc of 1.18 V",
                "ff_source": "fill factor (FF) of 84.2%",
                "structure_source": "The device structure was FTO/TiO2/Perovskite/Spiro-OMeTAD/Au"
            }
        },
        description="钙钛矿太阳能电池高效率示例",
        tags=["perovskite", "high_efficiency", "single_device"]
    ),
    FewShotExample(
        input_text="""
Device A (control) showed a PCE of 18.5% with Jsc of 22.3 mA/cm², Voc of 1.05 V, and FF of 79%.
Device B (with passivation layer) achieved a PCE of 22.8% with Jsc of 24.5 mA/cm², Voc of 1.15 V, and FF of 81%.
Device C (optimized) reached a PCE of 24.2% with Jsc of 25.1 mA/cm², Voc of 1.18 V, and FF of 82%.
All devices had the structure: ITO/SnO2/Perovskite/Spiro-OMeTAD/Ag.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "钝化层优化与界面工程 | Passivation layer and interface engineering",
                "best_pce": "24.2%"
            },
            "devices": [
                {
                    "device_label": "Device A (control)",
                    "structure": "ITO/SnO2/Perovskite/Spiro-OMeTAD/Ag",
                    "pce": "18.5%",
                    "jsc": "22.3 mA/cm²",
                    "voc": "1.05 V",
                    "ff": "79%"
                },
                {
                    "device_label": "Device B (passivation)",
                    "structure": "ITO/SnO2/Perovskite/Spiro-OMeTAD/Ag",
                    "pce": "22.8%",
                    "jsc": "24.5 mA/cm²",
                    "voc": "1.15 V",
                    "ff": "81%"
                },
                {
                    "device_label": "Device C (optimized)",
                    "structure": "ITO/SnO2/Perovskite/Spiro-OMeTAD/Ag",
                    "pce": "24.2%",
                    "jsc": "25.1 mA/cm²",
                    "voc": "1.18 V",
                    "ff": "82%"
                }
            ],
            "data_source": {
                "pce_source": "Device C (optimized) reached a PCE of 24.2%",
                "jsc_source": "Jsc of 25.1 mA/cm²",
                "voc_source": "Voc of 1.18 V",
                "ff_source": "FF of 82%",
                "structure_source": "All devices had the structure: ITO/SnO2/Perovskite/Spiro-OMeTAD/Ag"
            }
        },
        description="钙钛矿太阳能电池多器件对比示例",
        tags=["perovskite", "multi_device", "comparison"]
    ),
    FewShotExample(
        input_text="""
An organic solar cell with a non-fullerene acceptor achieved a PCE of 18.2%.
The J-V characteristics showed Jsc of 26.5 mA/cm², Voc of 0.85 V, and FF of 81%.
The device structure was ITO/PEDOT:PSS/PM6:Y6/PDINN/Ag.
The device exhibited negligible hysteresis and maintained 90% efficiency after 500 hours.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "非富勒烯受体设计 | Non-fullerene acceptor design",
                "best_pce": "18.2%"
            },
            "devices": [
                {
                    "device_label": "Champion",
                    "structure": "ITO/PEDOT:PSS/PM6:Y6/PDINN/Ag",
                    "pce": "18.2%",
                    "jsc": "26.5 mA/cm²",
                    "voc": "0.85 V",
                    "ff": "81%",
                    "hysteresis": "negligible",
                    "stability": "90% after 500 h"
                }
            ],
            "data_source": {
                "pce_source": "An organic solar cell with a non-fullerene acceptor achieved a PCE of 18.2%",
                "jsc_source": "Jsc of 26.5 mA/cm²",
                "voc_source": "Voc of 0.85 V",
                "ff_source": "FF of 81%",
                "structure_source": "The device structure was ITO/PEDOT:PSS/PM6:Y6/PDINN/Ag"
            }
        },
        description="有机太阳能电池示例 - 非富勒烯受体",
        tags=["organic", "non-fullerene", "high_efficiency"]
    ),
]

BATTERY_FEW_SHOT_EXAMPLES = [
    FewShotExample(
        input_text="""
The LiFePO4/graphite full cell demonstrated a specific capacity of 165 mAh/g at 0.5C
with excellent cycling stability, maintaining 95% capacity retention after 1000 cycles.
The energy density reached 350 Wh/kg with a coulombic efficiency of 99.8%.
The cell showed superior rate capability, delivering 120 mAh/g even at 5C rate.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "正极材料改性优化 | Cathode material modification",
                "best_capacity": "165 mAh/g"
            },
            "devices": [
                {
                    "device_label": "LiFePO4/graphite cell",
                    "configuration": "LiFePO4/graphite",
                    "capacity": "165 mAh/g",
                    "cycling_stability": "95% after 1000 cycles",
                    "energy_density": "350 Wh/kg",
                    "coulombic_efficiency": "99.8%",
                    "rate_capability": "120 mAh/g @ 5C"
                }
            ],
            "data_source": {
                "capacity_source": "The LiFePO4/graphite full cell demonstrated a specific capacity of 165 mAh/g at 0.5C",
                "cycling_source": "maintaining 95% capacity retention after 1000 cycles",
                "energy_density_source": "The energy density reached 350 Wh/kg",
                "configuration_source": "LiFePO4/graphite full cell"
            }
        },
        description="锂离子电池典型示例 - LiFePO4 正极",
        tags=["Li-ion", "LiFePO4", "high_stability"]
    ),
    FewShotExample(
        input_text="""
Sample A (pristine NMC811) showed an initial capacity of 185 mAh/g with 80% retention after 200 cycles.
Sample B (Al2O3-coated) achieved 190 mAh/g with 92% retention after 200 cycles.
Sample C (dual-modified) delivered 195 mAh/g with 96% retention after 500 cycles.
All samples were tested in NMC811/graphite full cells at 1C rate.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "表面涂层与双改性策略 | Surface coating and dual modification",
                "best_capacity": "195 mAh/g"
            },
            "devices": [
                {
                    "device_label": "Sample A (pristine)",
                    "configuration": "NMC811/graphite",
                    "capacity": "185 mAh/g",
                    "cycling_stability": "80% after 200 cycles"
                },
                {
                    "device_label": "Sample B (Al2O3-coated)",
                    "configuration": "NMC811/graphite",
                    "capacity": "190 mAh/g",
                    "cycling_stability": "92% after 200 cycles"
                },
                {
                    "device_label": "Sample C (dual-modified)",
                    "configuration": "NMC811/graphite",
                    "capacity": "195 mAh/g",
                    "cycling_stability": "96% after 500 cycles"
                }
            ],
            "data_source": {
                "capacity_source": "Sample C (dual-modified) delivered 195 mAh/g",
                "cycling_source": "96% retention after 500 cycles",
                "configuration_source": "All samples were tested in NMC811/graphite full cells"
            }
        },
        description="锂电池多样品对比示例 - NMC811 正极改性",
        tags=["Li-ion", "NMC811", "multi_device", "comparison"]
    ),
    FewShotExample(
        input_text="""
A solid-state lithium battery with Li6PS5Cl electrolyte achieved a capacity of 150 mAh/g
at 0.1C with a working voltage of 3.7 V. The cell demonstrated excellent cycling stability
with 98% retention after 300 cycles. The energy density was 450 Wh/kg.
The Li metal anode showed no dendrite formation after extended cycling.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "固态电解质设计 | Solid-state electrolyte design",
                "best_capacity": "150 mAh/g"
            },
            "devices": [
                {
                    "device_label": "Solid-state cell",
                    "configuration": "Li/Li6PS5Cl/cathode",
                    "capacity": "150 mAh/g",
                    "cycling_stability": "98% after 300 cycles",
                    "energy_density": "450 Wh/kg",
                    "voltage": "3.7 V"
                }
            ],
            "data_source": {
                "capacity_source": "A solid-state lithium battery with Li6PS5Cl electrolyte achieved a capacity of 150 mAh/g",
                "cycling_source": "98% retention after 300 cycles",
                "energy_density_source": "The energy density was 450 Wh/kg",
                "configuration_source": "Li6PS5Cl electrolyte"
            }
        },
        description="固态锂电池示例 - 硫化物电解质",
        tags=["solid-state", "sulfide_electrolyte", "high_energy"]
    ),
]

SENSOR_FEW_SHOT_EXAMPLES = [
    FewShotExample(
        input_text="""
An electrochemical glucose sensor based on glucose oxidase exhibited a sensitivity of
150 μA/mM·cm² with a detection limit of 5 μM. The linear range was 0.01-10 mM.
The sensor showed excellent selectivity against common interferents such as ascorbic acid
and uric acid. The response time was less than 3 seconds.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "酶固定化与电极修饰 | Enzyme immobilization and electrode modification",
                "research_type": "Electrochemical biosensor"
            },
            "devices": [
                {
                    "device_label": "Glucose sensor",
                    "sensor_type": "Electrochemical",
                    "target_analyte": "Glucose",
                    "sensitivity": "150 μA/mM·cm²",
                    "detection_limit": "5 μM",
                    "linear_range": "0.01-10 mM",
                    "selectivity": "Excellent against ascorbic acid and uric acid",
                    "response_time": "< 3 s"
                }
            ],
            "data_source": {
                "sensitivity_source": "sensitivity of 150 μA/mM·cm²",
                "detection_limit_source": "detection limit of 5 μM",
                "selectivity_source": "excellent selectivity against common interferents such as ascorbic acid and uric acid",
                "target_analyte_source": "glucose sensor based on glucose oxidase"
            }
        },
        description="电化学葡萄糖传感器示例",
        tags=["electrochemical", "glucose", "biosensor"]
    ),
    FewShotExample(
        input_text="""
Sensor A (bare electrode) showed a sensitivity of 45 μA/mM·cm² with LOD of 50 nM.
Sensor B (nanoparticle-modified) achieved a sensitivity of 120 μA/mM·cm² with LOD of 10 nM.
Sensor C (optimized) reached a sensitivity of 180 μA/mM·cm² with LOD of 2 nM for H2O2 detection.
All sensors exhibited good reproducibility with RSD < 5%.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "纳米粒子修饰优化 | Nanoparticle modification optimization",
                "research_type": "Electrochemical sensor"
            },
            "devices": [
                {
                    "device_label": "Sensor A (bare)",
                    "sensor_type": "Electrochemical",
                    "target_analyte": "H2O2",
                    "sensitivity": "45 μA/mM·cm²",
                    "detection_limit": "50 nM",
                    "reproducibility": "RSD < 5%"
                },
                {
                    "device_label": "Sensor B (NP-modified)",
                    "sensor_type": "Electrochemical",
                    "target_analyte": "H2O2",
                    "sensitivity": "120 μA/mM·cm²",
                    "detection_limit": "10 nM",
                    "reproducibility": "RSD < 5%"
                },
                {
                    "device_label": "Sensor C (optimized)",
                    "sensor_type": "Electrochemical",
                    "target_analyte": "H2O2",
                    "sensitivity": "180 μA/mM·cm²",
                    "detection_limit": "2 nM",
                    "reproducibility": "RSD < 5%"
                }
            ],
            "data_source": {
                "sensitivity_source": "Sensor C (optimized) reached a sensitivity of 180 μA/mM·cm²",
                "detection_limit_source": "LOD of 2 nM for H2O2 detection",
                "target_analyte_source": "H2O2 detection"
            }
        },
        description="多传感器对比示例 - H2O2 检测",
        tags=["electrochemical", "H2O2", "multi_device", "comparison"]
    ),
    FewShotExample(
        input_text="""
A gas sensor based on ZnO nanowires demonstrated high sensitivity to NO2 with a detection
limit of 10 ppb at 300°C. The response (Rg/Ra) was 15.5 to 1 ppm NO2.
The sensor showed excellent selectivity against CO, NH3, and CH4.
The response and recovery times were 8 s and 12 s, respectively.
The sensor maintained 95% of its initial response after 30 days.
""",
        expected_output={
            "paper_info": {
                "optimization_strategy": "ZnO 纳米线结构设计 | ZnO nanowire structure design",
                "research_type": "Gas sensor"
            },
            "devices": [
                {
                    "device_label": "ZnO nanowire sensor",
                    "sensor_type": "Resistive",
                    "target_analyte": "NO2",
                    "sensitivity": "Rg/Ra = 15.5 @ 1 ppm",
                    "detection_limit": "10 ppb",
                    "selectivity": "Excellent against CO, NH3, CH4",
                    "response_time": "8 s",
                    "stability": "95% after 30 days"
                }
            ],
            "data_source": {
                "sensitivity_source": "The response (Rg/Ra) was 15.5 to 1 ppm NO2",
                "detection_limit_source": "detection limit of 10 ppb at 300°C",
                "selectivity_source": "excellent selectivity against CO, NH3, and CH4",
                "target_analyte_source": "high sensitivity to NO2"
            }
        },
        description="气体传感器示例 - ZnO 纳米线 NO2 检测",
        tags=["gas_sensor", "ZnO", "NO2", "nanowire"]
    ),
]

FewShotExampleLibrary.register("oled", OLED_FEW_SHOT_EXAMPLES)
FewShotExampleLibrary.register("solar_cell", SOLAR_CELL_FEW_SHOT_EXAMPLES)
FewShotExampleLibrary.register("battery", BATTERY_FEW_SHOT_EXAMPLES)
FewShotExampleLibrary.register("sensor", SENSOR_FEW_SHOT_EXAMPLES)


class PromptBuilder:
    """
    Prompt 组装器
    
    支持动态组装 Prompt，包括：
    - 基础模板 + Few-shot 示例 + 当前任务
    - 模板类型自动选择
    - 示例数量动态调整
    """
    
    TEMPLATE_DOMAIN_MAP = {
        "oled": "oled",
        "solar_cell": "solar_cell",
        "battery": "battery",
        "sensor": "sensor",
    }
    
    def __init__(
        self,
        template_id: str = "oled",
        num_examples: int = 2,
        include_rules: bool = True,
        max_input_chars: int = 15000,
    ):
        self.template_id = template_id
        self.domain = self.TEMPLATE_DOMAIN_MAP.get(template_id, "oled")
        self.num_examples = num_examples
        self.include_rules = include_rules
        self.max_input_chars = max_input_chars
    
    def build(
        self,
        paper_text: str,
        schema: Optional[Dict[str, Any]] = None,
        template_prompt: Optional[str] = None,
        extra_examples: Optional[List[FewShotExample]] = None,
    ) -> str:
        """
        构建完整的 Prompt
        
        Args:
            paper_text: 论文文本
            schema: JSON Schema
            template_prompt: 来自 ExtractionTemplate 的 prompt_template
            extra_examples: 额外的 Few-shot 示例
            
        Returns:
            完整的 Prompt 字符串
        """
        if template_prompt:
            return self._build_from_template(paper_text, schema, template_prompt, extra_examples)
        
        return self._build_from_structured(paper_text, schema, extra_examples)
    
    def _build_from_template(
        self,
        paper_text: str,
        schema: Optional[Dict[str, Any]],
        template_prompt: str,
        extra_examples: Optional[List[FewShotExample]],
    ) -> str:
        """从 ExtractionTemplate 的 prompt_template 构建"""
        truncated_text = self._truncate_text(paper_text)
        
        prompt = template_prompt.replace("{paper_text}", truncated_text)
        
        if schema:
            schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
            prompt = prompt.replace("{schema}", schema_str)
        
        if self.num_examples > 0:
            examples_section = self._build_examples_section(extra_examples)
            if examples_section:
                prompt = self._inject_examples(prompt, examples_section)
        
        return prompt
    
    def _build_from_structured(
        self,
        paper_text: str,
        schema: Optional[Dict[str, Any]],
        extra_examples: Optional[List[FewShotExample]],
    ) -> str:
        """从结构化模板构建"""
        structured_template = self._get_structured_template()
        structured_template.few_shot_examples = self._get_examples(extra_examples)
        
        truncated_text = self._truncate_text(paper_text)
        
        return structured_template.render(
            truncated_text,
            schema=schema,
            num_examples=self.num_examples,
            include_rules=self.include_rules,
        )
    
    def _get_structured_template(self) -> StructuredPromptTemplate:
        """获取结构化模板"""
        templates = {
            "oled": self._create_oled_template(),
            "solar_cell": self._create_solar_cell_template(),
            "battery": self._create_battery_template(),
            "sensor": self._create_sensor_template(),
        }
        return templates.get(self.domain, templates["oled"])
    
    def _create_oled_template(self) -> StructuredPromptTemplate:
        return StructuredPromptTemplate(
            template_id="oled",
            template_name="OLED/LED/QLED 器件",
            task_description="你是一个学术论文数据提取专家，专注于 OLED/LED/QLED 器件领域。请从论文文本中提取结构化数据。",
            field_definitions={
                "paper_info": "论文基本信息，包括标题、作者、期刊、影响因子、年份、优化策略等",
                "devices": "器件数据列表，每个器件包含标签、结构、EQE、CIE、寿命等参数",
                "data_source": "数据溯源，为每个关键参数提供原文引用",
            },
            output_format="JSON",
            rules=[
                "多器件处理：每个器件的数据必须独立成一个完整的对象",
                "数据完整性：每个器件的参数必须来自同一个器件",
                "数据溯源：每个数值都必须附上原文出处",
                "空值处理：无法提取的字段使用 null",
                "单位保留：保留原始单位",
                "双语输出：总结类字段使用中英对照格式",
            ],
            few_shot_examples=[],
        )
    
    def _create_solar_cell_template(self) -> StructuredPromptTemplate:
        return StructuredPromptTemplate(
            template_id="solar_cell",
            template_name="太阳能电池",
            task_description="你是一个学术论文数据提取专家，专注于太阳能电池领域。请从论文文本中提取结构化数据。",
            field_definitions={
                "paper_info": "论文基本信息，包括标题、作者、期刊、影响因子、年份、优化策略、最高 PCE 等",
                "devices": "器件数据列表，每个器件包含标签、结构、PCE、Jsc、Voc、FF 等参数",
                "data_source": "数据溯源，为每个关键参数提供原文引用",
            },
            output_format="JSON",
            rules=[
                "多器件处理：每个器件的数据必须独立成一个完整的对象",
                "数据完整性：PCE、Jsc、Voc、FF 必须来自同一个器件",
                "数据溯源：每个数值都必须附上原文出处",
                "空值处理：无法提取的字段使用 null",
                "单位保留：保留原始单位（%、mA/cm²、V）",
            ],
            few_shot_examples=[],
        )
    
    def _create_battery_template(self) -> StructuredPromptTemplate:
        return StructuredPromptTemplate(
            template_id="battery",
            template_name="锂电池",
            task_description="你是一个学术论文数据提取专家，专注于锂电池领域。请从论文文本中提取结构化数据。",
            field_definitions={
                "paper_info": "论文基本信息，包括标题、作者、期刊、影响因子、年份、优化策略、最高容量等",
                "devices": "器件数据列表，每个器件包含标签、配置、容量、循环稳定性、能量密度等参数",
                "data_source": "数据溯源，为每个关键参数提供原文引用",
            },
            output_format="JSON",
            rules=[
                "多器件处理：每个样品的数据必须独立成一个完整的对象",
                "数据完整性：容量、循环稳定性等参数必须来自同一个样品",
                "数据溯源：每个数值都必须附上原文出处",
                "空值处理：无法提取的字段使用 null",
                "单位保留：保留原始单位（mAh/g、Wh/kg、V）",
            ],
            few_shot_examples=[],
        )
    
    def _create_sensor_template(self) -> StructuredPromptTemplate:
        return StructuredPromptTemplate(
            template_id="sensor",
            template_name="传感器",
            task_description="你是一个学术论文数据提取专家，专注于传感器领域。请从论文文本中提取结构化数据。",
            field_definitions={
                "paper_info": "论文基本信息，包括标题、作者、期刊、影响因子、年份、优化策略等",
                "devices": "传感器数据列表，每个传感器包含标签、类型、目标物、灵敏度、检测限等参数",
                "data_source": "数据溯源，为每个关键参数提供原文引用",
            },
            output_format="JSON",
            rules=[
                "多器件处理：每个传感器的数据必须独立成一个完整的对象",
                "数据完整性：灵敏度、检测限等参数必须来自同一个传感器",
                "数据溯源：每个数值都必须附上原文出处",
                "空值处理：无法提取的字段使用 null",
                "单位保留：保留原始单位",
            ],
            few_shot_examples=[],
        )
    
    def _get_examples(
        self,
        extra_examples: Optional[List[FewShotExample]],
    ) -> List[FewShotExample]:
        """获取 Few-shot 示例"""
        examples = list(FewShotExampleLibrary.get_examples(self.domain))
        if extra_examples:
            examples.extend(extra_examples)
        return examples
    
    def _build_examples_section(
        self,
        extra_examples: Optional[List[FewShotExample]],
    ) -> Optional[str]:
        """构建示例章节"""
        examples = self._get_examples(extra_examples)
        if not examples:
            return None
        
        lines = ["## 示例参考\n"]
        lines.append("以下是一些典型的提取示例，供参考：\n")
        
        for i, example in enumerate(examples[:self.num_examples], 1):
            lines.append(f"### 示例 {i}")
            lines.append(example.to_prompt_text())
            lines.append("")
        
        return "\n".join(lines)
    
    def _inject_examples(self, prompt: str, examples_section: str) -> str:
        """将示例章节注入到 Prompt 中"""
        rules_marker = "## 重要规则"
        current_task_marker = "## 论文 Markdown 文本"
        
        if rules_marker in prompt:
            parts = prompt.split(rules_marker, 1)
            return f"{parts[0]}{examples_section}\n\n{rules_marker}{parts[1]}"
        
        if current_task_marker in prompt:
            parts = prompt.split(current_task_marker, 1)
            return f"{parts[0]}{examples_section}\n\n{current_task_marker}{parts[1]}"
        
        return f"{prompt}\n\n{examples_section}"
    
    def _truncate_text(self, text: str) -> str:
        """截断文本以适应最大长度"""
        if not text or len(text) <= self.max_input_chars:
            return text
        
        truncated = text[:self.max_input_chars]
        boundary = max(
            truncated.rfind("\n\n"),
            truncated.rfind(". "),
            truncated.rfind("\n"),
        )
        if boundary > self.max_input_chars * 0.7:
            return truncated[:boundary].strip()
        return truncated.strip()


class MultiTurnValidator:
    """
    多轮对话验证器
    
    功能：
    - 检查首轮提取结果中关键字段的缺失情况
    - 构造补充提问 Prompt
    - 合并多轮提取结果
    """
    
    CRITICAL_FIELDS = {
        "oled": ["eqe", "structure", "cie"],
        "solar_cell": ["pce", "jsc", "voc", "ff"],
        "battery": ["capacity", "cycling_stability"],
        "sensor": ["sensitivity", "detection_limit", "target_analyte"],
    }
    
    IMPORTANT_FIELDS = {
        "oled": ["lifetime", "luminance", "current_efficiency"],
        "solar_cell": ["stability", "hysteresis"],
        "battery": ["energy_density", "coulombic_efficiency"],
        "sensor": ["selectivity", "response_time", "linear_range"],
    }
    
    def __init__(
        self,
        template_id: str = "oled",
        enable_follow_up: bool = True,
        max_follow_ups: int = 1,
    ):
        self.template_id = template_id
        self.domain = PromptBuilder.TEMPLATE_DOMAIN_MAP.get(template_id, "oled")
        self.enable_follow_up = enable_follow_up
        self.max_follow_ups = max_follow_ups
    
    def validate(
        self,
        extraction_result: Dict[str, Any],
        paper_text: str,
    ) -> Dict[str, Any]:
        """
        验证提取结果并返回验证报告
        
        Args:
            extraction_result: 首轮提取结果
            paper_text: 原始论文文本
            
        Returns:
            验证报告，包含缺失字段和是否需要补充提取
        """
        report = {
            "is_complete": True,
            "missing_critical_fields": [],
            "missing_important_fields": [],
            "needs_follow_up": False,
            "device_completeness": [],
        }
        
        critical_fields = self.CRITICAL_FIELDS.get(self.domain, [])
        important_fields = self.IMPORTANT_FIELDS.get(self.domain, [])
        
        devices = extraction_result.get("devices", [])
        if not devices:
            report["is_complete"] = False
            report["missing_critical_fields"] = critical_fields
            report["needs_follow_up"] = True
            return report
        
        for i, device in enumerate(devices):
            device_report = {
                "device_index": i,
                "device_label": device.get("device_label", f"Device {i+1}"),
                "missing_critical": [],
                "missing_important": [],
                "completeness_score": 0.0,
            }
            
            for field in critical_fields:
                if not device.get(field):
                    device_report["missing_critical"].append(field)
            
            for field in important_fields:
                if not device.get(field):
                    device_report["missing_important"].append(field)
            
            total_fields = len(critical_fields) + len(important_fields)
            filled_fields = total_fields - len(device_report["missing_critical"]) - len(device_report["missing_important"])
            device_report["completeness_score"] = filled_fields / total_fields if total_fields > 0 else 1.0
            
            report["device_completeness"].append(device_report)
            
            if device_report["missing_critical"]:
                report["missing_critical_fields"].extend(device_report["missing_critical"])
                report["is_complete"] = False
        
        report["missing_critical_fields"] = list(set(report["missing_critical_fields"]))
        
        paper_info = extraction_result.get("paper_info", {})
        if not paper_info.get("optimization_strategy"):
            report["missing_important_fields"].append("optimization_strategy")
        
        report["needs_follow_up"] = (
            self.enable_follow_up
            and not report["is_complete"]
            and len(report["missing_critical_fields"]) > 0
        )
        
        return report
    
    def build_follow_up_prompt(
        self,
        extraction_result: Dict[str, Any],
        validation_report: Dict[str, Any],
        paper_text: str,
    ) -> Optional[str]:
        """
        构建补充提取的 Prompt
        
        Args:
            extraction_result: 首轮提取结果
            validation_report: 验证报告
            paper_text: 原始论文文本
            
        Returns:
            补充提取的 Prompt，如果不需要则返回 None
        """
        if not validation_report.get("needs_follow_up"):
            return None
        
        missing_fields = validation_report.get("missing_critical_fields", [])
        if not missing_fields:
            return None
        
        field_descriptions = self._get_field_descriptions()
        
        lines = [
            "## 补充提取任务",
            "",
            "你之前已经从论文中提取了部分数据，但以下关键字段缺失或不完整：",
            "",
        ]
        
        for field in missing_fields:
            desc = field_descriptions.get(field, field)
            lines.append(f"- **{field}**: {desc}")
        
        lines.extend([
            "",
            "### 已提取的数据",
            "```json",
            json.dumps(extraction_result, indent=2, ensure_ascii=False),
            "```",
            "",
            "### 任务要求",
            "请仔细检查以下论文文本，补充缺失的字段。如果确实无法找到相关数据，请保持 null。",
            "",
            "### 论文文本",
            paper_text[:10000],
            "",
            "### 输出格式",
            "请输出完整的 JSON 数据（包含已提取和补充的字段），格式与之前相同。",
        ])
        
        return "\n".join(lines)
    
    def merge_results(
        self,
        original_result: Dict[str, Any],
        follow_up_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        合并首轮和补充提取的结果
        
        Args:
            original_result: 首轮提取结果
            follow_up_result: 补充提取结果
            
        Returns:
            合并后的结果
        """
        merged = dict(original_result)
        
        paper_info = dict(merged.get("paper_info", {}))
        follow_up_paper_info = follow_up_result.get("paper_info", {})
        
        for key, value in follow_up_paper_info.items():
            if value is not None and paper_info.get(key) is None:
                paper_info[key] = value
        
        merged["paper_info"] = paper_info
        
        original_devices = merged.get("devices", [])
        follow_up_devices = follow_up_result.get("devices", [])
        
        if len(follow_up_devices) > len(original_devices):
            merged["devices"] = follow_up_devices
        else:
            merged_devices = []
            for i, orig_device in enumerate(original_devices):
                merged_device = dict(orig_device)
                if i < len(follow_up_devices):
                    for key, value in follow_up_devices[i].items():
                        if value is not None and merged_device.get(key) is None:
                            merged_device[key] = value
                merged_devices.append(merged_device)
            merged["devices"] = merged_devices
        
        data_source = dict(merged.get("data_source", {}))
        follow_up_data_source = follow_up_result.get("data_source", {})
        
        for key, value in follow_up_data_source.items():
            if value is not None and data_source.get(key) is None:
                data_source[key] = value
        
        merged["data_source"] = data_source
        
        return merged
    
    def _get_field_descriptions(self) -> Dict[str, str]:
        """获取字段描述"""
        descriptions = {
            "eqe": "外量子效率，如 '22.5%' 或 '18.2% (max)'",
            "structure": "完整的器件结构，如 'ITO/PEDOT:PSS/EML/TPBi/LiF/Al'",
            "cie": "CIE 色坐标，如 '(0.21, 0.32)'",
            "lifetime": "器件寿命，如 '150 h @ 1000 cd/m²'",
            "luminance": "亮度数据，如 '5000 cd/m²'",
            "current_efficiency": "电流效率，如 '68 cd/A'",
            "pce": "光电转换效率，如 '25.5%'",
            "jsc": "短路电流密度，如 '25.5 mA/cm²'",
            "voc": "开路电压，如 '1.12 V'",
            "ff": "填充因子，如 '0.78' 或 '78%'",
            "stability": "器件稳定性描述",
            "hysteresis": "迟滞效应描述",
            "capacity": "比容量，如 '180 mAh/g'",
            "cycling_stability": "循环稳定性，如 '95% after 500 cycles'",
            "energy_density": "能量密度，如 '350 Wh/kg'",
            "coulombic_efficiency": "库伦效率，如 '99.5%'",
            "sensitivity": "灵敏度，如 '150 μA/mM·cm²'",
            "detection_limit": "检测限，如 '10 nM'",
            "target_analyte": "目标分析物，如 'Glucose', 'H2O2'",
            "selectivity": "选择性描述",
            "response_time": "响应时间，如 '< 5 s'",
            "linear_range": "线性范围，如 '0.1-100 μM'",
        }
        return descriptions


EXTRACTION_PROMPT_V3 = """你是一个学术论文数据提取专家。请从以下论文 Markdown 文本中提取结构化数据。

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
- notes: 其他重要信息

### 3. 数据溯源 (data_source) - 必须填写
为每个关键参数提供原文引用句子：
- eqe_source: EQE 数据的原文句子
- cie_source: CIE 数据的原文句子
- lifetime_source: 寿命数据的原文句子
- structure_source: 器件结构的原文句子

## 输出格式

请严格按照以下 JSON Schema 输出，不要添加任何额外说明：

```json
{schema}
```

## 重要规则

1. **多器件处理**：如果论文包含多个器件，每个器件的数据必须独立成一个完整的对象
2. **数据完整性**：每个器件的 EQE、CIE、寿命等参数必须来自同一个器件
3. **数据溯源**：每个数值都必须附上原文出处
4. **空值处理**：如果某字段无法提取，使用 null
5. **单位保留**：保留原始单位，如 "%"、"h"、"cd/m²"
6. **双语输出**：对于总结类文本字段，尽量输出中英对照

## 论文 Markdown 文本

{paper_text}

请严格按照 JSON 格式输出，不要添加任何额外说明。
"""

BILINGUAL_POSTPROCESS_PROMPT = """你是一个学术论文数据双语处理专家。请对以下提取结果进行双语格式优化。

## 任务要求

对于以下字段，如果内容是纯中文或纯英文，请补充为"中文 | English"的双语对照格式：
- optimization_strategy: 优化策略
- notes: 器件备注

## 输入数据

```json
{data}
```

## 输出要求

1. 保持原有 JSON 结构不变
2. 仅对上述字段进行双语格式化
3. 如果字段已有双语格式，保持不变
4. 如果字段为 null，保持 null
5. 其他字段保持原样

请输出完整的 JSON 数据。
"""

LITE_PAPER_INFO_BACKFILL_PROMPT = """你是一个学术论文元数据提取专家。请从以下论文文本片段中提取基本信息。

## 任务要求

提取以下字段（如果存在）：
- title: 论文标题
- authors: 作者列表，逗号分隔
- journal_name: 期刊名称
- raw_journal_title: 期刊原始标题（从页眉或页脚提取）
- year: 发表年份

## 输入信息

文件名: {source_file}
元数据: {metadata}

## 论文文本片段

{paper_text}

## 输出格式

请输出 JSON 格式，包含上述字段。如果某字段无法提取，使用 null。

```json
{
  "title": "...",
  "authors": "...",
  "journal_name": "...",
  "raw_journal_title": "...",
  "year": ...
}
```
"""


def format_extraction_prompt_v3(paper_text: str, schema: Optional[Dict[str, Any]] = None) -> str:
    """格式化 v3 版本的提取 Prompt"""
    prompt = EXTRACTION_PROMPT_V3.replace("{paper_text}", paper_text)
    if schema:
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        prompt = prompt.replace("{schema}", schema_str)
    return prompt


def format_extraction_prompt_with_template(
    paper_text: str,
    template: Any,
    num_examples: int = 2,
) -> str:
    """
    使用 ExtractionTemplate 格式化提取 Prompt
    
    Args:
        paper_text: 论文文本
        template: ExtractionTemplate 实例
        num_examples: Few-shot 示例数量
        
    Returns:
        格式化后的 Prompt
    """
    builder = PromptBuilder(
        template_id=template.template_id,
        num_examples=num_examples,
    )
    
    schema = template.to_json_schema()
    
    return builder.build(
        paper_text,
        schema=schema,
        template_prompt=template.prompt_template,
    )


def format_bilingual_postprocess_prompt(data: Dict[str, Any]) -> str:
    """格式化双语后处理 Prompt"""
    data_str = json.dumps(data, indent=2, ensure_ascii=False)
    return BILINGUAL_POSTPROCESS_PROMPT.replace("{data}", data_str)


def format_lite_paper_info_backfill_prompt(
    paper_text: str,
    source_file: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """格式化轻量级信息回填 Prompt"""
    prompt = LITE_PAPER_INFO_BACKFILL_PROMPT
    prompt = prompt.replace("{paper_text}", paper_text[:6000])
    prompt = prompt.replace("{source_file}", source_file or "unknown")
    prompt = prompt.replace("{metadata}", json.dumps(metadata or {}, ensure_ascii=False))
    return prompt
