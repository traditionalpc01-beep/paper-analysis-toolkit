"""
Pydantic 数据模型模块

定义论文数据提取的结构化模型，确保 LLM 输出符合预期格式。
支持多种研究领域的数据模型。
"""

from .schemas import (
    DeviceData,
    PaperInfo,
    PaperData,
    ExtractionResult,
    DataSourceReference,
    OptimizationInfo,
    SolarCellDeviceData,
    BatteryDeviceData,
    SensorDeviceData,
)
from .templates import (
    TemplateType,
    FieldDefinition,
    DeviceFieldConfig,
    PaperFieldConfig,
    DataSourceFieldConfig,
    ExtractionTemplate,
    OLED_TEMPLATE,
    SOLAR_CELL_TEMPLATE,
    BATTERY_TEMPLATE,
    SENSOR_TEMPLATE,
    DEFAULT_TEMPLATE,
    TEMPLATE_REGISTRY,
    get_template,
    get_default_template,
    list_templates,
    register_template,
    DynamicTemplateGenerator,
)

__all__ = [
    "DeviceData",
    "PaperInfo",
    "PaperData",
    "ExtractionResult",
    "DataSourceReference",
    "OptimizationInfo",
    "SolarCellDeviceData",
    "BatteryDeviceData",
    "SensorDeviceData",
    "TemplateType",
    "FieldDefinition",
    "DeviceFieldConfig",
    "PaperFieldConfig",
    "DataSourceFieldConfig",
    "ExtractionTemplate",
    "OLED_TEMPLATE",
    "SOLAR_CELL_TEMPLATE",
    "BATTERY_TEMPLATE",
    "SENSOR_TEMPLATE",
    "DEFAULT_TEMPLATE",
    "TEMPLATE_REGISTRY",
    "get_template",
    "get_default_template",
    "list_templates",
    "register_template",
    "DynamicTemplateGenerator",
]
