import React, { useMemo, useCallback, useState } from 'react';
import { formatImpactFactor, classifyErrorItem, buildFailureFixSuggestions, matchesQuery } from '../utils';
import ExportModal from './ExportModal';
import FilterBar from './FilterBar';
import ResultsPreview from './ResultsPreview';
import FeedbackModal from './FeedbackModal';

// 优化：创建可重用的子组件并使用React.memo
const ReportCard = React.memo(({ label, path }) => (
  <div className="report-card">
    <span>{label}</span>
    <button
      className="ghost small"
      onClick={() => window.paperInsight.openPath(path)}
    >
      打开
    </button>
  </div>
));

const SuccessItemCard = React.memo(({ item }) => (
  <div className="item-card success">
    <h3>{item.title || '未提取标题'}</h3>
    <div className="item-meta">
      <span>文件: {item.file}</span>
      <span>期刊: {item.journal || '未提取'}</span>
      <span>影响因子: {formatImpactFactor(item.impactFactor)}</span>
      <span>最佳 EQE: {item.bestEqe || '未提取'}</span>
    </div>
  </div>
));

const ErrorItem = React.memo(({ item }) => (
  <div className="error-item">
    <span>{item.file}</span>
    <p>{item.message}</p>
  </div>
));

const ErrorGroup = React.memo(({ suggestion, groupedErrorItems }) => {
  const errorItems = groupedErrorItems.find(([name]) => name === suggestion.groupName)?.[1] || [];
  
  return (
    <div className="error-group">
      <h3>{suggestion.groupName} ({suggestion.count})</h3>
      <div className="suggestion-card">
        <h4>{suggestion.title}</h4>
        <p>{suggestion.description}</p>
        <ul>
          {suggestion.actions.map((action, idx) => (
            <li key={idx}>{action}</li>
          ))}
        </ul>
      </div>
      <div className="error-files">
        {errorItems.map((item, idx) => (
          <ErrorItem key={idx} item={item} />
        ))}
      </div>
    </div>
  );
});

const LogItem = React.memo(({ log, isError }) => (
  <div key={log.id} className={`log-item ${isError ? 'error' : ''}`}>
    {log.text}
  </div>
));

