import React, { useEffect, useMemo, useState } from 'react';

const tabs = [
  { id: 'analyze', label: '分析工作台' },
  { id: 'settings', label: '服务配置' }
];

const initialRunOptions = {
  pdfDir: '',
  outputDir: '',
  recursive: true,
  maxPages: 0,
  mode: 'auto',
  exportJson: false,
  noCache: false,
  renamePdfs: false,
  bilingual: false
};

function cloneConfig(config) {
  return JSON.parse(JSON.stringify(config));
}

function getNestedValue(obj, path, defaultValue = '') {
  return path.split('.').reduce((acc, key) => {
    if (acc && typeof acc === 'object' && key in acc) {
      return acc[key];
    }
    return defaultValue;
  }, obj);
}

function setNestedValue(obj, path, value) {
  const keys = path.split('.');
  const next = cloneConfig(obj);
  let current = next;
  for (const key of keys.slice(0, -1)) {
    if (!current[key] || typeof current[key] !== 'object') {
      current[key] = {};
    }
    current = current[key];
  }
  current[keys[keys.length - 1]] = value;
  return next;
}

function formatProviderLabel(provider) {
  const mapping = {
    longcat: 'Longcat',
    deepseek: 'DeepSeek',
    openai: 'OpenAI',
    wenxin: '文心一言'
  };
  return mapping[provider] || provider;
}

function modeLabel(mode) {
  const mapping = {
    auto: '自动模式',
    api: '智能 API',
    regex: '正则兜底'
  };
  return mapping[mode] || mode;
}

