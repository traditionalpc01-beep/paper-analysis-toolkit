import React, { useEffect, useMemo, useState } from 'react';

const tabs = [
  { id: 'analyze', label: '分析工作台' },
  { id: 'settings', label: '服务配置' },
  { id: 'help', label: '关于与帮助' }
];

const wizardSteps = [
  { id: 'environment', title: '检查环境' },
  { id: 'longcat', title: '配置 Longcat' },
  { id: 'mineru', title: '配置 MinerU' },
  { id: 'review', title: '确认并保存' }
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

const supportLinks = [
  { label: '项目仓库', url: 'https://github.com/traditionalpc01-beep/paper-analysis-toolkit' },
  { label: '提交 Issue', url: 'https://github.com/traditionalpc01-beep/paper-analysis-toolkit/issues' },
  { label: 'Releases 下载页', url: 'https://github.com/traditionalpc01-beep/paper-analysis-toolkit/releases' },
  { label: 'GitHub Actions', url: 'https://github.com/traditionalpc01-beep/paper-analysis-toolkit/actions' },
  { label: 'OpenAI 平台', url: 'https://platform.openai.com/' },
  { label: 'DeepSeek 平台', url: 'https://platform.deepseek.com/' },
  { label: 'Longcat 文档', url: 'https://longcat.chat/platform/docs/zh/' },
  { label: 'MinerU Token 申请页', url: 'https://mineru.net/apiManage/token' },
  { label: 'MinerU 官网', url: 'https://mineru.net/' }
];

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

function defaultOutputDir(pdfDir) {
  const normalized = `${pdfDir || ''}`.trim();
  return normalized ? `${normalized}/output` : '';
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

function engineModeLabel(mode) {
  const mapping = {
    bundled: '内置后端',
    system_python: '系统 Python',
    manual_check: '需手动检查'
  };
  return mapping[mode] || mode;
}

function readinessLabel(status) {
  const mapping = {
    ready: '环境就绪',
    limited: '可启动，建议兜底',
    blocked: '需修复环境'
  };
  return mapping[status] || status;
}

function booleanStatusLabel(value, positive = '可用', negative = '不可用') {
  return value ? positive : negative;
}

function canApplyRecommendedEngine(mode) {
  return mode === 'bundled' || mode === 'system_python';
}

function buildRecommendedConfig(config, env) {
  const recommendedEngine = getNestedValue(env, 'recommendation.engineMode', '');
  if (!canApplyRecommendedEngine(recommendedEngine)) {
    return cloneConfig(config);
  }

  let nextConfig = setNestedValue(config, 'desktop.engine.mode', recommendedEngine);
  if (recommendedEngine === 'system_python') {
    const executable = getNestedValue(env, 'checks.systemPython.executable', '').trim();
    const command = getNestedValue(env, 'checks.systemPython.command', '').trim();
    const currentPythonPath = getNestedValue(config, 'desktop.engine.python_path', '').trim();
    if (!currentPythonPath && (executable || command)) {
      nextConfig = setNestedValue(
        nextConfig,
        'desktop.engine.python_path',
        executable || command
      );
    }
  }
  return nextConfig;
}

function hasLlmCredentials(config) {
  const provider = getNestedValue(config, 'llm.provider', 'longcat');
  const llmEnabled = Boolean(getNestedValue(config, 'llm.enabled', true));
  if (!llmEnabled) {
    return false;
  }
  if (provider === 'wenxin') {
    return Boolean(
      getNestedValue(config, 'llm.wenxin.client_id', '').trim() &&
      getNestedValue(config, 'llm.wenxin.client_secret', '').trim()
    );
  }
  return Boolean(getNestedValue(config, 'llm.api_key', '').trim());
}

function buildRecommendedOnboardingConfig(config, env) {
  let nextConfig = buildRecommendedConfig(config, env);
  const networkAvailable = Boolean(getNestedValue(env, 'checks.network.available', false));

  nextConfig = setNestedValue(nextConfig, 'llm.enabled', true);
  nextConfig = setNestedValue(nextConfig, 'llm.provider', 'longcat');
  nextConfig = setNestedValue(nextConfig, 'llm.model', getNestedValue(nextConfig, 'llm.model', 'LongCat-Flash-Chat') || 'LongCat-Flash-Chat');
  nextConfig = setNestedValue(nextConfig, 'mineru.enabled', true);
  nextConfig = setNestedValue(nextConfig, 'mineru.mode', getNestedValue(nextConfig, 'mineru.mode', 'api') || 'api');
  nextConfig = setNestedValue(nextConfig, 'mineru.model_version', getNestedValue(nextConfig, 'mineru.model_version', 'vlm') || 'vlm');
  nextConfig = setNestedValue(nextConfig, 'mineru.output_format', getNestedValue(nextConfig, 'mineru.output_format', 'markdown') || 'markdown');
  nextConfig = setNestedValue(nextConfig, 'mineru.method', getNestedValue(nextConfig, 'mineru.method', 'auto') || 'auto');
  nextConfig = setNestedValue(nextConfig, 'desktop.engine.mode', 'bundled');

  if (!networkAvailable) {
    nextConfig = setNestedValue(nextConfig, 'web_search.enabled', false);
  }

  return nextConfig;
}

function buildBasicOnboardingConfig(config, env) {
  let nextConfig = buildRecommendedConfig(config, env);
  nextConfig = setNestedValue(nextConfig, 'desktop.engine.mode', 'bundled');
  nextConfig = setNestedValue(nextConfig, 'llm.enabled', false);
  nextConfig = setNestedValue(nextConfig, 'mineru.enabled', false);
  nextConfig = setNestedValue(nextConfig, 'web_search.enabled', false);
  nextConfig = setNestedValue(nextConfig, 'output.format', ['excel']);
  return nextConfig;
}

function buildEnvironmentAlerts(env, config, runOptions) {
  const alerts = [];
  const readinessStatus = getNestedValue(env, 'readiness.status', 'limited');
  const recommendedEngine = getNestedValue(env, 'recommendation.engineMode', '');
  const currentEngine = getNestedValue(config, 'desktop.engine.mode', 'bundled');
  const networkAvailable = Boolean(getNestedValue(env, 'checks.network.available', false));
  const llmEnabled = Boolean(getNestedValue(config, 'llm.enabled', true));
  const currentMode = runOptions.mode || 'auto';
  const systemPythonAvailable = Boolean(getNestedValue(env, 'checks.systemPython.available', false));
  const systemPythonReady = systemPythonAvailable && Boolean(getNestedValue(env, 'checks.systemPython.hasPaperInsight', false));

  if (readinessStatus === 'blocked') {
    alerts.push({
      id: 'engine-blocked',
      severity: 'danger',
      title: '当前没有可直接启动的运行引擎',
      description: getNestedValue(env, 'readiness.summary', '请先检查内置后端或系统 Python。'),
      actions: ['open_settings', 'reopen_onboarding']
    });
  }

  if (!networkAvailable) {
    alerts.push({
      id: 'network-offline',
      severity: 'warning',
      title: '基础联网受限，建议先用正则兜底',
      description: getNestedValue(env, 'checks.network.message', '网络不可用时，API 提取和联网补全都可能失败。'),
      actions: ['use_regex', 'open_settings']
    });
  }

  if (llmEnabled && !hasLlmCredentials(config)) {
    alerts.push({
      id: 'llm-missing-creds',
      severity: 'warning',
      title: '已开启 LLM，但还没有完整 API 凭据',
      description: '可以去设置页补齐 API Key，或者先关闭 LLM / 切换到正则兜底。',
      actions: ['open_settings', 'use_regex']
    });
  }

  if (currentEngine === 'system_python' && !systemPythonReady) {
    alerts.push({
      id: 'python-unready',
      severity: 'danger',
      title: '当前选择了系统 Python，但该环境还不能直接运行',
      description: getNestedValue(env, 'checks.systemPython.message', '请检查 Python 路径和 paperinsight 安装状态。'),
      actions: ['apply_recommendation', 'open_settings']
    });
  }

  if (canApplyRecommendedEngine(recommendedEngine) && currentEngine !== recommendedEngine) {
    alerts.push({
      id: 'engine-drift',
      severity: 'info',
      title: '当前引擎与推荐值不一致',
      description: `推荐使用 ${engineModeLabel(recommendedEngine)}，可一键应用推荐启动设置。`,
      actions: ['apply_recommendation']
    });
  }

  if (currentMode === 'api' && !networkAvailable) {
    alerts.push({
      id: 'api-offline',
      severity: 'warning',
      title: '当前运行模式是智能 API，但网络不可用',
      description: '建议切回正则兜底，避免启动后立刻失败。',
      actions: ['use_regex']
    });
  }

  return alerts;
}

function hasConfiguredCredentials(config) {
  const provider = getNestedValue(config, 'llm.provider', 'longcat');
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
  if (step === 1 && Boolean(getNestedValue(draftConfig, 'llm.enabled', true))) {
    if (!getNestedValue(draftConfig, 'llm.api_key', '').trim()) {
      return '请先填写 Longcat API Key。';
    }
    if (!getNestedValue(draftConfig, 'llm.model', '').trim()) {
      return '请先选择一个 Longcat 模型。';
    }
  }

  if (step === 2 && Boolean(getNestedValue(draftConfig, 'mineru.enabled', true))) {
    if (getNestedValue(draftConfig, 'mineru.mode', 'api') === 'api' && !getNestedValue(draftConfig, 'mineru.token', '').trim()) {
      return '您选择了 MinerU API，请先填写 Token。';
    }
    if (!getNestedValue(draftConfig, 'mineru.model_version', '').trim()) {
      return '请先选择 MinerU 模型版本。';
    }
    if (!getNestedValue(draftConfig, 'mineru.output_format', '').trim()) {
      return '请先选择 MinerU 输出格式。';
    }
    if (!getNestedValue(draftConfig, 'mineru.method', '').trim()) {
      return '请先选择 MinerU 解析方式。';
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
  if (event.type === 'process-exit') {
    return event.code === 0 ? '后台进程已结束' : `后台进程异常退出（${event.code}）`;
  }
  return `${event.type}`;
}

function formatImpactFactor(value) {
  if (value === null || value === undefined || value === '') {
    return '未补全';
  }
  return `${value}`;
}

function matchesQuery(values, query) {
  if (!query) {
    return true;
  }
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return values.some((value) => `${value || ''}`.toLowerCase().includes(normalized));
}

function displayValue(value, fallback = '未设置') {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return `${value}`;
}

function maskedStatus(value, configuredLabel = '已填写', emptyLabel = '未填写') {
  return String(value || '').trim() ? configuredLabel : emptyLabel;
}

function buildGettingStartedSteps(config, env, runOptions, onboardingCompleted) {
  const pdfDir = String(runOptions.pdfDir || '').trim();
  const outputDir = String(runOptions.outputDir || defaultOutputDir(pdfDir)).trim();
  const hasApiKey = hasLlmCredentials(config);
  const mineruEnabled = Boolean(getNestedValue(config, 'mineru.enabled', true));
  const mineruMode = getNestedValue(config, 'mineru.mode', 'api');
  const hasMineruToken = String(getNestedValue(config, 'mineru.token', '') || '').trim().length > 0;
  const networkAvailable = Boolean(getNestedValue(env, 'checks.network.available', false));

  return [
    {
      id: 'guide-onboarding',
      title: onboardingCompleted ? '先确认配置状态' : '先完成首次配置',
      description: onboardingCompleted
        ? '如果你不确定当前配置是否可用，先重新打开向导检查一遍最稳妥。'
        : '第一次使用建议先走一次向导，按顺序把 Longcat、MinerU 和启动方式配好。',
      status: onboardingCompleted ? '已完成' : '待处理',
      action: 'reopen_onboarding',
      actionLabel: onboardingCompleted ? '检查向导' : '开始向导'
    },
    {
      id: 'guide-input',
      title: '再选择 PDF 和输出目录',
      description: pdfDir
        ? `已选论文目录：${pdfDir}${outputDir ? `；输出目录：${outputDir}` : '；建议顺手确认输出目录' }`
        : '到下方“输入与输出”里先选论文文件夹；不会改动原 PDF 内容。',
      status: pdfDir ? '已选择' : '待处理',
      action: 'focus_input',
      actionLabel: '去选目录'
    },
    {
      id: 'guide-run',
      title: '最后点开始分析',
      description: hasApiKey && (!mineruEnabled || mineruMode !== 'api' || hasMineruToken)
        ? `核心凭据已具备${networkAvailable ? '，可以直接尝试运行。' : '，但当前网络受限，建议先切到正则兜底。'}`
        : '如果还没填好 API Key 或 MinerU Token，先去设置页补齐，再开始处理。',
      status: hasApiKey && (!mineruEnabled || mineruMode !== 'api' || hasMineruToken) ? '可启动' : '待补齐',
      action: hasApiKey && (!mineruEnabled || mineruMode !== 'api' || hasMineruToken) ? 'start_analysis' : 'open_settings',
      actionLabel: hasApiKey && (!mineruEnabled || mineruMode !== 'api' || hasMineruToken) ? '开始分析' : '去补配置'
    }
  ];
}

function buildSetupChecklist(config, env, onboardingCompleted, runOptions) {
  const provider = getNestedValue(config, 'llm.provider', 'longcat');
  const mineruEnabled = Boolean(getNestedValue(config, 'mineru.enabled', true));
  const mineruMode = getNestedValue(config, 'mineru.mode', 'api');
  const network = getNestedValue(env, 'checks.network', {});
  const systemPython = getNestedValue(env, 'checks.systemPython', {});
  const bundledBackend = getNestedValue(env, 'checks.bundledBackend', {});

  return [
    {
      label: '首次向导',
      value: onboardingCompleted ? '已完成' : '待完成',
      tone: onboardingCompleted ? 'good' : 'warning',
      detail: onboardingCompleted ? '桌面端和命令行将共用这份配置。' : '建议先按向导一步步配置。'
    },
    {
      label: 'Longcat API Key',
      value: maskedStatus(getNestedValue(config, 'llm.api_key', '')),
      tone: hasLlmCredentials(config) ? 'good' : 'warning',
      detail: `当前提供商：${formatProviderLabel(provider)}`
    },
    {
      label: 'MinerU Token',
      value: !mineruEnabled ? '未启用' : mineruMode !== 'api' ? 'CLI 模式无需 Token' : maskedStatus(getNestedValue(config, 'mineru.token', '')),
      tone: !mineruEnabled || mineruMode !== 'api' || String(getNestedValue(config, 'mineru.token', '') || '').trim() ? 'good' : 'warning',
      detail: mineruEnabled ? `当前模式：${mineruMode === 'api' ? '云端 API' : '本地 CLI'}` : '当前未启用 MinerU'
    },
    {
      label: '基础联网',
      value: booleanStatusLabel(Boolean(network.available), '可用', '受限'),
      tone: Boolean(network.available) ? 'good' : 'warning',
      detail: displayValue(network.message, '尚未检测')
    },
    {
      label: '内置后端',
      value: booleanStatusLabel(Boolean(bundledBackend.available), '可用', '未检测到'),
      tone: Boolean(bundledBackend.available) ? 'good' : 'warning',
      detail: displayValue(bundledBackend.message, '尚未检测')
    },
    {
      label: '系统 Python',
      value: Boolean(systemPython.available) && Boolean(systemPython.hasPaperInsight) ? '可直接备用' : Boolean(systemPython.available) ? '已找到但未装 paperinsight' : '不可用',
      tone: Boolean(systemPython.available) && Boolean(systemPython.hasPaperInsight) ? 'good' : 'muted',
      detail: displayValue(systemPython.message, '尚未检测')
    }
  ];
}

function buildEnvironmentDetails(env, config) {
  const checks = getNestedValue(env, 'checks', {});
  const provider = formatProviderLabel(getNestedValue(config, 'llm.provider', 'longcat'));
  const llmReady = hasLlmCredentials(config);
  const mineruEnabled = Boolean(getNestedValue(config, 'mineru.enabled', true));
  const mineruMode = getNestedValue(config, 'mineru.mode', 'api');
  const mineruReady = !mineruEnabled || mineruMode !== 'api' || Boolean(String(getNestedValue(config, 'mineru.token', '') || '').trim());

  return [
    {
      title: '内置后端检测',
      status: booleanStatusLabel(Boolean(getNestedValue(checks, 'bundledBackend.available', false)), '可用', '未检测到'),
      tone: Boolean(getNestedValue(checks, 'bundledBackend.available', false)) ? 'good' : 'warning',
      detail: displayValue(getNestedValue(checks, 'bundledBackend.message', ''), '未返回检测结果')
    },
    {
      title: '系统 Python 检测',
      status: Boolean(getNestedValue(checks, 'systemPython.available', false)) && Boolean(getNestedValue(checks, 'systemPython.hasPaperInsight', false))
        ? '可直接使用'
        : Boolean(getNestedValue(checks, 'systemPython.available', false))
          ? '需要补装 paperinsight'
          : '不可用',
      tone: Boolean(getNestedValue(checks, 'systemPython.available', false)) && Boolean(getNestedValue(checks, 'systemPython.hasPaperInsight', false)) ? 'good' : 'warning',
      detail: displayValue(getNestedValue(checks, 'systemPython.message', ''), '未返回检测结果')
    },
    {
      title: '联网检测',
      status: booleanStatusLabel(Boolean(getNestedValue(checks, 'network.available', false)), '已联网', '网络受限'),
      tone: Boolean(getNestedValue(checks, 'network.available', false)) ? 'good' : 'warning',
      detail: displayValue(getNestedValue(checks, 'network.message', ''), '未返回检测结果')
    },
    {
      title: `${provider} 凭据`,
      status: llmReady ? '已可用' : '待填写',
      tone: llmReady ? 'good' : 'warning',
      detail: llmReady ? '已检测到可用于语义提取的凭据。' : '还没有完整 API 凭据，建议先去服务配置页补齐。'
    },
    {
      title: 'MinerU 配置',
      status: mineruReady ? '已就绪' : '待填写 Token',
      tone: mineruReady ? 'good' : 'warning',
      detail: mineruEnabled
        ? `当前模式：${mineruMode === 'api' ? '云端 API' : '本地 CLI'}`
        : '当前未启用 MinerU，将使用基础 PDF 解析流程。'
    }
  ];
}

function buildAnalysisGuard(config, env, runOptions, onboardingCompleted) {
  const issues = [];
  const mode = runOptions.mode || 'auto';
  const pdfDir = String(runOptions.pdfDir || '').trim();
  const llmReady = hasLlmCredentials(config);
  const mineruEnabled = Boolean(getNestedValue(config, 'mineru.enabled', true));
  const mineruMode = getNestedValue(config, 'mineru.mode', 'api');
  const mineruToken = String(getNestedValue(config, 'mineru.token', '') || '').trim();
  const networkAvailable = Boolean(getNestedValue(env, 'checks.network.available', false));

  if (!onboardingCompleted) {
    issues.push({
      id: 'onboarding',
      level: 'blocked',
      title: '还没有完成首次配置',
      description: '请先把首次向导走完，再开始处理论文，这样桌面端和命令行都会共用同一份配置。',
      action: 'reopen_onboarding',
      actionLabel: '完成首次配置'
    });
  }

  if (!pdfDir) {
    issues.push({
      id: 'pdf-dir',
      level: 'blocked',
      title: '还没有选择论文目录',
      description: '请先选择存放 PDF 的文件夹，软件才知道要处理哪一批论文。',
      action: 'focus_input',
      actionLabel: '去选论文目录'
    });
  }

  if ((mode === 'api' || mode === 'auto') && !llmReady) {
    issues.push({
      id: 'llm-creds',
      level: 'blocked',
      title: '当前模式需要可用的 LLM 凭据',
      description: '你现在选的是自动模式或智能 API 模式，但还没有完整 API Key，直接开始容易失败。',
      action: 'open_settings',
      actionLabel: '去补 API Key'
    });
  }

  if (mode === 'api' && !networkAvailable) {
    issues.push({
      id: 'network',
      level: 'blocked',
      title: '当前网络受限，不适合直接走智能 API',
      description: '建议先切到正则兜底，或者等网络恢复后再开始。',
      action: 'use_regex',
      actionLabel: '切到正则兜底'
    });
  }

  if (mineruEnabled && mineruMode === 'api' && !mineruToken) {
    issues.push({
      id: 'mineru-token',
      level: 'warning',
      title: 'MinerU 已启用，但还没有填写 Token',
      description: '这会影响更完整的 PDF 拆解效果。你可以先补 Token，或去设置页把 MinerU 改成本地 CLI / 暂时关闭。',
      action: 'open_settings',
      actionLabel: '去看 MinerU 设置'
    });
  }

  return {
    blockingIssues: issues.filter((item) => item.level === 'blocked'),
    warningIssues: issues.filter((item) => item.level === 'warning')
  };
}

function buildRunSummary(config, env, runOptions) {
  const provider = formatProviderLabel(getNestedValue(config, 'llm.provider', 'longcat'));
  const mineruEnabled = Boolean(getNestedValue(config, 'mineru.enabled', true));
  const mineruMode = getNestedValue(config, 'mineru.mode', 'api');
  return [
    ['论文目录', displayValue(runOptions.pdfDir, '未选择')],
    ['输出目录', displayValue(runOptions.outputDir || defaultOutputDir(runOptions.pdfDir), '未设置')],
    ['处理模式', modeLabel(runOptions.mode)],
    ['LLM 服务', `${provider} / ${displayValue(getNestedValue(config, 'llm.model', ''), '未设置模型')}`],
    ['MinerU', mineruEnabled ? `已启用（${mineruMode === 'api' ? '云端 API' : '本地 CLI'}）` : '未启用'],
    ['基础联网', booleanStatusLabel(Boolean(getNestedValue(env, 'checks.network.available', false)), '可用', '受限')],
    ['扫描方式', runOptions.recursive ? '递归扫描子目录' : '只处理当前目录'],
    ['附加输出', runOptions.exportJson ? 'Excel + JSON' : '仅 Excel']
  ];
}

function classifyErrorItem(item) {
  const text = `${item?.context || ''} ${item?.type || ''} ${item?.message || ''}`.toLowerCase();
  if (text.includes('token') || text.includes('api key') || text.includes('credential') || text.includes('鉴权') || text.includes('401') || text.includes('403')) {
    return '凭据或权限问题';
  }
  if (text.includes('network') || text.includes('timeout') || text.includes('连接') || text.includes('联网') || text.includes('dns') || text.includes('socket')) {
    return '网络或连接问题';
  }
  if (text.includes('mineru')) {
    return 'MinerU 解析问题';
  }
  if (text.includes('pdf') || text.includes('ocr') || text.includes('page') || text.includes('文件')) {
    return 'PDF 文件或内容问题';
  }
  return '其他问题';
}

function buildFailureFixSuggestions(groupedErrorItems) {
  const suggestionMap = {
    '凭据或权限问题': {
      title: '先检查 API Key / Token / 权限',
      description: '这类问题通常不是 PDF 本身坏了，而是服务没有授权成功。',
      actions: ['去服务配置页补 API Key 或 Token', '确认当前账号确实有对应模型或服务权限', '如果是 Longcat / MinerU 新凭据，保存后再重试']
    },
    '网络或连接问题': {
      title: '先确认联网，再决定是否切兜底',
      description: '这类问题大多和网络、代理、超时有关。',
      actions: ['先确认当前电脑能正常联网', '如果只是想先跑通流程，可以切到“正则兜底”模式', '如果你使用了 Base URL / 中转地址，确认地址是否可访问']
    },
    'MinerU 解析问题': {
      title: '优先检查 MinerU 设置',
      description: '这类问题通常和 MinerU 模式、Token 或解析方式有关。',
      actions: ['先确认 MinerU Token 是否有效', '可尝试切换 MinerU 模式或临时关闭 MinerU', '如果是特殊 PDF，可尝试更换 txt / ocr / auto 解析方式']
    },
    'PDF 文件或内容问题': {
      title: '先检查 PDF 本身是否适合解析',
      description: '这类问题通常说明文件本身有损坏、扫描质量差，或者内容结构太特殊。',
      actions: ['先手动打开 PDF，确认文件能正常阅读', '如果是扫描版 PDF，可尝试 OCR 相关方式', '必要时先用少量样本测试，再批量处理']
    },
    '其他问题': {
      title: '先看日志，再逐项排查',
      description: '这类问题暂时没有明显模式，建议先从日志和失败文件开始定位。',
      actions: ['先打开失败项对应文件和日志', '优先确认是否是路径、权限或环境异常', '若重复出现同类错误，再考虑单独做专项修复']
    }
  };

  return groupedErrorItems.map(([groupName, items]) => ({
    groupName,
    count: items.length,
    ...(suggestionMap[groupName] || suggestionMap['其他问题'])
  }));
}

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
              outputDir: event.outputDir || current.outputDir,
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
              currentFile: '',
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

  const heroTitle = useMemo(() => {
    if (activeTab === 'analyze') {
      return '用点选代替命令行';
    }
    if (activeTab === 'help') {
      return '把安装、配置和排障说明收进同一个桌面入口';
    }
    return '把 API Key 和运行模式收进设置页';
  }, [activeTab]);

  const heroDescription = useMemo(() => {
    if (activeTab === 'analyze') {
      return '现在已经加上首次启动向导，新用户第一次打开就能按步骤完成 API Key、引擎和默认项设置；高级用户仍然可以切回系统 Python。';
    }
    if (activeTab === 'help') {
      return '帮助页集中展示版本、路径、常用入口和外部资源，方便普通用户直接查看环境信息、定位结果目录并完成基础排障。';
    }
    return '所有常用配置项都已经收进图形界面，包括 LLM 服务、MinerU、缓存策略和系统 Python 兜底模式。';
  }, [activeTab]);

  const filteredResults = useMemo(() => {
    const stats = job.stats || {};
    const reports = Object.entries(stats.reportFiles || {}).filter(([label, targetPath]) =>
      matchesQuery([label, targetPath], resultQuery)
    );
    const successItems = (stats.successItems || []).filter((item) =>
      matchesQuery([item.file, item.title, item.journal, item.impactFactor, item.bestEqe], resultQuery)
    );
    const errorItems = (stats.errorItems || []).filter((item) =>
      matchesQuery([item.file, item.message, item.context, item.type], resultQuery)
    );

    return { reports, successItems, errorItems };
  }, [job.stats, resultQuery]);

  const groupedErrorItems = useMemo(() => {
    const groups = new Map();
    for (const item of filteredResults.errorItems) {
      const group = classifyErrorItem(item);
      if (!groups.has(group)) {
        groups.set(group, []);
      }
      groups.get(group).push(item);
    }
    return Array.from(groups.entries());
  }, [filteredResults.errorItems]);

  const failureFixSuggestions = useMemo(
    () => buildFailureFixSuggestions(groupedErrorItems),
    [groupedErrorItems]
  );

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
      ...(target === 'pdfDir' && !current.outputDir ? { outputDir: defaultOutputDir(selected) } : {})
    }));
  }

  function updateConfig(path, value) {
    setConfig((current) => setNestedValue(current, path, value));
  }

  function updateWizardConfig(path, value) {
    setWizardConfig((current) => setNestedValue(current, path, value));
  }

  async function persistConfig(nextConfig, successMessage) {
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
  }

  async function saveSettings() {
    setSaveState({ saving: true, message: '', error: '' });
    try {
      await persistConfig(config, '设置已保存。');
    } catch (error) {
      setSaveState({ saving: false, message: '', error: error.message || '保存失败' });
    }
  }

  async function applyRecommendedSetup() {
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
  }

  function useFallbackMode() {
    setRunOptions((current) => ({ ...current, mode: 'regex' }));
  }

  function handleAlertAction(action) {
    if (action === 'open_settings') {
      setActiveTab('settings');
      return;
    }
    if (action === 'reopen_onboarding') {
      reopenOnboarding();
      return;
    }
    if (action === 'use_regex') {
      useFallbackMode();
      return;
    }
    if (action === 'apply_recommendation') {
      applyRecommendedSetup();
    }
  }

  function handleGuideAction(action) {
    if (action === 'reopen_onboarding') {
      reopenOnboarding();
      return;
    }
    if (action === 'open_settings') {
      setActiveTab('settings');
      return;
    }
    if (action === 'use_regex') {
      useFallbackMode();
      return;
    }
    if (action === 'focus_input') {
      setActiveTab('analyze');
      const inputSection = document.getElementById('input-output-card');
      inputSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (action === 'start_analysis') {
      requestStartAnalysis();
    }
  }

  async function finishOnboarding(configToPersist, options = {}) {
    setOnboarding((current) => ({ ...current, saving: true, error: '' }));
    try {
      const nextConfig = await persistConfig(configToPersist, '首次配置已保存。');
      const nextMode = options.mode || (hasLlmCredentials(nextConfig) ? 'api' : 'regex');
      setRunOptions((current) => ({ ...current, mode: nextMode }));
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

  function skipOnboarding(configOverride) {
    finishOnboarding(configOverride || wizardConfig || buildBasicOnboardingConfig(config, env), { mode: 'regex' });
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

  function requestStartAnalysis() {
    const latestGuard = buildAnalysisGuard(config, env, runOptions, onboardingCompleted);
    if (latestGuard.blockingIssues.length) {
      const firstIssue = latestGuard.blockingIssues[0];
      setJob((current) => ({
        ...current,
        status: 'failed',
        logs: [{ id: `${Date.now()}`, text: firstIssue.description, type: 'failed' }, ...current.logs]
      }));
      handleGuideAction(firstIssue.action);
      return;
    }

    setRunConfirmVisible(true);
  }

  async function startAnalysis() {
    setRunConfirmVisible(false);
    const effectiveOutputDir = runOptions.outputDir || defaultOutputDir(runOptions.pdfDir);

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
      outputDir: effectiveOutputDir,
      launch: null
    });

    try {
      await window.paperInsight.startAnalysis({
        ...runOptions,
        outputDir: effectiveOutputDir,
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

  async function openExternal(targetUrl) {
    if (!targetUrl) {
      return;
    }
    await window.paperInsight.openExternal(targetUrl);
  }

  async function showItem(targetPath) {
    if (!targetPath) {
      return;
    }
    await window.paperInsight.showItem(targetPath);
  }

  if (loadState.loading) {
    return <div className="loading-shell">正在启动 PaperInsight Desktop...</div>;
  }

  if (loadState.error || !config) {
    return <div className="loading-shell error">加载失败：{loadState.error}</div>;
  }

  const provider = getNestedValue(config, 'llm.provider', 'longcat');
  const engineMode = getNestedValue(config, 'desktop.engine.mode', 'bundled');
  const onboardingCompleted = Boolean(getNestedValue(config, 'desktop.ui.onboarding_completed', false));
  const recommendedEngine = getNestedValue(env, 'recommendation.engineMode', engineMode);
  const recommendedAnalysisMode = getNestedValue(env, 'recommendation.analysisMode', 'regex');
  const networkAvailable = Boolean(getNestedValue(env, 'checks.network.available', false));
  const systemPythonReady = Boolean(getNestedValue(env, 'checks.systemPython.available', false)) && Boolean(getNestedValue(env, 'checks.systemPython.hasPaperInsight', false));
  const readinessStatus = getNestedValue(env, 'readiness.status', 'limited');
  const lastKnownOutputDir = job.outputDir || getNestedValue(config, 'desktop.ui.last_output_dir', '');
  const recommendationApplicable = canApplyRecommendedEngine(recommendedEngine);
  const currentMatchesRecommendation = engineMode === recommendedEngine && runOptions.mode === recommendedAnalysisMode;
  const environmentAlerts = buildEnvironmentAlerts(env, config, runOptions);
  const gettingStartedSteps = buildGettingStartedSteps(config, env, runOptions, onboardingCompleted);
  const setupChecklist = buildSetupChecklist(config, env, onboardingCompleted, runOptions);
  const environmentDetails = buildEnvironmentDetails(env, config);
  const analysisGuard = buildAnalysisGuard(config, env, runOptions, onboardingCompleted);
  const canStartAnalysis = analysisGuard.blockingIssues.length === 0;
  const runSummary = buildRunSummary(config, env, runOptions);
  const jobStatusLabel = job.running
    ? '正在执行'
    : job.status === 'completed'
      ? '已完成'
      : job.status === 'failed'
        ? '执行失败'
        : job.status === 'cancelled'
          ? '已取消'
          : job.status === 'preparing'
            ? '准备启动'
            : '待启动';
  const jobStatusHint = job.currentFile
    || (job.status === 'failed'
      ? '请查看下方日志定位异常。'
      : job.status === 'completed'
        ? '全部任务已完成。'
        : job.status === 'cancelled'
          ? '任务已取消。'
          : '等待任务开始');
  const overallStatus = analysisGuard.blockingIssues.length
    ? {
        tone: 'danger',
        title: '当前还不能直接开始分析',
        description: analysisGuard.blockingIssues[0]?.description || '请先处理阻塞项。'
      }
    : analysisGuard.warningIssues.length
      ? {
          tone: 'warning',
          title: '可以运行，但建议先补齐部分配置',
          description: analysisGuard.warningIssues[0]?.description || '当前存在非阻塞提醒。'
        }
      : {
          tone: 'good',
          title: '环境和配置已基本就绪',
          description: '可以直接开始分析；如果结果不完整，再回设置页微调。'
        };
  const workflowStages = [
    {
      id: 'pick',
      index: 1,
      title: '选择论文目录',
      description: runOptions.pdfDir ? displayValue(runOptions.pdfDir) : '先选择要处理的 PDF 文件夹',
      status: runOptions.pdfDir ? 'done' : 'current'
    },
    {
      id: 'options',
      index: 2,
      title: '确认处理模式',
      description: `${modeLabel(runOptions.mode)} · ${runOptions.recursive ? '递归扫描' : '仅当前目录'}`,
      status: runOptions.pdfDir ? 'done' : 'pending'
    },
    {
      id: 'run',
      index: 3,
      title: '开始分析',
      description: canStartAnalysis ? '可以直接开始' : '还有配置没补齐',
      status: job.running ? 'current' : job.status === 'completed' ? 'done' : canStartAnalysis ? 'current' : 'pending'
    },
    {
      id: 'result',
      index: 4,
      title: '查看结果',
      description: job.stats ? `已生成 ${Object.keys(job.stats.reportFiles || {}).length} 份输出` : '完成后可打开输出目录查看 Excel',
      status: job.stats ? 'done' : 'pending'
    }
  ];

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
              <span>当前引擎</span>
              <strong>{engineModeLabel(engineMode)}</strong>
            </div>
            <div className="status-card">
              <span>推荐启动</span>
              <strong>{engineModeLabel(recommendedEngine)}</strong>
            </div>
            <div className="status-card cool">
              <span>环境校验</span>
              <strong>{readinessLabel(readinessStatus)}</strong>
            </div>
            <div className="status-card sand">
              <span>基础联网</span>
              <strong>{booleanStatusLabel(networkAvailable, '可用', '受限')}</strong>
            </div>
            <div className="status-card sand">
              <span>Python 兜底</span>
              <strong>{booleanStatusLabel(systemPythonReady, '可用', '待补齐')}</strong>
            </div>
            <div className="status-card">
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
              <h2>{heroTitle}</h2>
              <p>{heroDescription}</p>
              <div className={`overall-status-strip ${overallStatus.tone}`}>
                <strong>{overallStatus.title}</strong>
                <span>{overallStatus.description}</span>
              </div>
            </div>
            <div className="hero-pills">
              <span>{engineModeLabel(recommendedEngine)}</span>
              <span>{modeLabel(runOptions.mode)}</span>
              <span>{runOptions.recursive ? '递归扫描' : '仅当前目录'}</span>
              <span>{runOptions.exportJson ? 'Excel + JSON' : '仅 Excel'}</span>
            </div>
          </header>

          {activeTab === 'analyze' ? (
            <section className="content-grid">
              <article className="panel-card wide quickstart-card">
                <div className="panel-head split">
                  <div>
                    <span className="panel-kicker">Quick Start</span>
                    <h3>第一次使用就按这 3 步走</h3>
                  </div>
                  <div className="action-row">
                    <button className="ghost" onClick={reopenOnboarding}>重新打开向导</button>
                    <button className="ghost" onClick={() => setActiveTab('settings')}>查看服务配置</button>
                  </div>
                </div>
                <div className="quickstart-grid">
                  {gettingStartedSteps.map((item, index) => (
                    <section key={item.id} className="quickstart-step">
                      <div className="quickstart-index">步骤 {index + 1}</div>
                      <strong>{item.title}</strong>
                      <span className={`inline-status ${item.status === '待处理' ? 'warning' : 'good'}`}>{item.status}</span>
                      <p>{item.description}</p>
                      <button className="ghost small" onClick={() => handleGuideAction(item.action)}>{item.actionLabel}</button>
                    </section>
                  ))}
                </div>
              </article>

              <article className="panel-card wide status-overview-card">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">Setup Status</span>
                    <h3>初始化和入口配置一眼看懂</h3>
                  </div>
                </div>
                <div className="setup-checklist-grid">
                  {setupChecklist.map((item) => (
                    <div key={item.label} className={`setup-check-item ${item.tone}`}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.detail}</small>
                    </div>
                  ))}
                </div>
              </article>

              <article className="panel-card wide">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">Preflight</span>
                    <h3>开始分析前，先看这张准备清单</h3>
                  </div>
                </div>
                {analysisGuard.blockingIssues.length ? (
                  <div className="alert-stack compact">
                    {analysisGuard.blockingIssues.map((item) => (
                      <section key={item.id} className="alert-card danger">
                        <div>
                          <strong>{item.title}</strong>
                          <p>{item.description}</p>
                        </div>
                        <div className="inline-actions">
                          <button className="ghost small" onClick={() => handleGuideAction(item.action)}>{item.actionLabel}</button>
                        </div>
                      </section>
                    ))}
                  </div>
                ) : (
                  <div className="preflight-ok">
                    <strong>可以开始分析了</strong>
                    <p>当前没有必须先处理的阻塞项。你可以继续选目录、调整选项，然后直接点击“开始分析”。</p>
                  </div>
                )}
                {analysisGuard.warningIssues.length ? (
                  <div className="alert-stack compact">
                    {analysisGuard.warningIssues.map((item) => (
                      <section key={`warning-${item.id}`} className="alert-card warning">
                        <div>
                          <strong>{item.title}</strong>
                          <p>{item.description}</p>
                        </div>
                        <div className="inline-actions">
                          <button className="ghost small" onClick={() => handleGuideAction(item.action)}>{item.actionLabel}</button>
                        </div>
                      </section>
                    ))}
                  </div>
                ) : null}
              </article>

              <article className="panel-card wide workflow-card">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">Workflow</span>
                    <h3>处理流程</h3>
                  </div>
                </div>
                <div className="workflow-grid">
                  {workflowStages.map((item) => (
                    <section key={item.id} className={`workflow-step ${item.status}`}>
                      <div className="workflow-step-index">0{item.index}</div>
                      <strong>{item.title}</strong>
                      <p>{item.description}</p>
                    </section>
                  ))}
                </div>
              </article>

              <article className="panel-card wide">
                <div className="panel-head split">
                  <div>
                    <span className="panel-kicker">Startup Check</span>
                    <h3>启动建议</h3>
                  </div>
                  <div className="action-row">
                    <button className="ghost" onClick={useFallbackMode}>切到正则兜底</button>
                    <button
                      className="primary"
                      disabled={!recommendationApplicable || saveState.saving || currentMatchesRecommendation}
                      onClick={applyRecommendedSetup}
                    >
                      {currentMatchesRecommendation ? '已应用推荐' : saveState.saving ? '应用中...' : '一键应用推荐'}
                    </button>
                  </div>
                </div>
                <div className={`startup-banner ${readinessStatus}`}>
                  <div>
                    <strong>{getNestedValue(env, 'readiness.summary', '环境检查已完成。')}</strong>
                    <p>
                      推荐引擎：{engineModeLabel(recommendedEngine)}；推荐分析模式：{modeLabel(recommendedAnalysisMode)}。
                      {getNestedValue(env, 'recommendation.engineReason', '')}
                    </p>
                  </div>
                  <div className="startup-badges">
                    <span>{booleanStatusLabel(networkAvailable, '联网可用', '联网受限')}</span>
                    <span>{booleanStatusLabel(systemPythonReady, 'Python 兜底可用', 'Python 兜底待补齐')}</span>
                    <span>{currentMatchesRecommendation ? '当前配置已对齐推荐' : '当前配置未完全对齐推荐'}</span>
                  </div>
                </div>
              </article>

              {environmentAlerts.length ? (
                <article className="panel-card wide">
                  <div className="panel-head">
                    <div>
                      <span className="panel-kicker">Diagnostics</span>
                      <h3>启动异常提示</h3>
                    </div>
                  </div>
                  <div className="alert-stack">
                    {environmentAlerts.map((alert) => (
                      <section key={alert.id} className={`alert-card ${alert.severity}`}>
                        <div>
                          <strong>{alert.title}</strong>
                          <p>{alert.description}</p>
                        </div>
                        <div className="inline-actions">
                          {alert.actions.map((action) => (
                            <button
                              key={action}
                              className="ghost small"
                              onClick={() => handleAlertAction(action)}
                            >
                              {{
                                open_settings: '打开设置',
                                reopen_onboarding: '重新运行向导',
                                use_regex: '切到正则兜底',
                                apply_recommendation: '应用推荐设置'
                              }[action] || action}
                            </button>
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                </article>
              ) : null}

              <article className="panel-card" id="input-output-card">
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
                      placeholder="默认写入 论文目录/output"
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
                      <button className="primary" disabled={!canStartAnalysis} onClick={requestStartAnalysis}>开始分析</button>
                    )}
                  </div>
                </div>
                  <div className="progress-block">
                    <div className="progress-meta">
                      <strong>{jobStatusLabel}</strong>
                      <span>{jobStatusHint}</span>
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

                    <div className="result-toolbar">
                      <label className="field result-search">
                        <span>搜索结果</span>
                        <input
                          value={resultQuery}
                          onChange={(event) => setResultQuery(event.target.value)}
                          placeholder="按文件名、标题、期刊或错误原因搜索"
                        />
                      </label>
                      <div className="scope-switch">
                        {[
                          ['all', '全部'],
                          ['success', '仅成功'],
                          ['error', '仅失败']
                        ].map(([value, label]) => (
                          <button
                            key={value}
                            className={resultScope === value ? 'scope-chip active' : 'scope-chip'}
                            onClick={() => setResultScope(value)}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="result-quick-actions">
                      <button className="ghost small" disabled={!filteredResults.reports.length} onClick={() => openPath(filteredResults.reports[0]?.[1])}>一键打开 Excel</button>
                      <button className="ghost small" disabled={!job.outputDir} onClick={openOutputDir}>一键打开输出目录</button>
                      <button className="ghost small" disabled={!filteredResults.errorItems.length} onClick={() => openPath(filteredResults.errorItems[0]?.path)}>定位第一条失败项</button>
                    </div>

                    <div className="result-grid">
                      <section className="result-card">
                        <div className="result-head">
                          <h4>报表与输出</h4>
                          <button className="ghost small" onClick={openOutputDir}>打开输出目录</button>
                        </div>
                        {filteredResults.reports.length ? (
                          <div className="result-list">
                            {filteredResults.reports.map(([label, targetPath]) => (
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
                          <span>{filteredResults.successItems.length} / {job.stats.successItems?.length || 0} 篇</span>
                        </div>
                        {resultScope !== 'error' && filteredResults.successItems.length ? (
                          <div className="result-list compact">
                            {filteredResults.successItems.map((item) => (
                              <button key={`${item.file}-${item.path}`} className="result-item" onClick={() => openPath(item.path)}>
                                <span>{item.file}</span>
                                <strong>{item.title || '未提取到标题'}</strong>
                                <small>{item.journal || '未提取期刊'} · IF {formatImpactFactor(item.impactFactor)}{item.bestEqe ? ` · EQE ${item.bestEqe}` : ''}</small>
                              </button>
                            ))}
                          </div>
                        ) : resultScope === 'error' ? (
                          <div className="empty-inline">当前筛选为“仅失败”，成功结果已隐藏。</div>
                        ) : (
                          <div className="empty-inline">暂无成功记录。</div>
                        )}
                      </section>

                      <section className="result-card">
                        <div className="result-head">
                          <h4>失败论文</h4>
                          <span>{filteredResults.errorItems.length} / {job.stats.errorItems?.length || 0} 篇</span>
                        </div>
                        {resultScope !== 'success' && filteredResults.errorItems.length ? (
                          <div className="error-group-list">
                            {groupedErrorItems.map(([groupName, items]) => (
                              <section key={groupName} className="error-group-card">
                                <div className="result-head">
                                  <h4>{groupName}</h4>
                                  <span>{items.length} 篇</span>
                                </div>
                                <div className="result-list compact">
                                  {items.map((item) => (
                                    <button key={`${groupName}-${item.file}-${item.path}`} className="result-item danger-soft" onClick={() => openPath(item.path)}>
                                      <span>{item.file || '未知文件'}</span>
                                      <strong>{item.context || item.type || '处理失败'}</strong>
                                      <small>{item.message || '未知错误'}</small>
                                    </button>
                                  ))}
                                </div>
                              </section>
                            ))}
                          </div>
                        ) : resultScope === 'success' ? (
                          <div className="empty-inline">当前筛选为“仅成功”，失败结果已隐藏。</div>
                        ) : (
                          <div className="empty-inline">本次没有失败文件。</div>
                        )}
                      </section>
                    </div>

                    {failureFixSuggestions.length ? (
                      <section className="failure-fix-panel">
                        <div className="result-head">
                          <h4>失败原因对应修复建议</h4>
                          <span>{failureFixSuggestions.length} 类</span>
                        </div>
                        <div className="failure-fix-grid">
                          {failureFixSuggestions.map((item) => (
                            <section key={`fix-${item.groupName}`} className="failure-fix-card">
                              <span>{item.groupName} · {item.count} 篇</span>
                              <strong>{item.title}</strong>
                              <p>{item.description}</p>
                              <div className="failure-fix-actions">
                                {item.actions.map((action) => (
                                  <div key={`${item.groupName}-${action}`}>{action}</div>
                                ))}
                              </div>
                            </section>
                          ))}
                        </div>
                      </section>
                    ) : null}
                  </>
                ) : null}

                <div className="log-panel">
                  {job.logs.length ? job.logs.map((entry) => (
                    <div key={entry.id} className={`log-line ${entry.type}`}>{entry.text}</div>
                  )) : <div className="empty-state">任务日志会显示在这里。</div>}
                </div>
              </article>
            </section>
          ) : activeTab === 'help' ? (
            <section className="content-grid settings-grid">
              <article className="panel-card">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">About</span>
                    <h3>运行环境</h3>
                  </div>
                </div>
                <div className="stat-grid help-stats">
                  <div><span>版本</span><strong>{meta?.version || env?.version || '未知'}</strong></div>
                  <div><span>平台</span><strong>{displayValue(env?.platform)}</strong></div>
                  <div><span>Python</span><strong>{displayValue(env?.pythonExecutable)}</strong></div>
                  <div><span>引擎模式</span><strong>{engineMode === 'bundled' ? '内置后端' : '系统 Python'}</strong></div>
                  <div><span>基础联网</span><strong>{booleanStatusLabel(networkAvailable, '可用', '受限')}</strong></div>
                  <div><span>环境状态</span><strong>{readinessLabel(readinessStatus)}</strong></div>
                </div>
              </article>

              <article className="panel-card">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">Paths</span>
                    <h3>本地路径</h3>
                  </div>
                </div>
                <div className="result-list">
                  {[
                    ['配置文件', meta?.configPath],
                    ['缓存目录', getNestedValue(config, 'cache.directory', '.cache')],
                    ['上次论文目录', getNestedValue(config, 'desktop.ui.last_pdf_dir', '')],
                    ['上次输出目录', getNestedValue(config, 'desktop.ui.last_output_dir', '')]
                  ].map(([label, value]) => (
                    <div key={label} className="result-item static">
                      <span>{label}</span>
                      <strong>{displayValue(value)}</strong>
                      <div className="inline-actions">
                        <button className="ghost small" disabled={!value} onClick={() => openPath(value)}>打开</button>
                        <button className="ghost small" disabled={!value} onClick={() => showItem(value)}>定位</button>
                      </div>
                    </div>
                  ))}
                </div>
              </article>

              <article className="panel-card wide">
                <div className="panel-head split">
                  <div>
                    <span className="panel-kicker">Support</span>
                    <h3>帮助与资源</h3>
                  </div>
                  <button className="ghost" onClick={reopenOnboarding}>重新打开首次向导</button>
                </div>
                <div className="help-grid">
                  <section className="help-card full">
                    <h4>启动建议</h4>
                    <div className="help-notes">
                      <div>
                        <strong>推荐启动方式</strong>
                        <p>{getNestedValue(env, 'recommendation.engineLabel', engineModeLabel(recommendedEngine))}：{getNestedValue(env, 'recommendation.engineReason', '未返回推荐原因。')}</p>
                      </div>
                      <div>
                        <strong>推荐分析模式</strong>
                        <p>{getNestedValue(env, 'recommendation.analysisLabel', modeLabel(recommendedAnalysisMode))}：{getNestedValue(env, 'recommendation.analysisReason', '未返回推荐原因。')}</p>
                      </div>
                      <div>
                        <strong>兜底工具</strong>
                        <p>{getNestedValue(env, 'recommendation.fallbackTool.label', '正则兜底')}：{getNestedValue(env, 'recommendation.fallbackTool.reason', '未返回兜底说明。')}</p>
                      </div>
                    </div>
                  </section>

                  <section className="help-card full">
                    <h4>环境异常与修复建议</h4>
                    {environmentAlerts.length ? (
                      <div className="alert-stack compact">
                        {environmentAlerts.map((alert) => (
                          <section key={`help-${alert.id}`} className={`alert-card ${alert.severity}`}>
                            <div>
                              <strong>{alert.title}</strong>
                              <p>{alert.description}</p>
                            </div>
                            <div className="inline-actions">
                              {alert.actions.map((action) => (
                                <button
                                  key={`help-${alert.id}-${action}`}
                                  className="ghost small"
                                  onClick={() => handleAlertAction(action)}
                                >
                                  {{
                                    open_settings: '打开设置',
                                    reopen_onboarding: '重新运行向导',
                                    use_regex: '切到正则兜底',
                                    apply_recommendation: '应用推荐设置'
                                  }[action] || action}
                                </button>
                              ))}
                            </div>
                          </section>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-inline">当前没有需要优先处理的启动异常。</div>
                    )}
                  </section>

                  <section className="help-card">
                    <h4>常见操作</h4>
                    <div className="result-list">
                      <button className="result-item" onClick={() => setActiveTab('analyze')}>
                        <span>开始处理</span>
                        <strong>返回分析工作台</strong>
                      </button>
                      <button className="result-item" onClick={() => setActiveTab('settings')}>
                        <span>修改配置</span>
                        <strong>打开服务配置页</strong>
                      </button>
                      <button className="result-item" disabled={!lastKnownOutputDir} onClick={() => openPath(lastKnownOutputDir)}>
                        <span>查看结果</span>
                        <strong>{lastKnownOutputDir || '打开最近输出目录'}</strong>
                      </button>
                    </div>
                  </section>

                  <section className="help-card">
                    <h4>外部链接</h4>
                    <div className="result-list">
                      {supportLinks.map((item) => (
                        <button key={item.url} className="result-item" onClick={() => openExternal(item.url)}>
                          <span>{item.label}</span>
                          <strong>{item.url}</strong>
                        </button>
                      ))}
                    </div>
                  </section>

                  <section className="help-card full">
                    <h4>发布与下载</h4>
                    <div className="release-grid">
                      <div className="result-item static">
                        <span>普通下载</span>
                        <strong>正式版本优先从 GitHub Releases 下载 `PaperInsight-Setup-版本.exe`。</strong>
                        <div className="inline-actions">
                          <button className="ghost small" onClick={() => openExternal('https://github.com/traditionalpc01-beep/paper-analysis-toolkit/releases')}>打开 Releases</button>
                        </div>
                      </div>
                      <div className="result-item static">
                        <span>预发布验证</span>
                        <strong>推送到 `main` 后，可先在 GitHub Actions 下载最新安装产物进行验证。</strong>
                        <div className="inline-actions">
                          <button className="ghost small" onClick={() => openExternal('https://github.com/traditionalpc01-beep/paper-analysis-toolkit/actions')}>打开 Actions</button>
                        </div>
                      </div>
                      <div className="result-item static">
                        <span>发布顺序</span>
                        <strong>更新版本号，推送 main 验证，再打 v* 标签发布正式安装包。</strong>
                      </div>
                    </div>
                  </section>

                  <section className="help-card full">
                    <h4>排障建议</h4>
                    <div className="help-notes">
                      <div>
                        <strong>1. API 调用失败</strong>
                        <p>先检查设置页里的 API Key、Base URL 和网络状态；如果只是本地跑通流程，可以先切到正则模式。</p>
                      </div>
                      <div>
                        <strong>2. 打包版无法调用后端</strong>
                        <p>优先使用内置后端；如果切换到系统 Python，请确认该环境已安装 `paperinsight` 并填写正确的 Python 路径。</p>
                      </div>
                      <div>
                        <strong>3. 结果不完整</strong>
                        <p>可以启用 MinerU、联网补全影响因子，或回到设置页检查当前是否禁用了 LLM 与缓存策略。</p>
                      </div>
                    </div>
                  </section>
                </div>
              </article>
            </section>
          ) : (
            <section className="content-grid settings-grid">
              <article className="panel-card wide status-overview-card">
                <div className="panel-head split">
                  <div>
                    <span className="panel-kicker">配置地图</span>
                    <h3>入口配置和初始化状态</h3>
                  </div>
                  <div className="action-row">
                    <button className="ghost" onClick={reopenOnboarding}>重新打开向导</button>
                    <button
                      className="primary"
                      disabled={!recommendationApplicable || saveState.saving || currentMatchesRecommendation}
                      onClick={applyRecommendedSetup}
                    >
                      {currentMatchesRecommendation ? '已应用推荐' : '一键对齐推荐'}
                    </button>
                  </div>
                </div>
                <div className="settings-intro-card">
                  <strong>如果你不知道先改哪一项，就按这个顺序看：先看环境检测，再看 Longcat，再看 MinerU，最后再改输出习惯。</strong>
                  <p>下面每张卡都只负责一类配置，不需要一次把所有选项都研究完。</p>
                </div>
                <div className="setup-checklist-grid">
                  {setupChecklist.map((item) => (
                    <div key={`settings-${item.label}`} className={`setup-check-item ${item.tone}`}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.detail}</small>
                    </div>
                  ))}
                </div>
              </article>

              <article className="panel-card wide">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">Environment</span>
                    <h3>环境检测明细</h3>
                  </div>
                </div>
                <div className="environment-detail-grid">
                  {environmentDetails.map((item) => (
                    <section key={item.title} className={`environment-detail-card ${item.tone}`}>
                      <span>{item.title}</span>
                      <strong>{item.status}</strong>
                      <p>{item.detail}</p>
                    </section>
                  ))}
                </div>
              </article>

              <article className="panel-card wide">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">配置顺序</span>
                    <h3>先填这些，再看高级项</h3>
                  </div>
                </div>
                <div className="settings-lane-grid">
                  <section className="settings-lane basic">
                    <span>基础必填</span>
                    <strong>先选运行方式：离线基础版，或联网增强版</strong>
                    <p>如果只是先跑通软件，不一定要立刻填 API Key。先选论文目录并用离线基础版开始，后续再补联网能力也可以。</p>
                  </section>
                  <section className="settings-lane advanced">
                    <span>高级选项</span>
                    <strong>运行引擎、Base URL、缓存、输出习惯</strong>
                    <p>这些不是第一次必须改的。只有你知道自己为什么要改，再动它们会更稳。</p>
                  </section>
                </div>
              </article>

              <article className="panel-card">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">Basic</span>
                    <h3>基础必填：AI 服务</h3>
                  </div>
                </div>
                <div className="card-tip">
                  <strong>这一张卡最重要。</strong>
                  <p>如果没有可用的 API Key，自动模式和智能 API 模式就很容易失败。</p>
                </div>
                <div className="toggle-grid single">
                  <label><input type="checkbox" checked={Boolean(getNestedValue(config, 'llm.enabled', true))} onChange={(event) => updateConfig('llm.enabled', event.target.checked)} />启用 LLM 语义提取</label>
                </div>
                <div className="inline-actions stacked">
                  <button className="ghost small" onClick={() => window.paperInsight.openExternal('https://longcat.chat/platform/docs/zh/')}>打开 Longcat 文档</button>
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
                  <input value={getNestedValue(config, 'llm.base_url', '')} onChange={(event) => updateConfig('llm.base_url', event.target.value)} placeholder="不知道就留空，需要中转时再填" />
                </label>
              </article>

              <article className="panel-card">
                <div className="panel-head">
                  <div>
                    <span className="panel-kicker">核心能力</span>
                    <h3>MinerU 与运行引擎</h3>
                  </div>
                </div>
                <div className="card-tip">
                  <strong>先看 MinerU，再决定要不要改引擎。</strong>
                  <p>普通用户优先用内置后端 + MinerU API；只有你已经有自己的 Python 环境时，再切系统 Python。</p>
                </div>
                <div className="env-summary-card">
                  <span>推荐：{engineModeLabel(recommendedEngine)}</span>
                  <strong>{getNestedValue(env, 'recommendation.engineReason', '未返回推荐原因。')}</strong>
                  <small>基础联网：{booleanStatusLabel(networkAvailable, '可用', '受限')} · Python 兜底：{booleanStatusLabel(systemPythonReady, '可用', '待补齐')} · 推荐分析模式：{modeLabel(recommendedAnalysisMode)}</small>
                </div>
                <div className="inline-actions stacked">
                  <button
                    className="ghost small"
                    disabled={!recommendationApplicable || saveState.saving || currentMatchesRecommendation}
                    onClick={applyRecommendedSetup}
                  >
                    {currentMatchesRecommendation ? '已应用推荐' : '应用推荐启动设置'}
                  </button>
                  <button className="ghost small" onClick={useFallbackMode}>仅切到正则兜底</button>
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
                <div className="inline-actions stacked">
                  <button className="ghost small" onClick={() => window.paperInsight.openExternal('https://mineru.net/apiManage/token')}>打开 MinerU Token 申请页</button>
                </div>
                <label className="field compact">
                  <span>MinerU 模式</span>
                  <select value={getNestedValue(config, 'mineru.mode', 'api')} onChange={(event) => updateConfig('mineru.mode', event.target.value)}>
                    <option value="api">云端 API（推荐）</option>
                    <option value="cli">本地 CLI</option>
                  </select>
                </label>
                <label className="field compact">
                  <span>MinerU Token</span>
                  <input type="password" value={getNestedValue(config, 'mineru.token', '')} onChange={(event) => updateConfig('mineru.token', event.target.value)} />
                </label>
                <label className="field compact">
                  <span>模型版本</span>
                  <select value={getNestedValue(config, 'mineru.model_version', 'vlm')} onChange={(event) => updateConfig('mineru.model_version', event.target.value)}>
                    <option value="vlm">vlm - 推荐</option>
                    <option value="pipeline">pipeline</option>
                    <option value="MinerU-HTML">MinerU-HTML</option>
                  </select>
                </label>
                <label className="field compact">
                  <span>输出格式</span>
                  <select value={getNestedValue(config, 'mineru.output_format', 'markdown')} onChange={(event) => updateConfig('mineru.output_format', event.target.value)}>
                    <option value="markdown">markdown</option>
                    <option value="json">json</option>
                  </select>
                </label>
                <label className="field compact">
                  <span>解析方式</span>
                  <select value={getNestedValue(config, 'mineru.method', 'auto')} onChange={(event) => updateConfig('mineru.method', event.target.value)}>
                    <option value="auto">auto - 推荐</option>
                    <option value="txt">txt</option>
                    <option value="ocr">ocr</option>
                  </select>
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
        env={env}
        setDraftValue={updateWizardConfig}
        onBack={previousWizardStep}
        onNext={nextWizardStep}
        onFinish={() => finishOnboarding(wizardConfig)}
        onSkip={skipOnboarding}
        saving={onboarding.saving}
        error={onboarding.error}
      />

      {runConfirmVisible ? (
        <div className="wizard-overlay">
          <div className="wizard-card run-confirm-card">
            <div className="wizard-header">
              <div>
                <span className="eyebrow">启动前检查</span>
                <h2>开始前，请再确认一遍</h2>
                <p>下面这份摘要会告诉你：这次会处理哪里、怎么处理、结果会写到哪里。确认没问题再开始。</p>
              </div>
            </div>
            <div className="run-summary-grid">
              {runSummary.map(([label, value]) => (
                <section key={label} className="wizard-summary-card">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </section>
              ))}
            </div>
            {analysisGuard.warningIssues.length ? (
              <div className="alert-stack compact">
                {analysisGuard.warningIssues.map((item) => (
                  <section key={`confirm-${item.id}`} className="alert-card warning">
                    <div>
                      <strong>{item.title}</strong>
                      <p>{item.description}</p>
                    </div>
                  </section>
                ))}
              </div>
            ) : null}
            <div className="wizard-actions">
              <button className="ghost" onClick={() => setRunConfirmVisible(false)}>返回继续检查</button>
              <button className="primary" onClick={startAnalysis}>确认并开始</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
