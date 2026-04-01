import React, { useMemo, useCallback } from 'react';
import { 
  buildEnvironmentAlerts, 
  buildGettingStartedSteps, 
  buildAnalysisGuard, 
  buildRunSummary,
  modeLabel,
  defaultOutputDir
} from '../utils';

// 优化：创建可重用的子组件并使用React.memo
const AlertComponent = React.memo(({ alert, onOpenSettings, onReopenOnboarding, onUseRegexMode, onApplyRecommendation }) => (
  <div className={`alert ${alert.severity}`}>
    <div>
      <h3>{alert.title}</h3>
      <p>{alert.description}</p>
    </div>
    <div className="alert-actions">
      {alert.actions.map((action) => (
        <button key={action} className="ghost small" onClick={() => {
          if (action === 'open_settings') onOpenSettings();
          if (action === 'reopen_onboarding') onReopenOnboarding();
          if (action === 'use_regex') onUseRegexMode();
          if (action === 'apply_recommendation' && onApplyRecommendation) onApplyRecommendation();
        }}>
          {{
            open_settings: '去设置',
            reopen_onboarding: '重走向导',
            use_regex: '切正则兜底',
            apply_recommendation: '应用推荐'
          }[action]}
        </button>
      ))}
    </div>
  </div>
));

const StepCard = React.memo(({ step, onReopenOnboarding, onFocusInput, onStartAnalysis, onOpenSettings }) => (
  <div className="step-card">
    <div>
      <h3>{step.title}</h3>
      <p>{step.description}</p>
      <div className="step-status">{step.status}</div>
    </div>
    <button className="primary small" onClick={() => {
      if (step.action === 'reopen_onboarding') onReopenOnboarding();
      if (step.action === 'focus_input') onFocusInput();
      if (step.action === 'start_analysis') onStartAnalysis();
      if (step.action === 'open_settings') onOpenSettings();
    }}>{step.actionLabel}</button>
  </div>
));

const IssueComponent = React.memo(({ issue, onReopenOnboarding, onFocusInput, onOpenSettings, onUseRegexMode }) => (
  <div className="issue">
    <h4>{issue.title}</h4>
    <p>{issue.description}</p>
    <button className="ghost small" onClick={() => {
      if (issue.action === 'reopen_onboarding') onReopenOnboarding();
      if (issue.action === 'focus_input') onFocusInput();
      if (issue.action === 'open_settings') onOpenSettings();
      if (issue.action === 'use_regex') onUseRegexMode();
    }}>{issue.actionLabel}</button>
  </div>
));

const SummaryItem = React.memo(({ label, value }) => (
  <div className="summary-item">
    <span>{label}</span>
    <strong>{value}</strong>
  </div>
));