function buildLogLine(event) {
  if (event.type === 'file-complete') {
    return event.status === 'success'
      ? `完成 ${event.file}${event.journal ? ` · ${event.journal}` : ''}`
      : `失败 ${event.file} · ${event.message}`;
  }
  if (event.type === 'progress') {
    return `处理中 ${event.currentFile}`;
  }
  if (event.type === 'log') {
    return event.message;
  }
  if (event.type === 'completed') {
    return `任务完成：成功 ${event.stats.successCount} / ${event.stats.pdfCount}`;
  }
  if (event.type === 'cancelled') {
    return event.message;
  }
  if (event.type === 'failed') {
    return event.message;
  }
  return `${event.type}`;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('analyze');
  const [config, setConfig] = useState(null);
  const [meta, setMeta] = useState(null);
  const [env, setEnv] = useState(null);
  const [runOptions, setRunOptions] = useState(initialRunOptions);
  const [loadState, setLoadState] = useState({ loading: true, error: '' });
  const [saveState, setSaveState] = useState({ saving: false, message: '', error: '' });
  const [job, setJob] = useState({
    running: false,
    status: 'idle',
    total: 0,
    completed: 0,
    currentFile: '',
    logs: [],
    stats: null,
    outputDir: '',
    launch: null
  });

  useEffect(() => {
    let unsubscribe = () => {};

    async function bootstrap() {
      try {
        const response = await window.paperInsight.getConfig();
        setConfig(response.config);
        setMeta(response.meta);
        setEnv(response.env);
        setRunOptions((current) => ({
          ...current,
          pdfDir: getNestedValue(response.config, 'desktop.ui.last_pdf_dir', ''),
          outputDir: getNestedValue(response.config, 'desktop.ui.last_output_dir', ''),
          exportJson: getNestedValue(response.config, 'output.format', []).includes('json'),
          renamePdfs: Boolean(getNestedValue(response.config, 'output.rename_pdfs', false)),
          bilingual: Boolean(getNestedValue(response.config, 'output.bilingual_text', false))
        }));
      } catch (error) {
        setLoadState({ loading: false, error: error.message || '加载失败' });
        return;
      }

      unsubscribe = window.paperInsight.onAnalysisEvent((event) => {
        setJob((current) => {
          const nextLogs = [
            {
              id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
              text: buildLogLine(event),
              type: event.type
            },
            ...current.logs
          ].slice(0, 120);

          if (event.type === 'started') {
            return {
              ...current,
              running: true,
              status: 'running',
              total: event.total,
              completed: 0,
              currentFile: '',
              outputDir: event.outputDir,
              launch: event.launch,
              logs: nextLogs,
              stats: null
            };
          }

          if (event.type === 'progress') {
            return {
              ...current,
              currentFile: event.currentFile,
              completed: event.completed,
              total: event.total,
              logs: nextLogs
            };
          }

          if (event.type === 'file-complete') {
            return {
              ...current,
              completed: event.completed,
              total: event.total,
              logs: nextLogs
            };
          }

          if (event.type === 'completed') {
            return {
              ...current,
              running: false,
              status: event.stats.status === 'no_files' ? 'idle' : 'completed',
              completed: event.stats.pdfCount,
              total: event.stats.pdfCount,
              stats: event.stats,
              logs: nextLogs
            };
          }

          if (event.type === 'failed' || event.type === 'cancelled') {
            return {
              ...current,
              running: false,
              status: event.type === 'failed' ? 'failed' : 'cancelled',
              logs: nextLogs
            };
          }

          return {
            ...current,
            logs: nextLogs
          };
        });
      });

      setLoadState({ loading: false, error: '' });
    }

    bootstrap();
    return () => unsubscribe();
  }, []);

  const progressPercent = useMemo(() => {
    if (!job.total) {
      return 0;
    }
    return Math.min(100, Math.round((job.completed / job.total) * 100));
  }, [job.completed, job.total]);

  async function chooseDirectory(target) {
    const selected = await window.paperInsight.chooseDirectory({
      title: target === 'pdfDir' ? '选择论文目录' : '选择输出目录',
      defaultPath: runOptions[target] || undefined
    });

    if (!selected) {
      return;
    }

    setRunOptions((current) => ({
      ...current,
      [target]: selected,
      ...(target === 'pdfDir' && !current.outputDir ? { outputDir: `${selected}/输出结果` } : {})
    }));
  }

  function updateConfig(path, value) {
    setConfig((current) => setNestedValue(current, path, value));
  }

  async function saveSettings() {
    setSaveState({ saving: true, message: '', error: '' });
    try {
      const nextConfig = setNestedValue(config, 'desktop.ui.last_pdf_dir', runOptions.pdfDir);
      const finalConfig = setNestedValue(nextConfig, 'desktop.ui.last_output_dir', runOptions.outputDir);
      const response = await window.paperInsight.saveConfig(finalConfig);
      setConfig(response.config);
      setSaveState({ saving: false, message: '设置已保存。', error: '' });
    } catch (error) {
      setSaveState({ saving: false, message: '', error: error.message || '保存失败' });
    }
  }

  async function startAnalysis() {
    if (!runOptions.pdfDir) {
      setJob((current) => ({
        ...current,
        status: 'failed',
        logs: [{ id: `${Date.now()}`, text: '请先选择包含 PDF 的目录。', type: 'failed' }, ...current.logs]
      }));
      return;
    }

    setJob({
      running: false,
      status: 'preparing',
      total: 0,
      completed: 0,
      currentFile: '',
      logs: [],
      stats: null,
      outputDir: runOptions.outputDir,
      launch: null
    });

    try {
      await window.paperInsight.startAnalysis({
        ...runOptions,
        engine: getNestedValue(config, 'desktop.engine', {})
      });
    } catch (error) {
      setJob((current) => ({
        ...current,
        running: false,
        status: 'failed',
        logs: [{ id: `${Date.now()}`, text: error.message || '启动失败', type: 'failed' }, ...current.logs]
      }));
    }
  }

  async function cancelAnalysis() {
    await window.paperInsight.cancelAnalysis();
  }

  async function openOutputDir() {
    if (!job.outputDir) {
      return;
    }
    await window.paperInsight.openPath(job.outputDir);
  }

  if (loadState.loading) {
    return <div className="loading-shell">正在启动 PaperInsight Desktop...</div>;
  }

  if (loadState.error || !config) {
    return <div className="loading-shell error">加载失败：{loadState.error}</div>;
  }

  const provider = getNestedValue(config, 'llm.provider', 'deepseek');
  const engineMode = getNestedValue(config, 'desktop.engine.mode', 'bundled');

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="brand-mark">PI</div>
          <h1>PaperInsight</h1>
          <p>面向论文批处理的桌面分析台，默认内置引擎，可按需切换到系统 Python。</p>
        </div>

        <div className="status-stack">
          <div className="status-card warm">
            <span>引擎模式</span>
            <strong>{engineMode === 'bundled' ? '内置后端' : '系统 Python'}</strong>
          </div>
          <div className="status-card">
            <span>LLM 提供商</span>
            <strong>{formatProviderLabel(provider)}</strong>
          </div>
          <div className="status-card cool">
            <span>当前版本</span>
            <strong>{meta?.version || env?.version || '未知'}</strong>
          </div>
        </div>

        <nav className="nav-list">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={tab.id === activeTab ? 'nav-item active' : 'nav-item'}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-meta">
          <div>配置文件</div>
          <strong>{meta?.configPath || '-'}</strong>
          <div className="small-note">Python: {env?.pythonExecutable || meta?.pythonExecutable || '-'}</div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="hero-card">
          <div>
            <span className="eyebrow">Desktop MVP</span>
            <h2>{activeTab === 'analyze' ? '用点选代替命令行' : '把 API Key 和运行模式收进设置页'}</h2>
            <p>
              第一阶段先打通目录选择、任务执行和结果回看；第二阶段配置直接写入本地
              <code> ~/.paperinsight/config.yaml </code>
              并保留系统 Python 高级入口。
            </p>
          </div>
          <div className="hero-pills">
            <span>{modeLabel(runOptions.mode)}</span>
            <span>{runOptions.recursive ? '递归扫描' : '仅当前目录'}</span>
            <span>{runOptions.exportJson ? 'Excel + JSON' : '仅 Excel'}</span>
          </div>
        </header>

        {activeTab === 'analyze' ? (
          <section className="content-grid">
            <article className="panel-card">
              <div className="panel-head">
                <div>
                  <span className="panel-kicker">Step 1</span>
                  <h3>输入与输出</h3>
                </div>
              </div>
              <label className="field">
                <span>论文目录</span>
                <div className="path-picker">
                  <input
                    value={runOptions.pdfDir}
                    onChange={(event) => setRunOptions((current) => ({ ...current, pdfDir: event.target.value }))}
                    placeholder="选择包含 PDF 的文件夹"
                  />
                  <button onClick={() => chooseDirectory('pdfDir')}>选择目录</button>
                </div>
              </label>
              <label className="field">
                <span>输出目录</span>
                <div className="path-picker">
                  <input
                    value={runOptions.outputDir}
                    onChange={(event) => setRunOptions((current) => ({ ...current, outputDir: event.target.value }))}
                    placeholder="默认写入 论文目录/输出结果"
                  />
                  <button onClick={() => chooseDirectory('outputDir')}>选择目录</button>
                </div>
              </label>
            </article>

            <article className="panel-card">
              <div className="panel-head">
                <div>
                  <span className="panel-kicker">Step 2</span>
                  <h3>运行选项</h3>
                </div>
              </div>
              <div className="option-grid">
                <label className="field compact">
                  <span>处理模式</span>
                  <select value={runOptions.mode} onChange={(event) => setRunOptions((current) => ({ ...current, mode: event.target.value }))}>
                    <option value="auto">自动模式</option>
                    <option value="api">智能 API</option>
                    <option value="regex">正则兜底</option>
                  </select>
                </label>
                <label className="field compact">
                  <span>最大页数</span>
                  <input
                    type="number"
                    min="0"
                    value={runOptions.maxPages}
                    onChange={(event) => setRunOptions((current) => ({ ...current, maxPages: Number(event.target.value || 0) }))}
                  />
                </label>
              </div>
              <div className="toggle-grid">
                <label><input type="checkbox" checked={runOptions.recursive} onChange={(event) => setRunOptions((current) => ({ ...current, recursive: event.target.checked }))} />递归扫描子目录</label>
                <label><input type="checkbox" checked={runOptions.exportJson} onChange={(event) => setRunOptions((current) => ({ ...current, exportJson: event.target.checked }))} />额外导出 JSON</label>
                <label><input type="checkbox" checked={runOptions.renamePdfs} onChange={(event) => setRunOptions((current) => ({ ...current, renamePdfs: event.target.checked }))} />处理后重命名 PDF</label>
                <label><input type="checkbox" checked={runOptions.noCache} onChange={(event) => setRunOptions((current) => ({ ...current, noCache: event.target.checked }))} />本次禁用缓存</label>
                <label><input type="checkbox" checked={runOptions.bilingual} onChange={(event) => setRunOptions((current) => ({ ...current, bilingual: event.target.checked }))} />输出中英双语字段</label>
              </div>
            </article>

            <article className="panel-card wide">
              <div className="panel-head split">
                <div>
                  <span className="panel-kicker">Step 3</span>
                  <h3>执行状态</h3>
                </div>
                <div className="action-row">
                  <button className="ghost" disabled={!job.outputDir} onClick={openOutputDir}>打开输出目录</button>
                  {job.running ? (
                    <button className="danger" onClick={cancelAnalysis}>取消任务</button>
                  ) : (
                    <button className="primary" onClick={startAnalysis}>开始分析</button>
                  )}
                </div>
              </div>
              <div className="progress-block">
                <div className="progress-meta">
                  <strong>{job.running ? '正在执行' : job.status === 'completed' ? '已完成' : '待启动'}</strong>
                  <span>{job.currentFile || '等待任务开始'}</span>
                </div>
                <div className="progress-track">
                  <div className="progress-bar" style={{ width: `${progressPercent}%` }} />
                </div>
                <div className="progress-numbers">{job.completed} / {job.total || 0}</div>
              </div>

              {job.stats ? (
                <div className="stat-grid">
                  <div><span>PDF 总数</span><strong>{job.stats.pdfCount}</strong></div>
                  <div><span>成功</span><strong>{job.stats.successCount}</strong></div>
                  <div><span>失败</span><strong>{job.stats.errorCount}</strong></div>
                  <div><span>重命名</span><strong>{job.stats.renamedCount}</strong></div>
                </div>
              ) : null}

              <div className="log-panel">
                {job.logs.length ? job.logs.map((entry) => (
                  <div key={entry.id} className={`log-line ${entry.type}`}>{entry.text}</div>
                )) : <div className="empty-state">任务日志会显示在这里。</div>}
              </div>
            </article>
          </section>
        ) : (
          <section className="content-grid settings-grid">
            <article className="panel-card">
              <div className="panel-head">
                <div>
                  <span className="panel-kicker">LLM</span>
                  <h3>服务凭据</h3>
                </div>
              </div>
              <div className="toggle-grid single">
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'llm.enabled', true))} onChange={(event) => updateConfig('llm.enabled', event.target.checked)} />启用 LLM 语义提取</label>
              </div>
              <label className="field compact">
                <span>提供商</span>
                <select value={provider} onChange={(event) => updateConfig('llm.provider', event.target.value)}>
                  <option value="longcat">Longcat</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai">OpenAI</option>
                  <option value="wenxin">文心一言</option>
                </select>
              </label>
              {provider === 'wenxin' ? (
                <>
                  <label className="field compact">
                    <span>Client ID</span>
                    <input type="password" value={getNestedValue(config, 'llm.wenxin.client_id', '')} onChange={(event) => updateConfig('llm.wenxin.client_id', event.target.value)} />
                  </label>
                  <label className="field compact">
                    <span>Client Secret</span>
                    <input type="password" value={getNestedValue(config, 'llm.wenxin.client_secret', '')} onChange={(event) => updateConfig('llm.wenxin.client_secret', event.target.value)} />
                  </label>
                </>
              ) : (
                <label className="field compact">
                  <span>API Key</span>
                  <input type="password" value={getNestedValue(config, 'llm.api_key', '')} onChange={(event) => updateConfig('llm.api_key', event.target.value)} />
                </label>
              )}
              <label className="field compact">
                <span>模型名称</span>
                <input value={getNestedValue(config, 'llm.model', '')} onChange={(event) => updateConfig('llm.model', event.target.value)} />
              </label>
              <label className="field compact">
                <span>自定义 Base URL</span>
                <input value={getNestedValue(config, 'llm.base_url', '')} onChange={(event) => updateConfig('llm.base_url', event.target.value)} placeholder="留空则使用官方地址" />
              </label>
            </article>

            <article className="panel-card">
              <div className="panel-head">
                <div>
                  <span className="panel-kicker">Engine</span>
                  <h3>运行引擎</h3>
                </div>
              </div>
              <div className="toggle-grid single">
                <label><input type="radio" name="engine-mode" checked={engineMode === 'bundled'} onChange={() => updateConfig('desktop.engine.mode', 'bundled')} />内置后端（推荐普通用户）</label>
                <label><input type="radio" name="engine-mode" checked={engineMode === 'system_python'} onChange={() => updateConfig('desktop.engine.mode', 'system_python')} />系统 Python（需已安装 paperinsight）</label>
              </div>
              <label className="field compact">
                <span>Python 路径</span>
                <input value={getNestedValue(config, 'desktop.engine.python_path', '')} onChange={(event) => updateConfig('desktop.engine.python_path', event.target.value)} placeholder="如 C:/Python311/python.exe，需要该环境已安装 paperinsight" />
              </label>
              <label className="field compact">
                <span>后端可执行路径</span>
                <input value={getNestedValue(config, 'desktop.engine.backend_path', '')} onChange={(event) => updateConfig('desktop.engine.backend_path', event.target.value)} placeholder="预留给高级用户覆盖内置后端" />
              </label>
              <div className="toggle-grid single">
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'web_search.enabled', true))} onChange={(event) => updateConfig('web_search.enabled', event.target.checked)} />启用影响因子联网补全</label>
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'mineru.enabled', true))} onChange={(event) => updateConfig('mineru.enabled', event.target.checked)} />启用 MinerU 解析</label>
              </div>
              <label className="field compact">
                <span>MinerU 模式</span>
                <select value={getNestedValue(config, 'mineru.mode', 'cli')} onChange={(event) => updateConfig('mineru.mode', event.target.value)}>
                  <option value="cli">本地 CLI</option>
                  <option value="api">云端 API</option>
                </select>
              </label>
              <label className="field compact">
                <span>MinerU Token</span>
                <input type="password" value={getNestedValue(config, 'mineru.token', '')} onChange={(event) => updateConfig('mineru.token', event.target.value)} />
              </label>
            </article>

            <article className="panel-card wide">
              <div className="panel-head split">
                <div>
                  <span className="panel-kicker">Output</span>
                  <h3>默认输出策略</h3>
                </div>
                <button className="primary" disabled={saveState.saving} onClick={saveSettings}>{saveState.saving ? '保存中...' : '保存设置'}</button>
              </div>
              <div className="toggle-grid">
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'output.rename_pdfs', false))} onChange={(event) => updateConfig('output.rename_pdfs', event.target.checked)} />默认重命名 PDF</label>
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'output.bilingual_text', false))} onChange={(event) => updateConfig('output.bilingual_text', event.target.checked)} />默认启用中英双语</label>
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'cache.enabled', true))} onChange={(event) => updateConfig('cache.enabled', event.target.checked)} />默认启用缓存</label>
                <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'desktop.ui.remember_last_paths', true))} onChange={(event) => updateConfig('desktop.ui.remember_last_paths', event.target.checked)} />记住上次目录</label>
              </div>
              <label className="field">
                <span>PDF 重命名模板</span>
                <input value={getNestedValue(config, 'output.rename_template', '')} onChange={(event) => updateConfig('output.rename_template', event.target.value)} />
              </label>
              <label className="field">
                <span>缓存目录</span>
                <input value={getNestedValue(config, 'cache.directory', '.cache')} onChange={(event) => updateConfig('cache.directory', event.target.value)} />
              </label>
              <div className="save-feedback">
                {saveState.message ? <span className="success-text">{saveState.message}</span> : null}
                {saveState.error ? <span className="error-text">{saveState.error}</span> : null}
              </div>
            </article>
          </section>
        )}
      </main>
    </div>
  );
}
