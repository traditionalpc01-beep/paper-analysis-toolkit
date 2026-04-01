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

export {
  cloneConfig,
  getNestedValue,
  setNestedValue,
  defaultOutputDir,
  formatProviderLabel,
  modeLabel,
  engineModeLabel,
  readinessLabel,
  booleanStatusLabel,
  canApplyRecommendedEngine,
  buildRecommendedConfig,
  hasLlmCredentials,
  buildRecommendedOnboardingConfig,
  buildBasicOnboardingConfig,
  buildEnvironmentAlerts,
  hasConfiguredCredentials,
  validateWizardStep,
  buildLogLine,
  formatImpactFactor,
  matchesQuery,
  displayValue,
  maskedStatus,
  buildGettingStartedSteps,
  buildSetupChecklist,
  buildEnvironmentDetails,
  buildAnalysisGuard,
  buildRunSummary,
  classifyErrorItem,
  buildFailureFixSuggestions
};