import React, { useState, useEffect, useCallback } from 'react';

function formatTimestamp(isoString) {
  if (!isoString) return '未知时间';
  
  try {
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}`;
  } catch {
    return '未知时间';
  }
}

function statusLabel(status) {
  const mapping = {
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
    partial: '部分完成'
  };
  return mapping[status] || status;
}

function statusClass(status) {
  const mapping = {
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning',
    partial: 'warning'
  };
  return mapping[status] || '';
}

function HistoryPanel({ onLoadHistory, onDeleteHistory, onClearHistory }) {
  const [historyList, setHistoryList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError('');
    
    try {
      const records = await window.paperInsight.getHistoryList({ limit: 50 });
      setHistoryList(records || []);
    } catch (err) {
      setError(err.message || '加载历史记录失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSelectRecord = (record) => {
    setSelectedRecord(selectedRecord?.id === record.id ? null : record);
  };

  const handleLoadRecord = async (record) => {
    if (onLoadHistory) {
      onLoadHistory(record);
    }
  };

  const handleDeleteRecord = async (recordId) => {
    try {
      await window.paperInsight.deleteHistoryRecord(recordId);
      setHistoryList(prev => prev.filter(r => r.id !== recordId));
      if (selectedRecord?.id === recordId) {
        setSelectedRecord(null);
      }
      setConfirmDelete(null);
      
      if (onDeleteHistory) {
        onDeleteHistory(recordId);
      }
    } catch (err) {
      setError(err.message || '删除失败');
    }
  };

  const handleClearHistory = async () => {
    try {
      await window.paperInsight.clearHistory();
      setHistoryList([]);
      setSelectedRecord(null);
      setConfirmClear(false);
      
      if (onClearHistory) {
        onClearHistory();
      }
    } catch (err) {
      setError(err.message || '清空失败');
    }
  };

  const handleOpenOutputDir = (outputDir) => {
    if (outputDir) {
      window.paperInsight.showItem(outputDir);
    }
  };

  if (loading) {
    return (
      <div className="history-panel">
        <div className="history-header">
          <h3>历史记录</h3>
        </div>
        <div className="history-loading">加载中...</div>
      </div>
    );
  }

  return (
    <div className="history-panel">
      <div className="history-header">
        <h3>历史记录</h3>
        {historyList.length > 0 && (
          <button 
            className="ghost small"
            onClick={() => setConfirmClear(true)}
          >
            清空全部
          </button>
        )}
      </div>

      {error && (
        <div className="history-error">{error}</div>
      )}

      {historyList.length === 0 ? (
        <div className="history-empty">
          <p>暂无历史记录</p>
          <small>完成分析后，记录将自动保存在这里</small>
        </div>
      ) : (
        <div className="history-list">
          {historyList.map((record) => (
            <div 
              key={record.id}
              className={`history-item ${selectedRecord?.id === record.id ? 'selected' : ''} ${statusClass(record.status)}`}
              onClick={() => handleSelectRecord(record)}
            >
              <div className="history-item-header">
                <span className="history-time">{formatTimestamp(record.timestamp)}</span>
                <span className={`history-status ${statusClass(record.status)}`}>
                  {statusLabel(record.status)}
                </span>
              </div>
              
              <div className="history-item-body">
                <div className="history-stat">
                  <span>文件数:</span>
                  <strong>{record.fileCount || 0}</strong>
                </div>
                <div className="history-stat">
                  <span>成功:</span>
                  <strong className="success-text">{record.successCount || 0}</strong>
                </div>
                <div className="history-stat">
                  <span>失败:</span>
                  <strong className={record.failedCount > 0 ? 'error-text' : ''}>
                    {record.failedCount || 0}
                  </strong>
                </div>
              </div>

              {selectedRecord?.id === record.id && (
                <div className="history-item-detail">
                  <div className="history-detail-row">
                    <span>论文目录:</span>
                    <code>{record.pdfDir || '未设置'}</code>
                  </div>
                  <div className="history-detail-row">
                    <span>输出目录:</span>
                    <code>{record.outputDir || '未设置'}</code>
                  </div>
                  <div className="history-detail-row">
                    <span>分析模式:</span>
                    <span>{record.mode || 'auto'}</span>
                  </div>
                  
                  <div className="history-actions">
                    <button 
                      className="ghost small"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleLoadRecord(record);
                      }}
                    >
                      加载结果
                    </button>
                    {record.outputDir && (
                      <button 
                        className="ghost small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenOutputDir(record.outputDir);
                        }}
                      >
                        打开目录
                      </button>
                    )}
                    <button 
                      className="danger small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDelete(record.id);
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {confirmDelete && (
        <div className="history-confirm-overlay">
          <div className="history-confirm-dialog">
            <p>确定要删除这条历史记录吗？</p>
            <div className="history-confirm-actions">
              <button className="ghost" onClick={() => setConfirmDelete(null)}>
                取消
              </button>
              <button className="danger" onClick={() => handleDeleteRecord(confirmDelete)}>
                删除
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmClear && (
        <div className="history-confirm-overlay">
          <div className="history-confirm-dialog">
            <p>确定要清空所有历史记录吗？此操作不可恢复。</p>
            <div className="history-confirm-actions">
              <button className="ghost" onClick={() => setConfirmClear(false)}>
                取消
              </button>
              <button className="danger" onClick={handleClearHistory}>
                清空
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HistoryPanel;
