# 功能增强迭代 Spec

## Why
PaperInsight 当前主要支持 OLED/LED/QLED 器件论文，领域局限明显；桌面应用功能相对简单，用户体验待提升；LLM 提取准确率约 85-90%，仍有改进空间。本次迭代旨在扩展研究领域支持、增强桌面应用功能、改进数据提取准确性，提升产品竞争力和用户体验。

## What Changes
- 新增太阳能电池（Perovskite Solar Cells）提取模板
- 新增锂电池（Li-ion Battery）提取模板
- 新增传感器（Sensors）提取模板
- 支持自定义提取模板配置
- 桌面应用添加实时进度显示
- 桌面应用支持拖拽上传 PDF
- 桌面应用添加结果预览和筛选功能
- 桌面应用支持导出格式选择
- 桌面应用添加历史记录管理
- 优化 Prompt 工程提升提取准确率
- 引入 Few-shot 学习机制
- 支持用户反馈修正功能

## Impact
- Affected specs: 核心提取能力、桌面应用交互、数据模型
- Affected code: 
  - `paperinsight/core/extractor.py` - 提取逻辑
  - `paperinsight/llm/prompt_templates.py` - Prompt 模板
  - `paperinsight/models/schemas.py` - 数据模型
  - `desktop/src/components/` - 桌面应用组件
  - `desktop/src/App.jsx` - 主应用逻辑

## ADDED Requirements

### Requirement: 扩展研究领域支持
系统 SHALL 支持多种研究领域的论文提取，包括但不限于 OLED/LED、太阳能电池、锂电池、传感器等。

#### Scenario: 太阳能电池论文提取
- **WHEN** 用户选择太阳能电池模板并上传相关论文
- **THEN** 系统应提取 PCE、Jsc、Voc、FF 等关键器件参数

#### Scenario: 锂电池论文提取
- **WHEN** 用户选择锂电池模板并上传相关论文
- **THEN** 系统应提取容量、循环稳定性、能量密度等关键参数

#### Scenario: 自定义模板配置
- **WHEN** 用户在配置文件中定义自定义提取模板
- **THEN** 系统应使用自定义模板进行数据提取

### Requirement: 桌面应用实时进度显示
系统 SHALL 在桌面应用中提供实时处理进度反馈。

#### Scenario: 批量处理进度显示
- **WHEN** 用户批量上传多个 PDF 文件进行处理
- **THEN** 系统应显示当前处理文件名、已完成数量、总数量和预估剩余时间

#### Scenario: 单文件处理阶段显示
- **WHEN** 系统处理单个 PDF 文件
- **THEN** 系统应显示当前处理阶段（解析中、提取中、获取影响因子中）

### Requirement: 桌面应用拖拽上传
系统 SHALL 支持通过拖拽方式上传 PDF 文件。

#### Scenario: 拖拽上传文件
- **WHEN** 用户将 PDF 文件拖拽到应用指定区域
- **THEN** 系统应识别并添加文件到待处理列表

#### Scenario: 拖拽多文件
- **WHEN** 用户同时拖拽多个 PDF 文件
- **THEN** 系统应将所有文件添加到待处理列表

### Requirement: 结果预览和筛选
系统 SHALL 在桌面应用中提供结果预览和筛选功能。

#### Scenario: 结果预览
- **WHEN** 处理完成后
- **THEN** 用户可在应用内预览提取结果表格

#### Scenario: 结果筛选
- **WHEN** 用户输入筛选条件
- **THEN** 系统应实时过滤显示符合条件的结果

### Requirement: 导出格式选择
系统 SHALL 支持多种导出格式选择。

#### Scenario: 选择导出格式
- **WHEN** 用户点击导出按钮
- **THEN** 系统应提供 Excel、JSON、CSV 等格式选项

### Requirement: 历史记录管理
系统 SHALL 在桌面应用中提供历史记录管理功能。

#### Scenario: 查看历史记录
- **WHEN** 用户打开历史记录面板
- **THEN** 系统应显示所有历史处理记录列表

#### Scenario: 重新打开历史结果
- **WHEN** 用户点击某条历史记录
- **THEN** 系统应加载该记录的处理结果

### Requirement: Prompt 工程优化
系统 SHALL 通过优化 Prompt 提升数据提取准确率。

#### Scenario: 结构化 Prompt
- **WHEN** 系统调用 LLM 进行提取
- **THEN** 应使用结构化、层次化的 Prompt 模板

#### Scenario: Few-shot 学习
- **WHEN** 系统进行数据提取
- **THEN** 应在 Prompt 中包含典型示例以引导 LLM 输出

### Requirement: 用户反馈修正
系统 SHALL 支持用户对提取结果进行反馈修正。

#### Scenario: 修正提取结果
- **WHEN** 用户发现提取结果有误并进行修正
- **THEN** 系统应保存修正后的结果

#### Scenario: 反馈学习
- **WHEN** 用户提交修正反馈
- **THEN** 系统应记录反馈用于后续优化

## MODIFIED Requirements

### Requirement: 提取模板系统
系统 SHALL 使用配置化的提取模板，支持多种研究领域。

**原有实现**: 硬编码 OLED/LED/QLED 器件字段

**修改后**: 配置化模板系统，支持动态扩展研究领域
