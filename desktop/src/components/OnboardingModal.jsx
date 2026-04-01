import React from 'react';
import { getNestedValue, booleanStatusLabel, modeLabel, engineModeLabel, buildBasicOnboardingConfig } from '../utils';
import { wizardSteps } from '../constants';

function OnboardingModal({
  visible,
  step,
  draftConfig,
  env,
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

  const provider = 'longcat';
  const llmEnabled = Boolean(getNestedValue(draftConfig, 'llm.enabled', true));
  const mineruEnabled = Boolean(getNestedValue(draftConfig, 'mineru.enabled', true));
  const mineruMode = getNestedValue(draftConfig, 'mineru.mode', 'api');
  const engineMode = getNestedValue(draftConfig, 'desktop.engine.mode', 'bundled');
  const currentStep = wizardSteps[step];
  const isLastStep = step === wizardSteps.length - 1;
  const recommendedEngine = getNestedValue(env, 'recommendation.engineMode', engineMode);
  const recommendedAnalysisMode = getNestedValue(env, 'recommendation.analysisMode', 'regex');
  const readinessSummary = getNestedValue(env, 'readiness.summary', '环境检测已完成。');
  const networkAvailable = Boolean(getNestedValue(env, 'checks.network.available', false));
  const systemPythonReady = Boolean(getNestedValue(env, 'checks.systemPython.available', false)) && Boolean(getNestedValue(env, 'checks.systemPython.hasPaperInsight', false));
  const wizardIntro = step === 0
    ? '别担心，先让我帮您看看这台电脑现在能不能直接用。'
    : step === 1
      ? llmEnabled
        ? '这一步只在您想启用智能提取时才需要填写，不急着用可以先关闭。'
        : '您当前选择的是离线基础版，这一步可以直接跳过 API 配置。'
      : step === 2
        ? mineruEnabled
          ? '这一步是给 PDF 拆解助手做准备，大多数人优先用 API 模式就行。'
          : '您当前先不开启 MinerU，会走更基础但更省心的流程。'
        : '最后再一起确认一遍，确认没问题就保存。';
  const wizardChecklist = [
    `现在在第 ${step + 1} 步，共 ${wizardSteps.length} 步`,
    '桌面端和命令行会共用同一份配置',
    '您填写的 Key 和 Token 只保存在本机'
  ];

  return (
    <div className="wizard-overlay">
      <div className="wizard-card">
        <div className="wizard-header">
          <div>
            <span className="eyebrow">首次启动向导</span>
            <h2>{currentStep.title}</h2>
            <p>您可以先用“离线基础版”直接上手，也可以补齐 Longcat / MinerU 做联网增强。配好后命令行和桌面版都会共用这份配置。</p>
          </div>
        </div>

        <section className="wizard-assistant-banner">
          <div>
            <strong>把它当成装机小助手就行</strong>
            <p>{wizardIntro}</p>
          </div>
          <div className="wizard-checklist">
            {wizardChecklist.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </section>

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
                <h3>先看一眼环境</h3>
                <p>这一步只是帮您确认软件现在能不能顺利启动，不会改坏任何设置。</p>
              </section>
              <section className="wizard-info-block teal">
                <h3>桌面版默认怎么跑</h3>
                <p>桌面版默认使用内置后端，也就是“装好就能用”的模式。大多数人不用自己折腾 Python。</p>
              </section>
              <section className="wizard-info-block sand full">
                <h3>您现在看到的结果</h3>
                <p>{readinessSummary}</p>
                <div className="wizard-inline-pills">
                  <span>默认后端：内置后端 bundled</span>
                  <span>{booleanStatusLabel(networkAvailable, '基础联网可用', '基础联网受限')}</span>
                  <span>{booleanStatusLabel(systemPythonReady, '系统 Python 可作为备用', '系统 Python 还不能直接备用')}</span>
                  <span>推荐分析模式：{modeLabel(recommendedAnalysisMode)}</span>
                </div>
              </section>
              <section className="wizard-info-block full recommendation">
                <h3>推荐先这样开始</h3>
                <p>如果您只是想先跑通软件，建议先使用“离线基础版”：不开启 Longcat、不启用 MinerU，先把论文目录选好直接分析。后面再补 API 也不迟。</p>
                <div className="inline-actions">
                  <button className="ghost small" onClick={() => onSkip(buildBasicOnboardingConfig(draftConfig, env))}>先用离线基础版</button>
                </div>
              </section>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="wizard-form-grid">
              <section className="wizard-choice-card wide-field">
                <h3>Longcat 智能提取</h3>
                <p className="wizard-hint">如果您想让软件走智能 API 提取，就打开它并填写 Key；如果只想先能用，直接关闭也可以。</p>
                <div className="inline-actions">
                  <button className="ghost small" onClick={() => window.paperInsight.openExternal('https://longcat.chat/platform/docs/zh/')}>打开 Longcat 文档</button>
                  <button className="ghost small" onClick={() => setDraftValue('llm.enabled', !llmEnabled)}>{llmEnabled ? '先关闭 Longcat' : '启用 Longcat'}</button>
                </div>
              </section>
              <div className="toggle-grid single wizard-toggle wide-field">
                <label><input type="checkbox" checked={llmEnabled} onChange={(event) => setDraftValue('llm.enabled', event.target.checked)} />启用 Longcat 智能提取</label>
              </div>
              {llmEnabled ? (
                <>
                  <label className="field compact wide-field">
                    <span>Longcat API Key</span>
                    <input type="password" value={getNestedValue(draftConfig, 'llm.api_key', '')} onChange={(event) => setDraftValue('llm.api_key', event.target.value)} placeholder="请粘贴您的 Longcat API Key" />
                  </label>
                  <label className="field compact wide-field">
                    <span>连接地址 / 中转地址</span>
                    <input value={getNestedValue(draftConfig, 'llm.base_url', '')} onChange={(event) => setDraftValue('llm.base_url', event.target.value)} placeholder="不知道就先留空，需要中转时再填" />
                  </label>
                  <label className="field compact wide-field">
                    <span>模型名称</span>
                    <select value={getNestedValue(draftConfig, 'llm.model', 'LongCat-Flash-Chat')} onChange={(event) => setDraftValue('llm.model', event.target.value)}>
                      <option value="LongCat-Flash-Chat">LongCat-Flash-Chat - 通用版，适合大多数人</option>
                      <option value="LongCat-Flash-Thinking">LongCat-Flash-Thinking - 更偏深度思考</option>
                      <option value="LongCat-Flash-Thinking-2601">LongCat-Flash-Thinking-2601 - Thinking 的升级版</option>
                      <option value="LongCat-Flash-Lite">LongCat-Flash-Lite - 更轻更省</option>
                      <option value="LongCat-Flash-Omni-2603">LongCat-Flash-Omni-2603 - 多模态版本</option>
                    </select>
                  </label>
                </>
              ) : (
                <section className="wizard-choice-card wide-field">
                  <h3>已切换为离线基础版</h3>
                  <p className="wizard-hint">当前不会要求您填写 API Key。之后如果需要更完整的智能提取，再回来开启 Longcat 即可。</p>
                </section>
              )}
            </div>
          ) : null}

          {step === 2 ? (
            <div className="wizard-form-grid">
              <section className="wizard-choice-card wide-field">
                <h3>MinerU 是什么</h3>
                <p className="wizard-hint">把它理解成“更会拆 PDF 的帮手”就行。大多数用户建议优先用 API 模式。</p>
                <div className="inline-actions">
                  <button className="ghost small" onClick={() => window.paperInsight.openExternal('https://mineru.net/apiManage/token')}>打开 MinerU Token 申请页</button>
                  <button className="ghost small" onClick={() => setDraftValue('mineru.enabled', !mineruEnabled)}>{mineruEnabled ? '先关闭 MinerU' : '启用 MinerU'}</button>
                </div>
                <p className="wizard-hint">提醒：第一次申请可能要等一会儿，Token 一般只有 90 天有效期。</p>
              </section>
              <div className="toggle-grid single wizard-toggle wide-field">
                <label><input type="checkbox" checked={Boolean(getNestedValue(draftConfig, 'mineru.enabled', true))} onChange={(event) => setDraftValue('mineru.enabled', event.target.checked)} />启用 MinerU。开了之后，通常 PDF 拆得更完整。</label>
              </div>
              <label className="field compact">
                <span>MinerU 模式</span>
                <select value={getNestedValue(draftConfig, 'mineru.mode', 'api')} onChange={(event) => setDraftValue('mineru.mode', event.target.value)}>
                  <option value="api">api - 推荐，大多数用户选这个</option>
                  <option value="cli">cli - 适合会自己装环境的人</option>
                </select>
              </label>
              <label className="field compact">
                <span>MinerU Token</span>
                <input type="password" value={getNestedValue(draftConfig, 'mineru.token', '')} onChange={(event) => setDraftValue('mineru.token', event.target.value)} placeholder="如果您选 api，这里就要填写 Token" />
              </label>
              <label className="field compact">
                <span>模型版本</span>
                <select value={getNestedValue(draftConfig, 'mineru.model_version', 'vlm')} onChange={(event) => setDraftValue('mineru.model_version', event.target.value)}>
                  <option value="vlm">vlm - 推荐，适合大多数论文</option>
                  <option value="pipeline">pipeline - 偏兼容场景</option>
                  <option value="MinerU-HTML">MinerU-HTML - 偏 HTML 结果</option>
                </select>
              </label>
              <label className="field compact">
                <span>输出格式</span>
                <select value={getNestedValue(draftConfig, 'mineru.output_format', 'markdown')} onChange={(event) => setDraftValue('mineru.output_format', event.target.value)}>
                  <option value="markdown">markdown - 更适合后续继续分析</option>
                  <option value="json">json - 更适合程序读取</option>
                </select>
              </label>
              <label className="field compact wide-field">
                <span>解析方式</span>
                <select value={getNestedValue(draftConfig, 'mineru.method', 'auto')} onChange={(event) => setDraftValue('mineru.method', event.target.value)}>
                  <option value="auto">auto - 让程序自己判断，推荐</option>
                  <option value="txt">txt - 更偏向直接读文字</option>
                  <option value="ocr">ocr - 更偏向识别扫描图像</option>
                </select>
              </label>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="wizard-summary-grid">
              <section className="wizard-summary-card">
                <span>环境</span>
                <strong>基础环境检查已完成</strong>
                <p>桌面版默认会使用 bundled 内置后端；命令行和桌面端会共用同一份配置。</p>
              </section>
              <section className="wizard-summary-card">
                <span>Longcat</span>
                <strong>{llmEnabled ? getNestedValue(draftConfig, 'llm.model', 'LongCat-Flash-Chat') : '未启用，先走离线基础版'}</strong>
                <p>{llmEnabled ? (getNestedValue(draftConfig, 'llm.base_url', '').trim() ? `您填写了连接地址：${getNestedValue(draftConfig, 'llm.base_url', '')}` : '您没有填写连接地址，程序会优先走默认官方地址。') : '当前不会要求 API Key，也不会阻塞您先开始使用。'}</p>
              </section>
              <section className="wizard-summary-card">
                <span>MinerU</span>
                <strong>{mineruEnabled ? `${mineruMode} 模式` : '已关闭，先走基础解析'}</strong>
                <p>{mineruEnabled ? `模型版本：${getNestedValue(draftConfig, 'mineru.model_version', 'vlm')}；输出格式：${getNestedValue(draftConfig, 'mineru.output_format', 'markdown')}；解析方式：${getNestedValue(draftConfig, 'mineru.method', 'auto')}` : '后续如果需要更完整的 PDF 拆解，可以再回来启用。'}</p>
              </section>
              <section className="wizard-summary-card full">
                <span>确认后会发生什么</span>
                <strong>保存到同一份用户配置</strong>
                <p>点“完成配置”后，这份设置会立刻写入本机配置文件。之后无论您用命令行还是桌面端，都会直接读取这份配置。</p>
              </section>
            </div>
          ) : null}
        </div>
        {error ? <div className="wizard-error">{error}</div> : null}

        <div className="wizard-actions">
          <div className="action-row">
            <button className="ghost" onClick={onBack} disabled={step === 0 || saving}>上一步</button>
            {step === 0 ? (
              <button className="ghost" onClick={() => onSkip(buildBasicOnboardingConfig(draftConfig, env))} disabled={saving}>先用离线基础版</button>
            ) : null}
          </div>
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

export default OnboardingModal;