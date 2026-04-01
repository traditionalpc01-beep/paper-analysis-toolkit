import React, { useState, useCallback, useMemo } from 'react';

const EXPORT_FORMATS = [
  { id: 'excel', label: 'Excel (.xlsx)', description: '适合数据分析和查看，支持富文本格式' },
  { id: 'json', label: 'JSON (.json)', description: '适合程序读取和数据处理' },
  { id: 'csv', label: 'CSV (.csv)', description: '通用表格格式，兼容性最好' }
];

const REPORT_COLUMNS = [
  { key: 'file', label: '文件名' },
  { key: 'url', label: '文件地址' },
  { key: 'journal', label: '期刊名称' },
  { key: 'impact_factor', label: '影响因子' },
  { key: 'authors', label: '作者' },
  { key: 'processing_status', label: '处理结果' },
  { key: 'title', label: '论文标题' },
  { key: 'structure', label: '器件结构' },
  { key: 'eqe', label: 'EQE' },
  { key: 'cie', label: 'CIE' },
  { key: 'lifetime', label: '寿命' },
  { key: 'best_eqe', label: '最高EQE' },
  { key: 'optimization_level', label: '优化层级' },
  { key: 'optimization_strategy', label: '优化策略' },
  { key: 'optimization_details', label: '优化详情' },
  { key: 'key_findings', label: '关键发现' },
  { key: 'eqe_source', label: 'EQE原文' },
  { key: 'cie_source', label: 'CIE原文' },
  { key: 'lifetime_source', label: '寿命原文' },
  { key: 'structure_source', label: '结构原文' }
];

const FIELD_MAPPING = {
  file: ['File', 'file', '文件', '文件名'],
  url: ['URL', 'url', '文件地址'],
  journal: ['journal_name', '期刊', '期刊名称'],
  impact_factor: ['影响因子', 'impact_factor'],
  authors: ['authors', '作者'],
  processing_status: ['processing_status', '处理结果/简述', '处理结果', '简述'],
  title: ['title', '标题', '论文标题'],
  structure: ['器件结构', 'device_structure', '结构'],
  eqe: ['EQE', 'eqe', '外量子效率'],
  cie: ['CIE', 'cie', '色度坐标'],
  lifetime: ['寿命', 'lifetime'],
  best_eqe: ['最高EQE', 'best_eqe'],
  optimization_level: ['优化层级', 'optimization_level'],
  optimization_strategy: ['优化策略', 'optimization_strategy'],
  optimization_details: ['优化详情'],
  key_findings: ['关键发现'],
  eqe_source: ['EQE原文', 'eqe_source'],
  cie_source: ['CIE原文', 'cie_source'],
  lifetime_source: ['寿命原文', 'lifetime_source'],
  structure_source: ['结构原文', 'structure_source']
};

function getFieldValue(item, fieldKey) {
  const keys = FIELD_MAPPING[fieldKey] || [fieldKey];
  for (const key of keys) {
    if (item[key] !== undefined && item[key] !== null && item[key] !== '') {
      return item[key];
    }
  }
  return '';
}

function escapeCSVField(value) {
  if (value === null || value === undefined) {
    return '';
  }
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

function generateCSVContent(items, columns) {
  const header = columns.map(col => escapeCSVField(col.label)).join(',');
  const rows = items.map(item => {
    return columns.map(col => escapeCSVField(getFieldValue(item, col.key))).join(',');
  });
  return [header, ...rows].join('\n');
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function ExportModal({ visible, items, outputDir, onClose }) {
  const [selectedFormat, setSelectedFormat] = useState('excel');
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const itemCount = useMemo(() => items?.length || 0, [items]);

  const handleFormatChange = useCallback((format) => {
    setSelectedFormat(format);
    setMessage({ type: '', text: '' });
  }, []);

  const handleExport = useCallback(async () => {
    if (!items || items.length === 0) {
      setMessage({ type: 'error', text: '没有可导出的数据' });
      return;
    }

    setExporting(true);
    setMessage({ type: '', text: '' });

    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const baseFilename = `paperinsight_report_${timestamp}`;

      if (selectedFormat === 'csv') {
        const csvContent = '\uFEFF' + generateCSVContent(items, REPORT_COLUMNS);
        downloadFile(csvContent, `${baseFilename}.csv`, 'text/csv;charset=utf-8');
        setMessage({ type: 'success', text: `已导出 ${items.length} 条记录到 CSV 文件` });
      } else if (selectedFormat === 'json') {
        const jsonContent = JSON.stringify(items, null, 2);
        downloadFile(jsonContent, `${baseFilename}.json`, 'application/json;charset=utf-8');
        setMessage({ type: 'success', text: `已导出 ${items.length} 条记录到 JSON 文件` });
      } else if (selectedFormat === 'excel') {
        if (window.paperInsight?.exportToExcel) {
          const result = await window.paperInsight.exportToExcel({
            items,
            outputDir,
            filename: `${baseFilename}.xlsx`
          });
          if (result.success) {
            setMessage({ type: 'success', text: `已导出 ${items.length} 条记录到 Excel 文件` });
          } else {
            throw new Error(result.error || '导出失败');
          }
        } else {
          setMessage({ type: 'error', text: 'Excel 导出需要后端支持，请使用 CSV 或 JSON 格式' });
        }
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message || '导出失败，请重试' });
    } finally {
      setExporting(false);
    }
  }, [items, selectedFormat, outputDir]);

  const handleOpenOutputDir = useCallback(() => {
    if (outputDir && window.paperInsight?.openPath) {
      window.paperInsight.openPath(outputDir);
    }
  }, [outputDir]);

  if (!visible) {
    return null;
  }

  return (
    <div className="wizard-overlay" onClick={onClose}>
      <div className="wizard-card export-modal" onClick={(e) => e.stopPropagation()}>
        <div className="wizard-header">
          <div>
            <span className="eyebrow">数据导出</span>
            <h2>选择导出格式</h2>
            <p>共 {itemCount} 条记录可供导出，请选择您需要的格式。</p>
          </div>
        </div>

        <div className="export-format-options">
          {EXPORT_FORMATS.map((format) => (
            <div
              key={format.id}
              className={`export-format-card ${selectedFormat === format.id ? 'selected' : ''}`}
              onClick={() => handleFormatChange(format.id)}
            >
              <div className="format-radio">
                <input
                  type="radio"
                  name="exportFormat"
                  value={format.id}
                  checked={selectedFormat === format.id}
                  onChange={() => handleFormatChange(format.id)}
                />
              </div>
              <div className="format-info">
                <strong>{format.label}</strong>
                <p>{format.description}</p>
              </div>
            </div>
          ))}
        </div>

        {selectedFormat === 'csv' && (
          <div className="export-tip">
            <strong>CSV 格式说明</strong>
            <p>CSV 文件已添加 UTF-8 BOM 标记，可正确显示中文。建议使用 Excel 或其他表格软件打开。</p>
          </div>
        )}

        {message.text && (
          <div className={`export-message ${message.type}`}>
            {message.text}
          </div>
        )}

        <div className="wizard-actions">
          <div className="action-row">
            {outputDir && (
              <button className="ghost" onClick={handleOpenOutputDir}>
                打开输出目录
              </button>
            )}
          </div>
          <div className="action-row">
            <button className="ghost" onClick={onClose} disabled={exporting}>
              取消
            </button>
            <button
              className="primary"
              onClick={handleExport}
              disabled={exporting || itemCount === 0}
            >
              {exporting ? '导出中...' : '开始导出'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExportModal;