function AnalyzeTab({
  config,
  env,
  runOptions,
  setRunOptions,
  job,
  onboardingCompleted,
  onChooseDirectory,
  onStartAnalysis,
  onUseRegexMode,
  onOpenSettings,
  onReopenOnboarding,
  onFocusInput,
  onApplyRecommendation
}) {
  // 优化：使用useCallback缓存事件处理函数
  const handleModeChange = useCallback((e) => {
    setRunOptions({ ...runOptions, mode: e.target.value });
  }, [runOptions, setRunOptions]);

  const handleRecursiveChange = useCallback((e) => {
    setRunOptions({ ...runOptions, recursive: e.target.value === 'true' });
  }, [runOptions, setRunOptions]);

  const handleExportJsonChange = useCallback((e) => {
    setRunOptions({ ...runOptions, exportJson: e.target.value === 'true' });
  }, [runOptions, setRunOptions]);

  const handleChoosePdfDir = useCallback(() => {
    onChooseDirectory('pdfDir');
  }, [onChooseDirectory]);

  const handleChooseOutputDir = useCallback(() => {
    onChooseDirectory('outputDir');
  }, [onChooseDirectory]);

  // 优化：使用useMemo缓存计算结果
  const alerts = useMemo(() => buildEnvironmentAlerts(env, config, runOptions), [env, config, runOptions]);
  const gettingStartedSteps = useMemo(() => buildGettingStartedSteps(config, env, runOptions, onboardingCompleted), [config, env, runOptions, onboardingCompleted]);
  const analysisGuard = useMemo(() => buildAnalysisGuard(config, env, runOptions, onboardingCompleted), [config, env, runOptions, onboardingCompleted]);
  const runSummary = useMemo(() => buildRunSummary(config, env, runOptions), [config, env, runOptions]);
  const outputDirValue = useMemo(() => runOptions.outputDir || defaultOutputDir(runOptions.pdfDir), [runOptions.outputDir, runOptions.pdfDir]);

  return (
    <div className="tab-content analyze">
      <section className="hero">
        <div>
          <h1>用点选代替命令行</h1>
          <p>现在已经加上首次启动向导，新用户第一次打开就能按步骤完成 API Key、引擎和默认项设置；高级用户仍然可以切回系统 Python。</p>
        </div>
      </section>

      <section className="alerts">
        {alerts.map((alert) => (
          <AlertComponent 
            key={alert.id} 
            alert={alert} 
            onOpenSettings={onOpenSettings}
            onReopenOnboarding={onReopenOnboarding}
            onUseRegexMode={onUseRegexMode}
            onApplyRecommendation={onApplyRecommendation}
          />
        ))}
      </section>

      <section className="getting-started">
        <div>
          <h2>快速开始</h2>
          <div className="steps">
            {gettingStartedSteps.map((step) => (
              <StepCard 
                key={step.id} 
                step={step} 
                onReopenOnboarding={onReopenOnboarding}
                onFocusInput={onFocusInput}
                onStartAnalysis={onStartAnalysis}
                onOpenSettings={onOpenSettings}
              />
            ))}
          </div>
        </div>
      </section>

      <section className="input-output">
        <h2>输入与输出</h2>
        <div className="grid">
          <div className="field-group">
            <label className="field">
              <span>论文目录</span>
              <div className="path-input">
                <input value={runOptions.pdfDir} readOnly placeholder="请选择包含 PDF 的文件夹" />
                <button className="ghost" onClick={handleChoosePdfDir}>选择</button>
              </div>
            </label>
            <label className="field">
              <span>输出目录</span>
              <div className="path-input">
                <input value={outputDirValue} readOnly placeholder="默认会在论文目录下生成 output 子目录" />
                <button className="ghost" onClick={handleChooseOutputDir}>选择</button>
              </div>
            </label>
          </div>
          <div className="options-group">
            <label className="field">
              <span>处理模式</span>
              <select value={runOptions.mode} onChange={handleModeChange}>
                <option value="auto">自动模式 - 优先 API，失败后回退</option>
                <option value="api">智能 API - 全程使用 LLM 提取</option>
                <option value="regex">正则兜底 - 纯本地，不联网</option>
              </select>
            </label>
            <label className="field">
              <span>扫描方式</span>
              <select value={runOptions.recursive} onChange={handleRecursiveChange}>
                <option value="true">递归扫描子目录</option>
                <option value="false">只处理当前目录</option>
              </select>
            </label>
            <label className="field">
              <span>附加输出</span>
              <select value={runOptions.exportJson} onChange={handleExportJsonChange}>
                <option value="false">仅 Excel</option>
                <option value="true">Excel + JSON</option>
              </select>
            </label>
          </div>
        </div>
      </section>

      <section className="run-section">
        <h2>开始分析</h2>
        <div className="run-summary">
          {runSummary.map(([label, value]) => (
            <SummaryItem key={label} label={label} value={value} />
          ))}
        </div>
        <div className="run-actions">
          <button 
            className="primary" 
            onClick={onStartAnalysis}
            disabled={job.running || analysisGuard.blockingIssues.length > 0}
          >
            {job.running ? '处理中...' : '开始分析'}
          </button>
          {analysisGuard.blockingIssues.length > 0 && (
            <div className="blocking-issues">
              {analysisGuard.blockingIssues.map((issue) => (
                <IssueComponent 
                  key={issue.id} 
                  issue={issue} 
                  onReopenOnboarding={onReopenOnboarding}
                  onFocusInput={onFocusInput}
                  onOpenSettings={onOpenSettings}
                  onUseRegexMode={onUseRegexMode}
                />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// 优化：使用React.memo包装主组件
export default React.memo(AnalyzeTab);