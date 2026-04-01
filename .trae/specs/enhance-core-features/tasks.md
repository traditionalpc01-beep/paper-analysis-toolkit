# Tasks

- [x] Task 1: 扩展研究领域支持 - 创建配置化提取模板系统
  - [x] SubTask 1.1: 设计提取模板配置数据结构
  - [x] SubTask 1.2: 创建太阳能电池（Perovskite Solar Cells）模板配置
  - [x] SubTask 1.3: 创建锂电池（Li-ion Battery）模板配置
  - [x] SubTask 1.4: 创建传感器（Sensors）模板配置
  - [x] SubTask 1.5: 修改 extractor.py 支持模板选择和加载
  - [x] SubTask 1.6: 更新 schemas.py 支持新领域数据模型
  - [x] SubTask 1.7: 更新 CLI 支持模板选择参数

- [ ] Task 2: 桌面应用增强 - 实时进度显示
  - [ ] SubTask 2.1: 设计进度数据结构和通信协议
  - [ ] SubTask 2.2: 修改 desktop_bridge.py 支持进度回调
  - [ ] SubTask 2.3: 在 Electron main.js 中实现 WebSocket 或 IPC 进度推送
  - [ ] SubTask 2.4: 创建 ProgressIndicator 组件显示处理阶段
  - [ ] SubTask 2.5: 创建 BatchProgressBar 组件显示批量进度

- [x] Task 3: 桌面应用增强 - 拖拽上传功能
  - [x] SubTask 3.1: 创建 DropZone 组件支持拖拽区域
  - [x] SubTask 3.2: 实现文件类型验证（仅接受 PDF）
  - [x] SubTask 3.3: 实现多文件拖拽处理逻辑
  - [x] SubTask 3.4: 添加拖拽视觉反馈效果

- [ ] Task 4: 桌面应用增强 - 结果预览和筛选
  - [ ] SubTask 4.1: 创建 ResultsPreview 组件显示结果表格
  - [ ] SubTask 4.2: 实现表格排序功能
  - [ ] SubTask 4.3: 创建 FilterBar 组件支持条件筛选
  - [ ] SubTask 4.4: 实现实时筛选逻辑

- [x] Task 5: 桌面应用增强 - 导出格式选择
  - [x] SubTask 5.1: 创建 ExportModal 组件提供格式选项
  - [x] SubTask 5.2: 实现 CSV 导出功能
  - [x] SubTask 5.3: 更新导出逻辑支持用户选择格式

- [x] Task 6: 桌面应用增强 - 历史记录管理
  - [x] SubTask 6.1: 设计历史记录数据存储方案（本地数据库或文件）
  - [x] SubTask 6.2: 创建 HistoryManager 服务管理历史记录
  - [x] SubTask 6.3: 创建 HistoryPanel 组件显示历史列表
  - [x] SubTask 6.4: 实现历史记录加载和删除功能

- [ ] Task 7: Prompt 工程优化
  - [ ] SubTask 7.1: 重构 prompt_templates.py 使用结构化模板
  - [ ] SubTask 7.2: 为每个领域创建 Few-shot 示例库
  - [ ] SubTask 7.3: 实现 Prompt 组装逻辑支持动态示例注入
  - [ ] SubTask 7.4: 添加多轮对话验证机制

- [ ] Task 8: 用户反馈修正功能
  - [ ] SubTask 8.1: 创建 FeedbackModal 组件支持结果修正
  - [ ] SubTask 8.2: 实现修正结果保存逻辑
  - [ ] SubTask 8.3: 创建反馈数据存储结构
  - [ ] SubTask 8.4: 实现反馈数据导出功能

- [ ] Task 9: 测试和文档
  - [ ] SubTask 9.1: 为新模板系统编写单元测试
  - [ ] SubTask 9.2: 为桌面应用新功能编写集成测试
  - [ ] SubTask 9.3: 更新用户文档说明新功能使用方法
  - [ ] SubTask 9.4: 更新配置示例文件

# Task Dependencies
- [Task 2] depends on [Task 1] (进度显示需要知道处理阶段信息)
- [Task 4] depends on [Task 1] (结果预览需要支持新数据模型)
- [Task 7] depends on [Task 1] (Prompt 优化需要与模板系统配合)
- [Task 8] depends on [Task 4] (反馈修正需要结果预览功能)
- [Task 9] depends on [Task 1-8] (测试需要所有功能完成)
