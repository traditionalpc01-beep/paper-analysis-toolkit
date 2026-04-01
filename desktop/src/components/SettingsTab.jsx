import React from 'react';
import { getNestedValue, setNestedValue, formatProviderLabel, engineModeLabel } from '../utils';

function SettingsTab({
  config,
  setConfig,
  saveState,
  onSaveSettings,
  onApplyRecommendedSetup
}) {
  const updateConfig = (path, value) => {
    setConfig((current) => setNestedValue(current, path, value));
  };

  return (
    <div className="tab-content settings">
      <section className="hero">
        <div>
          <h1>把 API Key 和运行模式收进设置页</h1>
          <p>所有常用配置项都已经收进图形界面，包括 LLM 服务、MinerU、缓存策略和系统 Python 兜底模式。</p>
        </div>
      </section>

      <section className="settings-section">
        <h2>LLM 服务</h2>
        <div className="grid">
          <label className="field">
            <span>服务提供商</span>
            <select value={getNestedValue(config, 'llm.provider', 'longcat')} onChange={(e) => updateConfig('llm.provider', e.target.value)}>
              <option value="longcat">Longcat</option>
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI</option>
              <option value="wenxin">文心一言</option>
            </select>
          </label>
          <label className="field">
            <span>启用 LLM</span>
            <select value={getNestedValue(config, 'llm.enabled', true)} onChange={(e) => updateConfig('llm.enabled', e.target.value === 'true')}>
              <option value="true">启用</option>
              <option value="false">禁用</option>
            </select>
          </label>
        </div>
        <div className="grid">
          <label className="field">
            <span>API Key</span>
            <input type="password" value={getNestedValue(config, 'llm.api_key', '')} onChange={(e) => updateConfig('llm.api_key', e.target.value)} placeholder="请输入 API Key" />
          </label>
          <label className="field">
            <span>模型名称</span>
            <input value={getNestedValue(config, 'llm.model', 'LongCat-Flash-Chat')} onChange={(e) => updateConfig('llm.model', e.target.value)} placeholder="请输入模型名称" />
          </label>
        </div>
        <div className="grid">
          <label className="field">
            <span>连接地址 / 中转地址</span>
            <input value={getNestedValue(config, 'llm.base_url', '')} onChange={(e) => updateConfig('llm.base_url', e.target.value)} placeholder="默认留空，使用官方地址" />
          </label>
        </div>
        <div className="grid">
          <label className="field">
            <span>文心一言 Client ID</span>
            <input type="password" value={getNestedValue(config, 'llm.wenxin.client_id', '')} onChange={(e) => updateConfig('llm.wenxin.client_id', e.target.value)} placeholder="仅文心一言需要" />
          </label>
          <label className="field">
            <span>文心一言 Client Secret</span>
            <input type="password" value={getNestedValue(config, 'llm.wenxin.client_secret', '')} onChange={(e) => updateConfig('llm.wenxin.client_secret', e.target.value)} placeholder="仅文心一言需要" />
          </label>
        </div>
      </section>

      <section className="settings-section">
        <h2>MinerU 配置</h2>
        <div className="grid">
          <label className="field">
            <span>启用 MinerU</span>
            <select value={getNestedValue(config, 'mineru.enabled', true)} onChange={(e) => updateConfig('mineru.enabled', e.target.value === 'true')}>
              <option value="true">启用</option>
              <option value="false">禁用</option>
            </select>
          </label>
          <label className="field">
            <span>MinerU 模式</span>
            <select value={getNestedValue(config, 'mineru.mode', 'api')} onChange={(e) => updateConfig('mineru.mode', e.target.value)}>
              <option value="api">API 模式</option>
              <option value="cli">CLI 模式</option>
            </select>
          </label>
        </div>
        <div className="grid">
          <label className="field">
            <span>MinerU Token</span>
            <input type="password" value={getNestedValue(config, 'mineru.token', '')} onChange={(e) => updateConfig('mineru.token', e.target.value)} placeholder="API 模式需要" />
          </label>
          <label className="field">
            <span>模型版本</span>
            <select value={getNestedValue(config, 'mineru.model_version', 'vlm')} onChange={(e) => updateConfig('mineru.model_version', e.target.value)}>
              <option value="vlm">vlm</option>
              <option value="pipeline">pipeline</option>
              <option value="MinerU-HTML">MinerU-HTML</option>
            </select>
          </label>
        </div>
        <div className="grid">
          <label className="field">
            <span>输出格式</span>
            <select value={getNestedValue(config, 'mineru.output_format', 'markdown')} onChange={(e) => updateConfig('mineru.output_format', e.target.value)}>
              <option value="markdown">markdown</option>
              <option value="json">json</option>
            </select>
          </label>
          <label className="field">
            <span>解析方式</span>
            <select value={getNestedValue(config, 'mineru.method', 'auto')} onChange={(e) => updateConfig('mineru.method', e.target.value)}>
              <option value="auto">auto</option>
              <option value="txt">txt</option>
              <option value="ocr">ocr</option>
            </select>
          </label>
        </div>
      </section>

      <section className="settings-section">
        <h2>运行引擎</h2>
        <div className="grid">
          <label className="field">
            <span>引擎模式</span>
            <select value={getNestedValue(config, 'desktop.engine.mode', 'bundled')} onChange={(e) => updateConfig('desktop.engine.mode', e.target.value)}>
              <option value="bundled">内置后端 (bundled)</option>
              <option value="system_python">系统 Python</option>
              <option value="manual_check">需手动检查</option>
            </select>
          </label>
          <label className="field">
            <span>Python 路径</span>
            <input value={getNestedValue(config, 'desktop.engine.python_path', '')} onChange={(e) => updateConfig('desktop.engine.python_path', e.target.value)} placeholder="系统 Python 模式需要" />
          </label>
        </div>
        <button className="ghost" onClick={onApplyRecommendedSetup}>应用推荐启动设置</button>
      </section>

      <section className="settings-section">
        <h2>输出设置</h2>
        <div className="grid">
          <label className="field">
            <span>导出格式</span>
            <select value={getNestedValue(config, 'output.format', ['excel']).includes('json')} onChange={(e) => updateConfig('output.format', e.target.value === 'true' ? ['excel', 'json'] : ['excel'])}>
              <option value="false">仅 Excel</option>
              <option value="true">Excel + JSON</option>
            </select>
          </label>
          <label className="field">
            <span>重命名 PDF</span>
            <select value={getNestedValue(config, 'output.rename_pdfs', false)} onChange={(e) => updateConfig('output.rename_pdfs', e.target.value === 'true')}>
              <option value="false">否</option>
              <option value="true">是</option>
            </select>
          </label>
        </div>
        <div className="grid">
          <label className="field">
            <span>双语输出</span>
            <select value={getNestedValue(config, 'output.bilingual_text', false)} onChange={(e) => updateConfig('output.bilingual_text', e.target.value === 'true')}>
              <option value="false">否</option>
              <option value="true">是</option>
            </select>
          </label>
        </div>
      </section>

      <section className="settings-actions">
        <button className="primary" onClick={onSaveSettings} disabled={saveState.saving}>
          {saveState.saving ? '保存中...' : '保存设置'}
        </button>
        {saveState.message && <div className="save-message">{saveState.message}</div>}
        {saveState.error && <div className="save-error">{saveState.error}</div>}
      </section>
    </div>
  );
}

export default SettingsTab;