import React from 'react';

function BatchProgressBar({
  completed,
  total,
  progressPercent,
  currentFile,
  status,
  onCancel
}) {
  const isRunning = status === 'running';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';

  const getBarColor = () => {
    if (isFailed) return '#ef4444';
    if (isCompleted) return '#10b981';
    return '#3b82f6';
  };

  const getStatusText = () => {
    if (isRunning) return '处理中';
    if (isCompleted) return '已完成';
    if (isFailed) return '失败';
    return '就绪';
  };

  return (
    <div className="batch-progress-bar">
      <div className="progress-meta">
        <div className="meta-left">
          <span className={`status-badge ${status}`}>
            {getStatusText()}
          </span>
          <span className="file-count">
            {completed} / {total} 文件
          </span>
        </div>
        <div className="meta-right">
          <span className="percent-text">{progressPercent}%</span>
        </div>
      </div>

      <div className="progress-track">
        <div
          className="progress-fill"
          style={{
            width: `${progressPercent}%`,
            backgroundColor: getBarColor()
          }}
        >
          {progressPercent > 10 && (
            <span className="fill-text">{progressPercent}%</span>
          )}
        </div>
      </div>

      {isRunning && currentFile && (
        <div className="current-file-info">
          <span className="label">当前文件:</span>
          <span className="filename" title={currentFile}>
            {currentFile}
          </span>
        </div>
      )}

      {isRunning && onCancel && (
        <button className="cancel-btn" onClick={onCancel}>
          取消处理
        </button>
      )}

      {isCompleted && (
        <div className="completion-info">
          <span className="success-icon">✓</span>
          <span className="message">
            成功处理 {completed} 个文件
          </span>
        </div>
      )}

      {isFailed && (
        <div className="error-info">
          <span className="error-icon">✗</span>
          <span className="message">处理过程中出现错误</span>
        </div>
      )}
    </div>
  );
}

export default React.memo(BatchProgressBar);
