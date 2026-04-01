import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { tabs, initialRunOptions } from './constants';
import { 
  getNestedValue, 
  setNestedValue, 
  cloneConfig, 
  buildLogLine, 
  buildBasicOnboardingConfig,
  buildRecommendedConfig,
  validateWizardStep,
  booleanStatusLabel,
  readinessLabel
} from './utils';
import OnboardingModal from './components/OnboardingModal';
import AnalyzeTab from './components/AnalyzeTab';
import SettingsTab from './components/SettingsTab';
import HelpTab from './components/HelpTab';
import ResultsTab from './components/ResultsTab';
import HistoryPanel from './components/HistoryPanel';
import ProgressIndicator from './components/ProgressIndicator';
import BatchProgressBar from './components/BatchProgressBar';

// 优化：使用React.memo包装组件，减少不必要的重渲染
const MemoizedAnalyzeTab = React.memo(AnalyzeTab);
const MemoizedSettingsTab = React.memo(SettingsTab);
const MemoizedHelpTab = React.memo(HelpTab);
const MemoizedResultsTab = React.memo(ResultsTab);
const MemoizedOnboardingModal = React.memo(OnboardingModal);
const MemoizedHistoryPanel = React.memo(HistoryPanel);

export default function App() {
  const [activeTab, setActiveTab] = useState('analyze');
  const [config, setConfig] = useState(null);
  const [meta, setMeta] = useState(null);
  const [env, setEnv] = useState(null);
  const [runOptions, setRunOptions] = useState(initialRunOptions);
  const [loadState, setLoadState] = useState({ loading: true, error: '' });
  const [saveState, setSaveState] = useState({ saving: false, message: '', error: '' });
  const [onboarding, setOnboarding] = useState({ visible: false, step: 0, saving: false, error: '' });
  const [runConfirmVisible, setRunConfirmVisible] = useState(false);
  const [wizardConfig, setWizardConfig] = useState(null);
  const [resultQuery, setResultQuery] = useState('');
  const [resultScope, setResultScope] = useState('all');
  const [job, setJob] = useState({
    running: false,
    status: 'idle',
    total: 0,
    completed: 0,
    currentFile: '',
    currentStage: '',
    stageMessage: '',
    progressPercent: 0,
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
        setConfig(response.config);
        setMeta(response.meta);
        setEnv(response.env);
        setRunOptions((current) => ({
          ...current,
          pdfDir: getNestedValue(response.config, 'desktop.ui.last_pdf_dir', ''),
          outputDir: getNestedValue(response.config, 'desktop.ui.last_output_dir', ''),
          mode: getNestedValue(response.env, 'recommendation.analysisMode', current.mode),
          exportJson: getNestedValue(response.config, 'output.format', []).includes('json'),
          renamePdfs: Boolean(getNestedValue(response.config, 'output.rename_pdfs', false)),
          bilingual: Boolean(getNestedValue(response.config, 'output.bilingual_text', false))
        }));

        if (!onboardingCompleted) {
          setWizardConfig(buildBasicOnboardingConfig(response.config, response.env));
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
              currentStage: '',
              stageMessage: '',
              progressPercent: 0,
              outputDir: event.outputDir || current.outputDir,
              launch: event.launch,
              logs: nextLogs,
              stats: null
            };
          }

          if (event.type === 'stage-progress') {
            return {
              ...current,
              currentFile: event.currentFile,
              currentStage: event.currentStage,
              stageMessage: event.stageMessage || '',
              completed: event.completedCount,
              total: event.totalCount,
              progressPercent: event.progressPercent || 0,
              logs: nextLogs
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
              currentFile: '',
              currentStage: '',
              stageMessage: '',
              progressPercent: 100,
              outputDir: event.outputDir || current.outputDir,
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

          if (event.type === 'process-exit') {
            if (!current.running) {
              return {
                ...current,
                logs: nextLogs
              };
            }

            return {
              ...current,
              running: false,
              status: event.code === 0 && current.completed >= current.total ? 'completed' : 'failed',
              currentFile: '',
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

  const onboardingCompleted = useMemo(() => {
    return Boolean(getNestedValue(config, 'desktop.ui.onboarding_completed', false));
  }, [config]);

  // 优化：使用useCallback缓存函数，减少不必要的函数重新创建
  const chooseDirectory = useCallback(async (target) => {
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
      ...(target === 'pdfDir' && !current.outputDir ? { outputDir: `${selected}/output` } : {})
    }));
  }, [runOptions]);

  const updateWizardConfig = useCallback((path, value) => {
    setWizardConfig((current) => setNestedValue(current, path, value));
  }, []);

  const persistConfig = useCallback(async (nextConfig, successMessage) => {
    const rememberLastPaths = Boolean(getNestedValue(nextConfig, 'desktop.ui.remember_last_paths', true));
    const withPdfDir = setNestedValue(nextConfig, 'desktop.ui.last_pdf_dir', rememberLastPaths ? runOptions.pdfDir : '');
    const withOutputDir = setNestedValue(withPdfDir, 'desktop.ui.last_output_dir', rememberLastPaths ? runOptions.outputDir : '');
    const finalConfig = setNestedValue(withOutputDir, 'desktop.ui.onboarding_completed', true);
    const response = await window.paperInsight.saveConfig(finalConfig);
    setConfig(response.config);
    setWizardConfig(cloneConfig(response.config));
    if (response.env) {
      setEnv(response.env);
    }
    setSaveState({ saving: false, message: successMessage, error: '' });
    return response.config;
  }, [runOptions.pdfDir, runOptions.outputDir]);

  const saveSettings = useCallback(async () => {
    setSaveState({ saving: true, message: '', error: '' });
    try {
      await persistConfig(config, '设置已保存。');
    } catch (error) {
      setSaveState({ saving: false, message: '', error: error.message || '保存失败' });
    }
  }, [config, persistConfig]);

  const applyRecommendedSetup = useCallback(async () => {
    const nextConfig = buildRecommendedConfig(config, env);
    const nextMode = getNestedValue(env, 'recommendation.analysisMode', runOptions.mode);
    const previousConfig = config;

    setConfig(nextConfig);
    setRunOptions((current) => ({ ...current, mode: nextMode }));
    setSaveState({ saving: true, message: '', error: '' });

    try {
      await persistConfig(nextConfig, '已应用推荐启动设置。');
    } catch (error) {
      setConfig(previousConfig);
      setSaveState({ saving: false, message: '', error: error.message || '应用推荐设置失败' });
    }
  }, [config, env, runOptions.mode, persistConfig]);

  const useFallbackMode = useCallback(() => {
    setRunOptions((current) => ({ ...current, mode: 'regex' }));
  }, []);

  const cancelAnalysis = useCallback(async () => {
    try {
      await window.paperInsight.cancelAnalysis();
    } catch (error) {
      setJob((current) => ({
        ...current,
        logs: [
          {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            text: `取消失败：${error.message}`,
            type: 'error'
          },
          ...current.logs
        ]
      }));
    }
  }, []);

  const startAnalysis = useCallback(async () => {
    if (!runOptions.pdfDir) {
      alert('请先选择论文目录');
      return;
    }

    try {
      await window.paperInsight.startAnalysis({
        pdfDir: runOptions.pdfDir,
        outputDir: runOptions.outputDir || `${runOptions.pdfDir}/output`,
        recursive: runOptions.recursive,
        maxPages: runOptions.maxPages,
        mode: runOptions.mode,
        exportJson: runOptions.exportJson,
        noCache: runOptions.noCache,
        renamePdfs: runOptions.renamePdfs,
        bilingual: runOptions.bilingual
      });
    } catch (error) {
      setJob((current) => ({
        ...current,
        running: false,
        status: 'failed',
        logs: [
          {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            text: `启动失败：${error.message}`,
            type: 'failed'
          },
          ...current.logs
        ]
      }));
    }
  }, [runOptions]);

  const handleWizardBack = useCallback(() => {
    setOnboarding((current) => ({
      ...current,
      step: Math.max(0, current.step - 1),
      error: ''
    }));
  }, []);

  const handleWizardNext = useCallback(() => {
    const error = validateWizardStep(onboarding.step, wizardConfig);
    if (error) {
      setOnboarding((current) => ({ ...current, error }));
      return;
    }

    setOnboarding((current) => ({
      ...current,
      step: current.step + 1,
      error: ''
    }));
  }, [onboarding.step, wizardConfig]);

  const handleWizardFinish = useCallback(async () => {
    setOnboarding((current) => ({ ...current, saving: true, error: '' }));
    try {
      await persistConfig(wizardConfig, '配置已保存。');
      setOnboarding((current) => ({ ...current, visible: false, saving: false }));
    } catch (error) {
      setOnboarding((current) => ({ ...current, error: error.message || '保存失败', saving: false }));
    }
  }, [wizardConfig, persistConfig]);

  const handleWizardSkip = useCallback(async (configToSave) => {
    setOnboarding((current) => ({ ...current, saving: true, error: '' }));
    try {
      await persistConfig(configToSave, '已保存基础配置。');
      setOnboarding((current) => ({ ...current, visible: false, saving: false }));
    } catch (error) {
      setOnboarding((current) => ({ ...current, error: error.message || '保存失败', saving: false }));
    }
  }, [persistConfig]);

  const handleReopenOnboarding = useCallback(() => {
    setWizardConfig(cloneConfig(config));
    setOnboarding({ visible: true, step: 0, saving: false, error: '' });
  }, [config]);

  const handleFocusInput = useCallback(() => {
  }, []);

  const handleFilesDropped = useCallback(async (files) => {
    if (!files || files.length === 0) {
      return;
    }

    const filePaths = files.map(file => file.path || file.name);
    
    if (filePaths.length === 1) {
      const singleFile = files[0];
      const dirPath = singleFile.path ? singleFile.path.substring(0, singleFile.path.lastIndexOf('/')) : '';
      
      if (dirPath) {
        setRunOptions((current) => ({
          ...current,
          pdfDir: dirPath,
          ...(current.outputDir ? {} : { outputDir: `${dirPath}/output` })
        }));
      }
    } else {
      const paths = files.map(f => f.path).filter(Boolean);
      if (paths.length > 0) {
        const commonDir = paths.reduce((common, path) => {
          const parts = path.split('/');
          const commonParts = common.split('/');
          const shared = [];
          for (let i = 0; i < Math.min(parts.length - 1, commonParts.length); i++) {
            if (parts[i] === commonParts[i]) {
              shared.push(parts[i]);
            } else {
              break;
            }
          }
          return shared.join('/');
        }, paths[0].substring(0, paths[0].lastIndexOf('/')));

        if (commonDir) {
          setRunOptions((current) => ({
            ...current,
            pdfDir: commonDir,
            ...(current.outputDir ? {} : { outputDir: `${commonDir}/output` })
          }));
        }
      }
    }

    setJob((current) => ({
      ...current,
      logs: [
        {
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          text: `已选择 ${files.length} 个 PDF 文件`,
          type: 'info'
        },
        ...current.logs
      ].slice(0, 120)
    }));
  }, []);

  if (loadState.loading) {
    return <div className="loading-shell">加载中...</div>;
  }

  if (loadState.error) {
    return <div className="loading-shell error">{loadState.error}</div>;
  }

  return (
    <div className="app">
      <header className="top-nav">
        <div className="brand">
          <h1>PaperInsight</h1>
        </div>
        <nav className="main-nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`nav-item ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="status-bar">
          <span className="version">v{meta?.version || '4.2'}</span>
          <span className="status">{job.running ? '处理中...' : '就绪'}</span>
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <div className="env-card">
            <h3>环境状态</h3>
            <div className="env-info">
              <div className="info-item">
                <span>引擎状态:</span>
                <span className={getNestedValue(env, 'readiness.status', '') === 'ready' ? 'status-ready' : 'status-warning'}>
                  {readinessLabel(getNestedValue(env, 'readiness.status', 'limited'))}
                </span>
              </div>
              <div className="info-item">
                <span>网络状态:</span>
                <span className={getNestedValue(env, 'checks.network.available', false) ? 'status-ready' : 'status-warning'}>
                  {booleanStatusLabel(
                    getNestedValue(env, 'checks.network.available', false), 
                    '可用', 
                    '受限'
                  )}
                </span>
              </div>
              <div className="info-item">
                <span>分析模式:</span>
                <span>{runOptions.mode}</span>
              </div>
            </div>
          </div>

          <div className="quick-actions">
            <h3>快捷操作</h3>
            <button className="action-btn" onClick={() => setActiveTab('analyze')}>
              开始分析
            </button>
            <button className="action-btn" onClick={() => setActiveTab('settings')}>
              系统设置
            </button>
            <button className="action-btn" onClick={handleReopenOnboarding}>
              配置向导
            </button>
          </div>

          <div className="config-management">
            <h3>配置管理</h3>
            <button className="action-btn secondary">
              导入配置
            </button>
            <button className="action-btn secondary">
              导出配置
            </button>
          </div>
        </aside>

        <main className="main-panel">
          <div className="panel-header">
            <h2>{tabs.find(tab => tab.id === activeTab)?.label}</h2>
            {activeTab === 'analyze' && (
              <div className="panel-actions">
                {job.running ? (
                  <button className="danger" onClick={cancelAnalysis}>
                    取消分析
                  </button>
                ) : (
                  <button className="primary" onClick={startAnalysis}>
                    开始分析
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="panel-content">
            {activeTab === 'analyze' && (
              <MemoizedAnalyzeTab
                config={config}
                env={env}
                runOptions={runOptions}
                setRunOptions={setRunOptions}
                job={job}
                onboardingCompleted={onboardingCompleted}
                onChooseDirectory={chooseDirectory}
                onStartAnalysis={startAnalysis}
                onUseRegexMode={useFallbackMode}
                onOpenSettings={() => setActiveTab('settings')}
                onReopenOnboarding={handleReopenOnboarding}
                onFocusInput={handleFocusInput}
                onApplyRecommendation={applyRecommendedSetup}
                onFilesDropped={handleFilesDropped}
              />
            )}

            {activeTab === 'settings' && (
              <MemoizedSettingsTab
                config={config}
                setConfig={setConfig}
                saveState={saveState}
                onSaveSettings={saveSettings}
                onApplyRecommendedSetup={applyRecommendedSetup}
              />
            )}

            {activeTab === 'help' && (
              <MemoizedHelpTab
                config={config}
                env={env}
                onboardingCompleted={onboardingCompleted}
                runOptions={runOptions}
              />
            )}

            {activeTab === 'history' && (
              <MemoizedHistoryPanel
                onLoadHistory={(record) => {
                  if (record.pdfDir) {
                    setRunOptions((current) => ({
                      ...current,
                      pdfDir: record.pdfDir,
                      outputDir: record.outputDir || `${record.pdfDir}/output`
                    }));
                  }
                  setActiveTab('analyze');
                }}
              />
            )}

            {activeTab === 'analyze' && job.status !== 'idle' && (
              <MemoizedResultsTab
                job={job}
                resultQuery={resultQuery}
                setResultQuery={setResultQuery}
                resultScope={resultScope}
                setResultScope={setResultScope}
              />
            )}
          </div>

          {job.running && (
            <div className="progress-panel">
              <BatchProgressBar
                completed={job.completed}
                total={job.total}
                progressPercent={job.progressPercent || progressPercent}
                currentFile={job.currentFile}
                status={job.status}
                onCancel={cancelAnalysis}
              />
              {job.currentStage && (
                <ProgressIndicator
                  currentStage={job.currentStage}
                  stageMessage={job.stageMessage}
                  currentFile={job.currentFile}
                  completedCount={job.completed}
                  totalCount={job.total}
                  progressPercent={job.progressPercent || progressPercent}
                />
              )}
            </div>
          )}

          <div className="panel-footer">
            <div className="progress-info">
              {job.running && (
                <span>进度: {progressPercent}% ({job.completed}/{job.total})</span>
              )}
            </div>
            <div className="system-info">
              <span>PaperInsight 4.2</span>
            </div>
          </div>
        </main>
      </div>

      <MemoizedOnboardingModal
        visible={onboarding.visible}
        step={onboarding.step}
        draftConfig={wizardConfig}
        env={env}
        setDraftValue={updateWizardConfig}
        onBack={handleWizardBack}
        onNext={handleWizardNext}
        onFinish={handleWizardFinish}
        onSkip={handleWizardSkip}
        saving={onboarding.saving}
        error={onboarding.error}
      />
    </div>
  );
}