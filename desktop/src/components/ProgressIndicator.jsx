import React from 'react';

const STAGE_CONFIG = {
  parsing: {
    label: '解析 PDF',
    icon: '📄',
    color: '#3b82f6',
    description: '正在解析 PDF 文档结构'
  },
  cleaning: {
    label: '文本清洗',
    icon: '🧹',
    color: '#8b5cf6',
    description: '正在清洗和过滤文本'
  },
  extracting: {
    label: '数据提取',
    icon: '🔍',
    color: '#f59e0b',
    description: '正在提取结构化数据'
  },
  fetching_if: {
    label: '获取影响因子',
    icon: '📊',
    color: '#10b981',
    description: '正在查询期刊影响因子'
  },
  validating: {
    label: '数据验证',
    icon: '✅',
    color: '#06b6d4',
    description: '正在验证数据完整性'
  }
};

function ProgressIndicator({
  currentStage,
  stageMessage,
  currentFile,
  completedCount,
  totalCount,
  progressPercent
}) {
  const stageInfo = STAGE_CONFIG[currentStage] || {
    label: currentStage,
    icon: '⚙️',
    color: '#6b7280',
    description: stageMessage || '处理中...'
  };

  const stages = Object.keys(STAGE_CONFIG);
  const currentStageIndex = stages.indexOf(currentStage);

  return (
    <div className="progress-indicator">
      <div className="progress-header">
        <div className="current-file">
          <span className="file-icon">📑</span>
          <span className="file-name" title={currentFile}>
            {currentFile}
          </span>
        </div>
        <div className="progress-stats">
          <span className="count">{completedCount} / {totalCount}</span>
          <span className="percent">{progressPercent}%</span>
        </div>
      </div>

      <div className="stage-info">
        <div className="stage-icon" style={{ backgroundColor: stageInfo.color }}>
          {stageInfo.icon}
        </div>
        <div className="stage-details">
          <div className="stage-label">{stageInfo.label}</div>
          <div className="stage-message">{stageMessage || stageInfo.description}</div>
        </div>
      </div>

      <div className="stage-steps">
        {stages.map((stage, index) => {
          const config = STAGE_CONFIG[stage];
          const isActive = index === currentStageIndex;
          const isCompleted = index < currentStageIndex;

          return (
            <div
              key={stage}
              className={`stage-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
            >
              <div
                className="step-dot"
                style={{
                  backgroundColor: isCompleted || isActive ? config.color : '#e5e7eb',
                  borderColor: config.color
                }}
              >
                {isCompleted && <span className="check">✓</span>}
                {isActive && <span className="pulse" />}
              </div>
              <span className="step-label">{config.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default React.memo(ProgressIndicator);
