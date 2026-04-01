import React from 'react';
import { buildEnvironmentDetails, buildSetupChecklist } from '../utils';
import { supportLinks } from '../constants';

function HelpTab({ config, env, onboardingCompleted, runOptions }) {
  const environmentDetails = buildEnvironmentDetails(env, config);
  const setupChecklist = buildSetupChecklist(config, env, onboardingCompleted, runOptions);

  return (
    <div className="tab-content help">
      <section className="hero">
        <div>
          <h1>把安装、配置和排障说明收进同一个桌面入口</h1>
          <p>帮助页集中展示版本、路径、常用入口和外部资源，方便普通用户直接查看环境信息、定位结果目录并完成基础排障。</p>
        </div>
      </section>

      <section className="environment-details">
        <h2>环境信息</h2>
        <div className="details-grid">
          {environmentDetails.map((item, index) => (
            <div key={index} className={`detail-card ${item.tone}`}>
              <h3>{item.title}</h3>
              <div className="detail-status">{item.status}</div>
              <p>{item.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="setup-checklist">
        <h2>配置检查</h2>
        <div className="checklist">
          {setupChecklist.map((item, index) => (
            <div key={index} className="checklist-item">
              <div>
                <span className="checklist-label">{item.label}</span>
                <span className={`checklist-value ${item.tone}`}>{item.value}</span>
              </div>
              <p className="checklist-detail">{item.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="support-links">
        <h2>常用链接</h2>
        <div className="links-grid">
          {supportLinks.map((link, index) => (
            <div key={index} onClick={() => window.paperInsight.openExternal(link.url)} className="link-card">
              <span>{link.label}</span>
              <span className="link-arrow">→</span>
            </div>
          ))}
        </div>
      </section>

      <section className="help-content">
        <h2>使用说明</h2>
        <div className="help-sections">
          <div className="help-section">
            <h3>首次使用</h3>
            <ul>
              <li>打开软件后会自动弹出首次启动向导</li>
              <li>按照向导步骤配置 Longcat API Key 和 MinerU Token</li>
              <li>选择论文目录和输出目录</li>
              <li>点击“开始分析”按钮</li>
            </ul>
          </div>
          <div className="help-section">
            <h3>排障指南</h3>
            <ul>
              <li>如果网络受限，建议使用“正则兜底”模式</li>
              <li>如果 API Key 无效，检查是否正确粘贴</li>
              <li>如果 MinerU 失败，尝试切换解析方式</li>
              <li>如果输出目录无权限，尝试更换目录</li>
            </ul>
          </div>
          <div className="help-section">
            <h3>常见问题</h3>
            <ul>
              <li>Q: 为什么分析速度很慢？A: 智能 API 模式需要联网调用，速度取决于网络状况</li>
              <li>Q: 为什么有些 PDF 分析失败？A: 可能是 PDF 加密、损坏或扫描质量差</li>
              <li>Q: 如何查看分析结果？A: 结果会保存在输出目录，包含 Excel 和 JSON 文件</li>
              <li>Q: 如何更新软件？A: 访问 GitHub Releases 页面下载最新版本</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

export default HelpTab;