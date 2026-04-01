const tabs = [
  { id: 'analyze', label: '分析工作台' },
  { id: 'history', label: '历史记录' },
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

export {
  tabs,
  wizardSteps,
  initialRunOptions,
  supportLinks
};