import React, { useState, useCallback, useMemo } from 'react';
import { formatImpactFactor } from '../utils';

const EDITABLE_FIELDS = [
  { key: 'title', label: '标题', type: 'text' },
  { key: 'journal', label: '期刊', type: 'text' },
  { key: 'year', label: '年份', type: 'number' },
  { key: 'impactFactor', label: '影响因子', type: 'number' },
  { key: 'bestEqe', label: '最佳 EQE/PCE', type: 'text' }
];

function FeedbackModal({ visible, item, outputDir, onSave, onClose }) {
  const [editedItem, setEditedItem] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useMemo(() => {
    if (item) {
      setEditedItem({ ...item });
      setError('');
    }
  }, [item]);

  const handleFieldChange = useCallback((key, value) => {
    setEditedItem(prev => ({
      ...prev,
      [key]: value
    }));
  }, []);

  const getChangedFields = useCallback(() => {
    if (!item || !editedItem) return [];
    
    return EDITABLE_FIELDS.filter(field => {
      const original = item[field.key];
      const modified = editedItem[field.key];
      return String(original || '') !== String(modified || '');
    }).map(field => ({
      key: field.key,
      label: field.label,
      original: item[field.key],
      modified: editedItem[field.key]
    }));
  }, [item, editedItem]);

  const handleSave = useCallback(async () => {
    if (!editedItem) return;

    const changes = getChangedFields();
    if (changes.length === 0) {
      setError('没有检测到任何修改');
      return;
    }

    setSaving(true);
    setError('');

    try {
      await onSave({
        originalItem: item,
        modifiedItem: editedItem,
        changes,
        outputDir,
        timestamp: new Date().toISOString()
      });
      onClose();
    } catch (err) {
      setError(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  }, [editedItem, item, getChangedFields, outputDir, onSave, onClose]);

  const handleCancel = useCallback(() => {
    setEditedItem(item ? { ...item } : null);
    setError('');
    onClose();
  }, [item, onClose]);

  if (!visible || !item || !editedItem) {
    return null;
  }

  const changes = getChangedFields();

  return (
    <div className="feedback-overlay" onClick={handleCancel}>
      <div className="feedback-modal" onClick={e => e.stopPropagation()}>
        <div className="feedback-header">
          <h2>修正提取结果</h2>
          <button className="ghost small" onClick={handleCancel}>
            关闭
          </button>
        </div>

        <div className="feedback-content">
          <div className="feedback-section">
            <h3>文件信息</h3>
            <div className="feedback-file-info">
              <span className="file-label">文件名:</span>
              <span className="file-name">{item.file || '未知'}</span>
            </div>
          </div>

          <div className="feedback-section">
            <h3>编辑字段</h3>
            <div className="feedback-fields">
              {EDITABLE_FIELDS.map(field => (
                <div key={field.key} className="feedback-field">
                  <label>{field.label}</label>
                  <div className="field-input-wrapper">
                    <input
                      type={field.type}
                      value={editedItem[field.key] || ''}
                      onChange={e => handleFieldChange(field.key, e.target.value)}
                      placeholder={`输入${field.label}`}
                    />
                    {item[field.key] !== editedItem[field.key] && (
                      <span className="field-changed-indicator">*</span>
                    )}
                  </div>
                  <div className="field-original">
                    <span className="original-label">原始值:</span>
                    <span className="original-value">
                      {field.key === 'impactFactor' && item[field.key] !== null && item[field.key] !== undefined
                        ? formatImpactFactor(item[field.key])
                        : item[field.key] || '(空)'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {changes.length > 0 && (
            <div className="feedback-section">
              <h3>修改摘要</h3>
              <div className="feedback-changes">
                {changes.map(change => (
                  <div key={change.key} className="change-item">
                    <span className="change-label">{change.label}:</span>
                    <span className="change-original">
                      {change.key === 'impactFactor' && change.original !== null && change.original !== undefined
                        ? formatImpactFactor(change.original)
                        : change.original || '(空)'}
                    </span>
                    <span className="change-arrow">→</span>
                    <span className="change-modified">
                      {change.key === 'impactFactor' && change.modified !== null && change.modified !== undefined
                        ? formatImpactFactor(change.modified)
                        : change.modified || '(空)'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="feedback-error">
              {error}
            </div>
          )}
        </div>

        <div className="feedback-actions">
          <button className="ghost" onClick={handleCancel} disabled={saving}>
            取消
          </button>
          <button 
            className="primary" 
            onClick={handleSave} 
            disabled={saving || changes.length === 0}
          >
            {saving ? '保存中...' : `保存修改 (${changes.length})`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default React.memo(FeedbackModal);
