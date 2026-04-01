"""
模板系统单元测试

测试内容：
- 模板加载和选择
- 各领域模板的字段定义
- JSON Schema 生成
- 动态模板生成
"""

import pytest
from unittest.mock import Mock, patch

from paperinsight.models.templates import (
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


class TestFieldDefinition:
    """字段定义测试"""
    
    def test_field_definition_creation(self):
        """测试字段定义创建"""
        field = FieldDefinition(
            name="eqe",
            description="外量子效率",
            field_type="string",
            required=False,
            unit="%",
            aliases=["EQE", "external quantum efficiency"],
            extraction_hints=["EQE", "external quantum efficiency"]
        )
        
        assert field.name == "eqe"
        assert field.description == "外量子效率"
        assert field.field_type == "string"
        assert field.required is False
        assert field.unit == "%"
        assert "EQE" in field.aliases
        assert "EQE" in field.extraction_hints
    
    def test_field_definition_defaults(self):
        """测试字段定义默认值"""
        field = FieldDefinition(
            name="test_field",
            description="测试字段"
        )
        
        assert field.field_type == "string"
        assert field.required is False
        assert field.unit is None
        assert field.aliases == []
        assert field.extraction_hints == []


class TestDeviceFieldConfig:
    """器件字段配置测试"""
    
    def test_device_field_config_creation(self):
        """测试器件字段配置创建"""
        fields = [
            FieldDefinition(name="field1", description="字段1"),
            FieldDefinition(name="field2", description="字段2"),
        ]
        
        config = DeviceFieldConfig(
            fields=fields,
            multi_device_support=True,
            max_devices=6
        )
        
        assert len(config.fields) == 2
        assert config.multi_device_support is True
        assert config.max_devices == 6
    
    def test_device_field_config_defaults(self):
        """测试器件字段配置默认值"""
        config = DeviceFieldConfig(fields=[])
        
        assert config.multi_device_support is True
        assert config.max_devices == 6


class TestExtractionTemplate:
    """提取模板测试"""
    
    def test_get_device_field_names(self):
        """测试获取器件字段名称列表"""
        names = OLED_TEMPLATE.get_device_field_names()
        
        assert "device_label" in names
        assert "structure" in names
        assert "eqe" in names
        assert "cie" in names
        assert "lifetime" in names
    
    def test_get_paper_field_names(self):
        """测试获取论文字段名称列表"""
        names = OLED_TEMPLATE.get_paper_field_names()
        
        assert "title" in names
        assert "authors" in names
        assert "journal_name" in names
        assert "year" in names
    
    def test_get_field_description(self):
        """测试获取字段描述"""
        desc = OLED_TEMPLATE.get_field_description("eqe")
        assert "外量子效率" in desc
        
        desc = OLED_TEMPLATE.get_field_description("title")
        assert "标题" in desc
        
        desc = OLED_TEMPLATE.get_field_description("nonexistent_field")
        assert desc is None
    
    def test_to_json_schema_structure(self):
        """测试 JSON Schema 生成结构"""
        schema = OLED_TEMPLATE.to_json_schema()
        
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "paper_info" in schema["properties"]
        assert "devices" in schema["properties"]
        assert "data_source" in schema["properties"]
        
        assert schema["properties"]["devices"]["type"] == "array"
        assert "items" in schema["properties"]["devices"]
    
    def test_to_json_schema_paper_info_fields(self):
        """测试 JSON Schema 论文字段"""
        schema = OLED_TEMPLATE.to_json_schema()
        paper_props = schema["properties"]["paper_info"]["properties"]
        
        assert "title" in paper_props
        assert "authors" in paper_props
        assert "journal_name" in paper_props
        assert "impact_factor" in paper_props
        assert paper_props["impact_factor"]["type"] == ["number", "null"]
    
    def test_to_json_schema_device_fields(self):
        """测试 JSON Schema 器件字段"""
        schema = OLED_TEMPLATE.to_json_schema()
        device_props = schema["properties"]["devices"]["items"]["properties"]
        
        assert "eqe" in device_props
        assert "cie" in device_props
        assert "lifetime" in device_props
        assert "structure" in device_props
    
    def test_to_json_schema_data_source_fields(self):
        """测试 JSON Schema 数据溯源字段"""
        schema = OLED_TEMPLATE.to_json_schema()
        data_source_props = schema["properties"]["data_source"]["properties"]
        
        assert "eqe_source" in data_source_props
        assert "cie_source" in data_source_props


class TestOLEDTemplate:
    """OLED 模板测试"""
    
    def test_template_basic_info(self):
        """测试模板基本信息"""
        assert OLED_TEMPLATE.template_id == "oled"
        assert "OLED" in OLED_TEMPLATE.template_name
        assert OLED_TEMPLATE.template_type == TemplateType.OLED
    
    def test_device_fields_count(self):
        """测试器件字段数量"""
        assert len(OLED_TEMPLATE.device_config.fields) >= 8
    
    def test_paper_fields_count(self):
        """测试论文字段数量"""
        assert len(OLED_TEMPLATE.paper_config.fields) >= 15
    
    def test_regex_patterns_exist(self):
        """测试正则模式存在"""
        assert "eqe" in OLED_TEMPLATE.regex_patterns
        assert "cie" in OLED_TEMPLATE.regex_patterns
        assert "lifetime" in OLED_TEMPLATE.regex_patterns
        assert "structure" in OLED_TEMPLATE.regex_patterns
        
        for patterns in OLED_TEMPLATE.regex_patterns.values():
            assert len(patterns) > 0
    
    def test_optimization_keywords_exist(self):
        """测试优化关键词存在"""
        assert len(OLED_TEMPLATE.optimization_keywords) > 0
        assert "材料合成" in OLED_TEMPLATE.optimization_keywords
    
    def test_research_type_keywords_exist(self):
        """测试研究类型关键词存在"""
        assert "OLED" in OLED_TEMPLATE.research_type_keywords
        assert "QLED" in OLED_TEMPLATE.research_type_keywords


class TestSolarCellTemplate:
    """太阳能电池模板测试"""
    
    def test_template_basic_info(self):
        """测试模板基本信息"""
        assert SOLAR_CELL_TEMPLATE.template_id == "solar_cell"
        assert "太阳能" in SOLAR_CELL_TEMPLATE.template_name
        assert SOLAR_CELL_TEMPLATE.template_type == TemplateType.SOLAR_CELL
    
    def test_key_device_fields(self):
        """测试关键器件字段"""
        names = SOLAR_CELL_TEMPLATE.get_device_field_names()
        
        assert "pce" in names
        assert "jsc" in names
        assert "voc" in names
        assert "ff" in names
    
    def test_regex_patterns_for_pv_metrics(self):
        """测试光伏指标正则模式"""
        assert "pce" in SOLAR_CELL_TEMPLATE.regex_patterns
        assert "jsc" in SOLAR_CELL_TEMPLATE.regex_patterns
        assert "voc" in SOLAR_CELL_TEMPLATE.regex_patterns
        assert "ff" in SOLAR_CELL_TEMPLATE.regex_patterns


class TestBatteryTemplate:
    """锂电池模板测试"""
    
    def test_template_basic_info(self):
        """测试模板基本信息"""
        assert BATTERY_TEMPLATE.template_id == "battery"
        assert "锂" in BATTERY_TEMPLATE.template_name
        assert BATTERY_TEMPLATE.template_type == TemplateType.BATTERY
    
    def test_key_device_fields(self):
        """测试关键器件字段"""
        names = BATTERY_TEMPLATE.get_device_field_names()
        
        assert "capacity" in names
        assert "cycling_stability" in names
        assert "energy_density" in names
        assert "coulombic_efficiency" in names


class TestSensorTemplate:
    """传感器模板测试"""
    
    def test_template_basic_info(self):
        """测试模板基本信息"""
        assert SENSOR_TEMPLATE.template_id == "sensor"
        assert "传感器" in SENSOR_TEMPLATE.template_name
        assert SENSOR_TEMPLATE.template_type == TemplateType.SENSOR
    
    def test_key_device_fields(self):
        """测试关键器件字段"""
        names = SENSOR_TEMPLATE.get_device_field_names()
        
        assert "sensitivity" in names
        assert "detection_limit" in names
        assert "selectivity" in names
        assert "response_time" in names


class TestTemplateRegistry:
    """模板注册表测试"""
    
    def test_registry_contains_all_templates(self):
        """测试注册表包含所有模板"""
        assert "oled" in TEMPLATE_REGISTRY
        assert "solar_cell" in TEMPLATE_REGISTRY
        assert "battery" in TEMPLATE_REGISTRY
        assert "sensor" in TEMPLATE_REGISTRY
    
    def test_get_template(self):
        """测试获取模板"""
        template = get_template("oled")
        assert template is not None
        assert template.template_id == "oled"
        
        template = get_template("nonexistent")
        assert template is None
    
    def test_get_default_template(self):
        """测试获取默认模板"""
        template = get_default_template()
        assert template is not None
        assert template.template_id == "oled"
        assert template == DEFAULT_TEMPLATE
    
    def test_list_templates(self):
        """测试列出所有模板"""
        templates = list_templates()
        
        assert len(templates) == 4
        ids = [t["id"] for t in templates]
        assert "oled" in ids
        assert "solar_cell" in ids
        assert "battery" in ids
        assert "sensor" in ids
        
        for t in templates:
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "type" in t
    
    def test_register_template(self):
        """测试注册自定义模板"""
        custom_template = ExtractionTemplate(
            template_id="custom_test",
            template_name="自定义测试模板",
            template_type=TemplateType.CUSTOM,
            description="用于测试的自定义模板",
            device_config=DeviceFieldConfig(
                fields=[FieldDefinition(name="test_field", description="测试字段")]
            ),
            paper_config=PaperFieldConfig(
                fields=[FieldDefinition(name="title", description="标题")]
            ),
            data_source_config=DataSourceFieldConfig(enabled=False),
            prompt_template="test prompt"
        )
        
        register_template(custom_template)
        
        assert "custom_test" in TEMPLATE_REGISTRY
        assert get_template("custom_test") == custom_template
        
        del TEMPLATE_REGISTRY["custom_test"]


class TestDynamicTemplateGenerator:
    """动态模板生成器测试"""
    
    def test_generator_creation(self):
        """测试生成器创建"""
        generator = DynamicTemplateGenerator()
        assert generator.llm_client is None
        
        mock_client = Mock()
        generator = DynamicTemplateGenerator(llm_client=mock_client)
        assert generator.llm_client == mock_client
    
    def test_generate_template_without_llm(self):
        """测试无 LLM 时生成模板"""
        generator = DynamicTemplateGenerator()
        
        result = generator.generate_template(
            research_field="Test Field",
            keywords=["test"],
            metrics=["metric1"]
        )
        
        assert result is None
    
    def test_generate_template_with_llm(self):
        """测试有 LLM 时生成模板"""
        mock_client = Mock()
        mock_client.generate_json.return_value = {
            "template_id": "test_field",
            "template_name": "测试领域",
            "description": "测试描述",
            "device_fields": [
                {
                    "name": "metric1",
                    "description": "指标1",
                    "unit": "unit",
                    "aliases": ["m1"],
                    "extraction_hints": ["hint1"]
                }
            ],
            "paper_fields": [
                {"name": "title", "description": "标题"}
            ],
            "data_source_fields": ["metric1_source"]
        }
        
        generator = DynamicTemplateGenerator(llm_client=mock_client)
        
        result = generator.generate_template(
            research_field="Test Field",
            keywords=["test"],
            metrics=["metric1"]
        )
        
        assert result is not None
        assert result.template_id == "test_field"
        assert result.template_type == TemplateType.DYNAMIC
        assert len(result.device_config.fields) == 1
        assert result.device_config.fields[0].name == "metric1"
    
    def test_generate_template_with_excel_template(self):
        """测试使用 Excel 模板生成"""
        mock_client = Mock()
        mock_client.generate_json.return_value = {
            "template_id": "excel_based",
            "template_name": "Excel 模板",
            "description": "基于 Excel 的模板",
            "device_fields": [],
            "paper_fields": [],
            "data_source_fields": []
        }
        
        generator = DynamicTemplateGenerator(llm_client=mock_client)
        
        result = generator.generate_template(
            research_field="Test Field",
            excel_template="col1,col2,col3\nval1,val2,val3"
        )
        
        assert result is not None
        mock_client.generate_json.assert_called_once()
    
    def test_generate_template_handles_exception(self):
        """测试生成模板异常处理"""
        mock_client = Mock()
        mock_client.generate_json.side_effect = Exception("Test error")
        
        generator = DynamicTemplateGenerator(llm_client=mock_client)
        
        result = generator.generate_template(research_field="Test Field")
        
        assert result is None
    
    def test_build_generation_prompt(self):
        """测试构建生成 Prompt"""
        generator = DynamicTemplateGenerator()
        
        prompt = generator._build_generation_prompt(
            research_field="量子点 LED",
            keywords=["QD", "LED"],
            metrics=["EQE", "亮度"],
            excel_template=None
        )
        
        assert "量子点 LED" in prompt
        assert "QD" in prompt
        assert "LED" in prompt
        assert "EQE" in prompt
        assert "亮度" in prompt
        assert "JSON" in prompt
    
    def test_parse_template_response(self):
        """测试解析模板响应"""
        generator = DynamicTemplateGenerator()
        
        response = {
            "template_id": "custom",
            "template_name": "自定义模板",
            "description": "测试描述",
            "device_fields": [
                {
                    "name": "field1",
                    "description": "字段1",
                    "unit": "unit1",
                    "aliases": ["alias1"],
                    "extraction_hints": ["hint1"]
                }
            ],
            "paper_fields": [
                {"name": "title", "description": "标题"}
            ],
            "data_source_fields": ["field1_source"]
        }
        
        result = generator._parse_template_response(response, "Test Field")
        
        assert result is not None
        assert result.template_id == "custom"
        assert result.template_name == "自定义模板"
        assert result.template_type == TemplateType.DYNAMIC
        assert len(result.device_config.fields) == 1
        assert result.device_config.fields[0].name == "field1"
        assert len(result.paper_config.fields) == 1
        assert result.data_source_config.enabled is True


class TestTemplateType:
    """模板类型枚举测试"""
    
    def test_template_type_values(self):
        """测试模板类型值"""
        assert TemplateType.OLED.value == "oled"
        assert TemplateType.SOLAR_CELL.value == "solar_cell"
        assert TemplateType.BATTERY.value == "battery"
        assert TemplateType.SENSOR.value == "sensor"
        assert TemplateType.CUSTOM.value == "custom"
        assert TemplateType.DYNAMIC.value == "dynamic"


class TestTemplateIntegration:
    """模板集成测试"""
    
    def test_all_templates_have_required_fields(self):
        """测试所有模板都有必需字段"""
        templates = [OLED_TEMPLATE, SOLAR_CELL_TEMPLATE, BATTERY_TEMPLATE, SENSOR_TEMPLATE]
        
        for template in templates:
            assert template.template_id is not None
            assert template.template_name is not None
            assert template.template_type is not None
            assert template.description is not None
            assert template.device_config is not None
            assert template.paper_config is not None
            assert template.prompt_template is not None
    
    def test_all_templates_generate_valid_schema(self):
        """测试所有模板生成有效 Schema"""
        templates = [OLED_TEMPLATE, SOLAR_CELL_TEMPLATE, BATTERY_TEMPLATE, SENSOR_TEMPLATE]
        
        for template in templates:
            schema = template.to_json_schema()
            
            assert schema["type"] == "object"
            assert "paper_info" in schema["properties"]
            assert "devices" in schema["properties"]
            assert "data_source" in schema["properties"]
            assert "required" in schema
            assert "paper_info" in schema["required"]
            assert "devices" in schema["required"]
    
    def test_all_templates_have_paper_basic_fields(self):
        """测试所有模板都有论文基本字段"""
        templates = [OLED_TEMPLATE, SOLAR_CELL_TEMPLATE, BATTERY_TEMPLATE, SENSOR_TEMPLATE]
        basic_fields = ["title", "authors", "journal_name", "year"]
        
        for template in templates:
            names = template.get_paper_field_names()
            for field in basic_fields:
                assert field in names, f"{template.template_id} 缺少字段 {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