function ResultsTab({ job, resultQuery, setResultQuery, resultScope, setResultScope }) {
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [feedbackModalVisible, setFeedbackModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [filters, setFilters] = useState({
    title: '',
    journal: '',
    year: '',
    impactFactor: '',
    bestEqe: ''
  });
  const [viewMode, setViewMode] = useState('table');

  const handleSearchChange = useCallback((e) => {
    setResultQuery(e.target.value);
  }, [setResultQuery]);

  const handleScopeChange = useCallback((scope) => {
    setResultScope(scope);
  }, [setResultScope]);

  const handleOpenExportModal = useCallback(() => {
    setExportModalVisible(true);
  }, []);

  const handleCloseExportModal = useCallback(() => {
    setExportModalVisible(false);
  }, []);

  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  const handleViewModeChange = useCallback((mode) => {
    setViewMode(mode);
  }, []);

  const handleEditClick = useCallback((item) => {
    setEditingItem(item);
    setFeedbackModalVisible(true);
  }, []);

  const handleFeedbackSave = useCallback(async (params) => {
    try {
      await window.paperInsight.saveFeedback(params);
      return true;
    } catch (error) {
      throw new Error(error.message || '保存反馈失败');
    }
  }, []);

  const handleFeedbackClose = useCallback(() => {
    setFeedbackModalVisible(false);
    setEditingItem(null);
  }, []);

  const parseNumericFilter = useCallback((filterValue) => {
    if (!filterValue || filterValue.trim() === '') {
      return null;
    }
    const trimmed = filterValue.trim();
    
    if (trimmed.startsWith('>')) {
      const value = parseFloat(trimmed.slice(1));
      if (!isNaN(value)) return { op: 'gt', value };
    } else if (trimmed.startsWith('<')) {
      const value = parseFloat(trimmed.slice(1));
      if (!isNaN(value)) return { op: 'lt', value };
    } else if (trimmed.startsWith('>=')) {
      const value = parseFloat(trimmed.slice(2));
      if (!isNaN(value)) return { op: 'gte', value };
    } else if (trimmed.startsWith('<=')) {
      const value = parseFloat(trimmed.slice(2));
      if (!isNaN(value)) return { op: 'lte', value };
    } else if (trimmed.includes('-')) {
      const parts = trimmed.split('-');
      if (parts.length === 2) {
        const min = parseFloat(parts[0]);
        const max = parseFloat(parts[1]);
        if (!isNaN(min) && !isNaN(max)) return { op: 'range', min, max };
      }
    } else {
      const value = parseFloat(trimmed);
      if (!isNaN(value)) return { op: 'eq', value };
    }
    return null;
  }, []);

  const matchesNumericFilter = useCallback((itemValue, filter) => {
    if (!filter) return true;
    
    const numValue = parseFloat(String(itemValue || '').replace(/[^\d.-]/g, ''));
    if (isNaN(numValue)) return false;

    switch (filter.op) {
      case 'gt': return numValue > filter.value;
      case 'lt': return numValue < filter.value;
      case 'gte': return numValue >= filter.value;
      case 'lte': return numValue <= filter.value;
      case 'range': return numValue >= filter.min && numValue <= filter.max;
      case 'eq': return numValue === filter.value;
      default: return true;
    }
  }, []);

  const matchesAdvancedFilters = useCallback((item) => {
    if (filters.title && filters.title.trim() !== '') {
      const titleFilter = filters.title.toLowerCase();
      if (!String(item.title || '').toLowerCase().includes(titleFilter)) {
        return false;
      }
    }

    if (filters.journal && filters.journal.trim() !== '') {
      const journalFilter = filters.journal.toLowerCase();
      if (!String(item.journal || '').toLowerCase().includes(journalFilter)) {
        return false;
      }
    }

    if (filters.year && filters.year.trim() !== '') {
      const yearFilter = parseNumericFilter(filters.year);
      if (yearFilter && !matchesNumericFilter(item.year, yearFilter)) {
        return false;
      }
    }

    if (filters.impactFactor && filters.impactFactor.trim() !== '') {
      const ifFilter = parseNumericFilter(filters.impactFactor);
      if (ifFilter && !matchesNumericFilter(item.impactFactor, ifFilter)) {
        return false;
      }
    }

    if (filters.bestEqe && filters.bestEqe.trim() !== '') {
      const eqeFilter = parseNumericFilter(filters.bestEqe);
      if (eqeFilter && !matchesNumericFilter(item.bestEqe, eqeFilter)) {
        return false;
      }
    }

    return true;
  }, [filters, parseNumericFilter, matchesNumericFilter]);

  const filteredResults = useMemo(() => {
    const stats = job.stats || {};
    const reports = Object.entries(stats.reportFiles || {}).filter(([label, targetPath]) =>
      matchesQuery([label, targetPath], resultQuery)
    );
    
    let successItems = (stats.successItems || []).filter((item) =>
      matchesQuery([item.file, item.title, item.journal, item.impactFactor, item.bestEqe], resultQuery)
    );

    successItems = successItems.filter(matchesAdvancedFilters);

    const errorItems = (stats.errorItems || []).filter((item) =>
      matchesQuery([item.file, item.message, item.context, item.type], resultQuery)
    );

    return { reports, successItems, errorItems };
  }, [job.stats, resultQuery, matchesAdvancedFilters]);

  const exportItems = useMemo(() => {
    const stats = job.stats || {};
    return stats.successItems || [];
  }, [job.stats]);

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

  // 优化：计算进度百分比，避免在渲染中直接计算
  const progressPercent = useMemo(() => {
    if (!job.total) return 0;
    return Math.min(100, Math.round((job.completed / job.total) * 100));
  }, [job.completed, job.total]);

  return (
    <div className="tab-content results">
      <section className="hero">
        <div>
          <h1>分析结果</h1>
          <p>查看分析完成的论文列表、失败文件和生成的报告。</p>
        </div>
      </section>

      {job.status === 'completed' && (
        <>
          <section className="results-header">
            <div className="search-box">
              <input
                type="text"
                value={resultQuery}
                onChange={handleSearchChange}
                placeholder="搜索论文标题、期刊、文件..."
              />
            </div>
            <div className="filter-tabs">
              <button
                className={resultScope === 'all' ? 'active' : ''}
                onClick={() => handleScopeChange('all')}
              >
                全部
              </button>
              <button
                className={resultScope === 'success' ? 'active' : ''}
                onClick={() => handleScopeChange('success')}
              >
                成功
              </button>
              <button
                className={resultScope === 'error' ? 'active' : ''}
                onClick={() => handleScopeChange('error')}
              >
                失败
              </button>
            </div>
          </section>

          <section className="reports-section">
            <div className="section-header">
              <h2>生成的报告</h2>
              <button className="ghost small" onClick={handleOpenExportModal}>
                导出数据
              </button>
            </div>
            <div className="reports-grid">
              {filteredResults.reports.map(([label, path]) => (
                <ReportCard key={label} label={label} path={path} />
              ))}
            </div>
          </section>

          {(resultScope === 'all' || resultScope === 'success') && filteredResults.successItems.length > 0 && (
            <section className="success-items">
              <div className="section-header">
                <h2>成功分析的论文</h2>
                <div className="view-mode-switch">
                  <button
                    className={`view-mode-btn ${viewMode === 'table' ? 'active' : ''}`}
                    onClick={() => handleViewModeChange('table')}
                  >
                    表格视图
                  </button>
                  <button
                    className={`view-mode-btn ${viewMode === 'card' ? 'active' : ''}`}
                    onClick={() => handleViewModeChange('card')}
                  >
                    卡片视图
                  </button>
                </div>
              </div>

              <FilterBar
                filters={filters}
                onFilterChange={handleFilterChange}
                totalCount={(job.stats?.successItems || []).length}
                filteredCount={filteredResults.successItems.length}
              />

              {viewMode === 'table' ? (
                <ResultsPreview
                  items={filteredResults.successItems}
                  onRowClick={(item) => {
                    console.log('Selected item:', item);
                  }}
                  onEditClick={handleEditClick}
                />
              ) : (
                <div className="items-grid">
                  {filteredResults.successItems.map((item, index) => (
                    <SuccessItemCard key={index} item={item} />
                  ))}
                </div>
              )}
            </section>
          )}

          {(resultScope === 'all' || resultScope === 'error') && filteredResults.errorItems.length > 0 && (
            <section className="error-items">
              <h2>分析失败的论文</h2>
              {failureFixSuggestions.map((suggestion, index) => (
                <ErrorGroup 
                  key={index} 
                  suggestion={suggestion} 
                  groupedErrorItems={groupedErrorItems} 
                />
              ))}
            </section>
          )}

          {filteredResults.successItems.length === 0 && filteredResults.errorItems.length === 0 && (
            <section className="no-results">
              <h2>暂无结果</h2>
              <p>请先运行分析任务。</p>
            </section>
          )}
        </>
      )}

      {job.status === 'running' && (
        <section className="running-status">
          <h2>分析中</h2>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
          <p>当前处理: {job.currentFile}</p>
          <p>进度: {job.completed} / {job.total}</p>
          <div className="logs">
            <h3>日志</h3>
            <div className="log-list">
              {job.logs.slice(0, 50).map((log) => (
                <LogItem key={log.id} log={log} isError={false} />
              ))}
            </div>
          </div>
        </section>
      )}

      {job.status === 'failed' && (
        <section className="failed-status">
          <h2>分析失败</h2>
          <div className="logs">
            <h3>错误日志</h3>
            <div className="log-list">
              {job.logs.slice(0, 50).map((log) => (
                <LogItem key={log.id} log={log} isError={true} />
              ))}
            </div>
          </div>
        </section>
      )}

      {job.status === 'idle' && (
        <section className="idle-status">
          <h2>准备就绪</h2>
          <p>请在分析工作台选择论文目录并开始分析。</p>
        </section>
      )}

      <ExportModal
        visible={exportModalVisible}
        items={exportItems}
        outputDir={job.outputDir}
        onClose={handleCloseExportModal}
      />

      <FeedbackModal
        visible={feedbackModalVisible}
        item={editingItem}
        outputDir={job.outputDir}
        onSave={handleFeedbackSave}
        onClose={handleFeedbackClose}
      />
    </div>
  );
}

// 优化：使用React.memo包装主组件
export default React.memo(ResultsTab);