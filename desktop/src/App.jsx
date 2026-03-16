import React, { useEffect, useMemo, useState } from 'react';

const tabs = [
  { id: 'analyze', label: '分析工作台' },
  { id: 'settings', label: '服务配置' }
];

const wizardSteps = [
  { id: 'welcome', title: '欢迎使用' },
  { id: 'llm', title: '配置 AI 服务' },
  { id: 'engine', title: '选择运行引擎' },
  { id: 'review', title: '确认并开始' }
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

function hasConfiguredCredentials(config) {
  const provider = getNestedValue(config, 'llm.provider', 'deepseek');
  const llmEnabled = Boolean(getNestedValue(config, 'llm.enabled', true));
  const llmApiKey = getNestedValue(config, 'llm.api_key', '');
  const wenxinId = getNestedValue(config, 'llm.wenxin.client_id', '');
  const wenxinSecret = getNestedValue(config, 'llm.wenxin.client_secret', '');
  const mineruToken = getNestedValue(config, 'mineru.token', '');
  const paddlexToken = getNestedValue(config, 'paddlex.token', '');

  if (provider === 'wenxin' && llmEnabled && wenxinId && wenxinSecret) {
    return true;
  }

  return Boolean((llmEnabled && llmApiKey) || mineruToken || paddlexToken);
}

function validateWizardStep(step, draftConfig) {
  if (step === 1 && getNestedValue(draftConfig, 'llm.enabled', true)) {
    const provider = getNestedValue(draftConfig, 'llm.provider', 'deepseek');
    if (provider === 'wenxin') {
      if (!getNestedValue(draftConfig, 'llm.wenxin.client_id', '').trim()) {
        return '请填写文心一言 Client ID，或关闭 LLM 语义提取。';
      }
      if (!getNestedValue(draftConfig, 'llm.wenxin.client_secret', '').trim()) {
        return '请填写文心一言 Client Secret，或关闭 LLM 语义提取。';
      }
      return '';
    }

    if (!getNestedValue(draftConfig, 'llm.api_key', '').trim()) {
      return `请填写 ${formatProviderLabel(provider)} API Key，或关闭 LLM 语义提取。`;
    }
  }

  if (step === 2 && getNestedValue(draftConfig, 'desktop.engine.mode', 'bundled') === 'system_python') {
    const pythonPath = getNestedValue(draftConfig, 'desktop.engine.python_path', '').trim();
    if (!pythonPath) {
      return '系统 Python 模式建议填写 Python 路径，方便桌面端直接调用。';
    }
  }

  return '';
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

function formatImpactFactor(value) {
  if (value === null || value === undefined || value === '') {
    return '未补全';
  }
  return `${value}`;
}

function OnboardingModal({
  visible,
  step,
  draftConfig,
  setDraftValue,
  onBack,
  onNext,
  onFinish,
  onSkip,
  saving,
  error
}) {
  if (!visible || !draftConfig) {
    return null;
  }

  const provider = getNestedValue(draftConfig, 'llm.provider', 'deepseek');
  const llmEnabled = Boolean(getNestedValue(draftConfig, 'llm.enabled', true));
  const engineMode = getNestedValue(draftConfig, 'desktop.engine.mode', 'bundled');
  const currentStep = wizardSteps[step];
  const isLastStep = step === wizardSteps.length - 1;

  return (
    <div className="wizard-overlay">
      <div className="wizard-card">
        <div className="wizard-header">
          <div>
            <span className="eyebrow">首次启动向导</span>
            <h2>{currentStep.title}</h2>
            <p>先完成一次最小配置，后续使用就可以直接点选运行。</p>
          </div>
          <button className="ghost small" onClick={onSkip} disabled={saving}>跳过向导</button>
        </div>

        <div className="wizard-progress">
          {wizardSteps.map((item, index) => (
            <div key={item.id} className={index <= step ? 'wizard-step active' : 'wizard-step'}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{item.title}</strong>
            </div>
          ))}
        </div>

        <div className="wizard-body">
          {step === 0 ? (
            <div className="wizard-panel-grid">
              <section className="wizard-info-block accent">
                <h3>默认体验</h3>
                <p>普通用户推荐使用内置后端 + 图形界面，安装后只需要补 API Key 即可开始分析。</p>
              </section>
              <section className="wizard-info-block teal">
                <h3>高级模式</h3>
                <p>如果你已经有 Python 环境和源码仓库，也可以切换到系统 Python 模式继续沿用原有脚本能力。</p>
              </section>
              <section className="wizard-info-block sand full">
                <h3>这一步会做什么</h3>
                <p>我们会帮你设置 LLM 服务、运行引擎和常用默认项。你也可以先跳过，稍后从“服务配置”页重新打开向导。</p>
              </section>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="wizard-form-grid">
              <label className="field compact">
                <span>启用 LLM 语义提取</span>
                <div className="toggle-grid single wizard-toggle">
                  <label><input type="checkbox" checked={llmEnabled} onChange={(event) => setDraftValue('llm.enabled', event.target.checked)} />启用后可使用 OpenAI / DeepSeek / Longcat / 文心一言做语义提取</label>
                </div>
              </label>
              <label className="field compact">
                <span>LLM 提供商</span>
                <select value={provider} onChange={(event) => setDraftValue('llm.provider', event.target.value)}>
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
                    <input type="password" value={getNestedValue(draftConfig, 'llm.wenxin.client_id', '')} onChange={(event) => setDraftValue('llm.wenxin.client_id', event.target.value)} placeholder="填写文心一言 Client ID" />
                  </label>
                  <label className="field compact">
                    <span>Client Secret</span>
                    <input type="password" value={getNestedValue(draftConfig, 'llm.wenxin.client_secret', '')} onChange={(event) => setDraftValue('llm.wenxin.client_secret', event.target.value)} placeholder="填写文心一言 Client Secret" />
                  </label>
                </>
              ) : (
                <label className="field compact wide-field">
                  <span>API Key</span>
                  <input type="password" value={getNestedValue(draftConfig, 'llm.api_key', '')} onChange={(event) => setDraftValue('llm.api_key', event.target.value)} placeholder={`填写 ${formatProviderLabel(provider)} API Key`} />
                </label>
              )}
              <label className="field compact wide-field">
                <span>模型名称</span>
                <input value={getNestedValue(draftConfig, 'llm.model', '')} onChange={(event) => setDraftValue('llm.model', event.target.value)} placeholder="例如 gpt-4o / deepseek-chat / LongCat-Flash-Chat" />
              </label>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="wizard-form-grid">
              <section className="wizard-choice-card">
                <h3>运行引擎</h3>
                <div className="toggle-grid single wizard-toggle">
                  <label><input type="radio" name="wizard-engine" checked={engineMode === 'bundled'} onChange={() => setDraftValue('desktop.engine.mode', 'bundled')} />内置后端（推荐）</label>
                  <label><input type="radio" name="wizard-engine" checked={engineMode === 'system_python'} onChange={() => setDraftValue('desktop.engine.mode', 'system_python')} />系统 Python（高级用户）</label>
                </div>
                <label className="field compact">
                  <span>Python 路径</span>
                  <input value={getNestedValue(draftConfig, 'desktop.engine.python_path', '')} onChange={(event) => setDraftValue('desktop.engine.python_path', event.target.value)} placeholder="如 C:/Python311/python.exe" />
                </label>
              </section>
              <section className="wizard-choice-card">
                <h3>文档解析与联网能力</h3>
                <div className="toggle-grid single wizard-toggle">
                  <label><input type="checkbox" checked={Boolean(getNestedValue(draftConfig, 'mineru.enabled', true))} onChange={(event) => setDraftValue('mineru.enabled', event.target.checked)} />启用 MinerU 解析</label>
                  <label><input type="checkbox" checked={Boolean(getNestedValue(draftConfig, 'web_search.enabled', true))} onChange={(event) => setDraftValue('web_search.enabled', event.target.checked)} />启用影响因子联网补全</label>
                  <label><input type="checkbox" checked={Boolean(getNestedValue(draftConfig, 'cache.enabled', true))} onChange={(event) => setDraftValue('cache.enabled', event.target.checked)} />启用缓存</label>
                </div>
                <label className="field compact">
                  <span>MinerU 模式</span>
                  <select value={getNestedValue(draftConfig, 'mineru.mode', 'cli')} onChange={(event) => setDraftValue('mineru.mode', event.target.value)}>
                    <option value="cli">本地 CLI</option>
                    <option value="api">云端 API</option>
                  </select>
                </label>
                <label className="field compact">
                  <span>MinerU Token</span>
                  <input type="password" value={getNestedValue(draftConfig, 'mineru.token', '')} onChange={(event) => setDraftValue('mineru.token', event.target.value)} placeholder="可稍后补充" />
                </label>
              </section>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="wizard-summary-grid">
              <section className="wizard-summary-card">
                <span>LLM</span>
                <strong>{llmEnabled ? formatProviderLabel(provider) : '关闭，先走正则兜底'}</strong>
                <p>{llmEnabled ? '已准备好语义提取入口。' : '后续仍可在设置页补充 API Key。'}</p>
              </section>
              <section className="wizard-summary-card">
                <span>运行引擎</span>
                <strong>{engineMode === 'bundled' ? '内置后端' : '系统 Python'}</strong>
                <p>{engineMode === 'bundled' ? '优先面向普通用户，无需额外理解 Python。' : '保留本地 Python 可选能力。'}</p>
              </section>
              <section className="wizard-summary-card">
                <span>论文处理默认项</span>
                <strong>{Boolean(getNestedValue(draftConfig, 'cache.enabled', true)) ? '缓存开启' : '缓存关闭'}</strong>
                <p>MinerU：{Boolean(getNestedValue(draftConfig, 'mineru.enabled', true)) ? '启用' : '禁用'}，Web 搜索：{Boolean(getNestedValue(draftConfig, 'web_search.enabled', true)) ? '启用' : '禁用'}</p>
              </section>
              <section className="wizard-summary-card full">
                <span>完成后</span>
                <strong>进入分析工作台</strong>
                <p>你可以直接选择论文目录开始分析，或者去“服务配置”页继续补充更细的参数。</p>
              </section>
            </div>
          ) : null}
        </div>

        {error ? <div className="wizard-error">{error}</div> : null}

        <div className="wizard-actions">
          <button className="ghost" onClick={onBack} disabled={step === 0 || saving}>上一步</button>
          {isLastStep ? (
            <button className="primary" onClick={onFinish} disabled={saving}>{saving ? '保存中...' : '完成配置'}</button>
          ) : (
            <button className="primary" onClick={onNext} disabled={saving}>下一步</button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState('analyze');
  const [config, setConfig] = useState(null);
  const [meta, setMeta] = useState(null);
  const [env, setEnv] = useState(null);
  const [runOptions, setRunOptions] = useState(initialRunOptions);
  const [loadState, setLoadState] = useState({ loading: true, error: '' });
  const [saveState, setSaveState] = useState({ saving: false, message: '', error: '' });
  const [onboarding, setOnboarding] = useState({ visible: false, step: 0, saving: false, error: '' });
  const [wizardConfig, setWizardConfig] = useState(null);
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
        const onboardingCompleted = Boolean(getNestedValue(response.config, 'desktop.ui.onboarding_completed', false));
        const existingCredentials = hasConfiguredCredentials(response.config);

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

        if (!onboardingCompleted && !existingCredentials) {
          setWizardConfig(cloneConfig(response.config));
          setOnboarding({ visible: true, step: 0, saving: false, error: '' });
        }
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

  function updateWizardConfig(path, value) {
    setWizardConfig((current) => setNestedValue(current, path, value));
  }

  async function persistConfig(nextConfig, successMessage) {
    const withPdfDir = setNestedValue(nextConfig, 'desktop.ui.last_pdf_dir', runOptions.pdfDir);
    const withOutputDir = setNestedValue(withPdfDir, 'desktop.ui.last_output_dir', runOptions.outputDir);
    const finalConfig = setNestedValue(withOutputDir, 'desktop.ui.onboarding_completed', true);
    const response = await window.paperInsight.saveConfig(finalConfig);
    setConfig(response.config);
    setWizardConfig(cloneConfig(response.config));
    setSaveState({ saving: false, message: successMessage, error: '' });
    return response.config;
  }

  async function saveSettings() {
    setSaveState({ saving: true, message: '', error: '' });
    try {
      await persistConfig(config, '设置已保存。');
    } catch (error) {
      setSaveState({ saving: false, message: '', error: error.message || '保存失败' });
    }
  }

  async function finishOnboarding(configToPersist) {
    setOnboarding((current) => ({ ...current, saving: true, error: '' }));
    try {
      const nextConfig = await persistConfig(configToPersist, '首次配置已保存。');
      setOnboarding({ visible: false, step: 0, saving: false, error: '' });
      setWizardConfig(cloneConfig(nextConfig));
      setActiveTab('analyze');
    } catch (error) {
      setOnboarding((current) => ({ ...current, saving: false, error: error.message || '保存失败' }));
    }
  }

  function reopenOnboarding() {
    setWizardConfig(cloneConfig(config));
    setOnboarding({ visible: true, step: 0, saving: false, error: '' });
  }

  function skipOnboarding() {
    finishOnboarding(config);
  }

  function nextWizardStep() {
    const error = validateWizardStep(onboarding.step, wizardConfig);
    if (error) {
      setOnboarding((current) => ({ ...current, error }));
      return;
    }
    setOnboarding((current) => ({ ...current, step: current.step + 1, error: '' }));
  }

  function previousWizardStep() {
    setOnboarding((current) => ({ ...current, step: Math.max(0, current.step - 1), error: '' }));
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

  async function openPath(targetPath) {
    if (!targetPath) {
      return;
    }
    await window.paperInsight.openPath(targetPath);
  }

  if (loadState.loading) {
    return <div className="loading-shell">正在启动 PaperInsight Desktop...</div>;
  }

  if (loadState.error || !config) {
    return <div className="loading-shell error">加载失败：{loadState.error}</div>;
  }

  const provider = getNestedValue(config, 'llm.provider', 'deepseek');
  const engineMode = getNestedValue(config, 'desktop.engine.mode', 'bundled');
  const onboardingCompleted = Boolean(getNestedValue(config, 'desktop.ui.onboarding_completed', false));

  return (
    <>
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
            <div className="status-card sand">
              <span>首次向导</span>
              <strong>{onboardingCompleted ? '已完成' : '待完成'}</strong>
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

          <button className="sidebar-link" onClick={reopenOnboarding}>重新打开首次向导</button>

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
                现在已经加上首次启动向导，新用户第一次打开就能按步骤完成 API Key、引擎和默认项设置；
                高级用户仍然可以切回系统 Python。
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
                  <>
                    <div className="stat-grid">
                      <div><span>PDF 总数</span><strong>{job.stats.pdfCount}</strong></div>
                      <div><span>成功</span><strong>{job.stats.successCount}</strong></div>
                      <div><span>失败</span><strong>{job.stats.errorCount}</strong></div>
                      <div><span>重命名</span><strong>{job.stats.renamedCount}</strong></div>
                    </div>

                    <div className="result-grid">
                      <section className="result-card">
                        <div className="result-head">
                          <h4>报表与输出</h4>
                          <button className="ghost small" onClick={openOutputDir}>打开输出目录</button>
                        </div>
                        {Object.entries(job.stats.reportFiles || {}).length ? (
                          <div className="result-list">
                            {Object.entries(job.stats.reportFiles || {}).map(([label, targetPath]) => (
                              <button key={label} className="result-item" onClick={() => openPath(targetPath)}>
                                <span>{label}</span>
                                <strong>{targetPath}</strong>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="empty-inline">本次未生成报表文件。</div>
                        )}
                      </section>

                      <section className="result-card">
                        <div className="result-head">
                          <h4>成功论文</h4>
                          <span>{job.stats.successItems?.length || 0} 篇</span>
                        </div>
                        {job.stats.successItems?.length ? (
                          <div className="result-list compact">
                            {job.stats.successItems.map((item) => (
                              <button key={`${item.file}-${item.path}`} className="result-item" onClick={() => openPath(item.path)}>
                                <span>{item.file}</span>
                                <strong>{item.title || '未提取到标题'}</strong>
                                <small>{item.journal || '未提取期刊'} · IF {formatImpactFactor(item.impactFactor)}{item.bestEqe ? ` · EQE ${item.bestEqe}` : ''}</small>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="empty-inline">暂无成功记录。</div>
                        )}
                      </section>

                      <section className="result-card">
                        <div className="result-head">
                          <h4>失败论文</h4>
                          <span>{job.stats.errorItems?.length || 0} 篇</span>
                        </div>
                        {job.stats.errorItems?.length ? (
                          <div className="result-list compact">
                            {job.stats.errorItems.map((item) => (
                              <button key={`${item.file}-${item.path}`} className="result-item danger-soft" onClick={() => openPath(item.path)}>
                                <span>{item.file || '未知文件'}</span>
                                <strong>{item.context || item.type || '处理失败'}</strong>
                                <small>{item.message || '未知错误'}</small>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="empty-inline">本次没有失败文件。</div>
                        )}
                      </section>
                    </div>
                  </>
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
                  <div className="action-row">
                    <button className="ghost" onClick={reopenOnboarding}>重新打开向导</button>
                    <button className="primary" disabled={saveState.saving} onClick={saveSettings}>{saveState.saving ? '保存中...' : '保存设置'}</button>
                  </div>
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

      <OnboardingModal
        visible={onboarding.visible}
        step={onboarding.step}
        draftConfig={wizardConfig}
        setDraftValue={updateWizardConfig}
        onBack={previousWizardStep}
        onNext={nextWizardStep}
        onFinish={() => finishOnboarding(wizardConfig)}
        onSkip={skipOnboarding}
        saving={onboarding.saving}
        error={onboarding.error}
      />
    </>
  );
}
