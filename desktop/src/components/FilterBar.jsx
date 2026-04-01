import React, { useCallback, useMemo, useState } from 'react';

const FILTER_FIELDS = [
  { key: 'title', label: '标题', placeholder: '输入标题关键词...', type: 'text' },
  { key: 'journal', label: '期刊', placeholder: '输入期刊名称...', type: 'text' },
  { key: 'year', label: '年份', placeholder: '如: 2024 或 >2020', type: 'text' },
  { key: 'impactFactor', label: '影响因子', placeholder: '如: >10 或 5-10', type: 'text' },
  { key: 'bestEqe', label: 'EQE/PCE', placeholder: '如: >20 或 15-25', type: 'text' }
];

function FilterBar({ filters, onFilterChange, totalCount, filteredCount }) {
  const [isExpanded, setIsExpanded] = useState(true);

  const handleFilterUpdate = useCallback((field, value) => {
    onFilterChange({
      ...filters,
      [field]: value
    });
  }, [filters, onFilterChange]);

  const handleClearAll = useCallback(() => {
    const clearedFilters = {};
    FILTER_FIELDS.forEach(field => {
      clearedFilters[field.key] = '';
    });
    onFilterChange(clearedFilters);
  }, [onFilterChange]);

  const hasActiveFilters = useMemo(() => {
    return Object.values(filters).some(value => value && value.trim() !== '');
  }, [filters]);

  const activeFilterCount = useMemo(() => {
    return Object.values(filters).filter(value => value && value.trim() !== '').length;
  }, [filters]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded(prev => !prev);
  }, []);

  return (
    <div className={`filter-bar ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="filter-header">
        <div className="filter-title" onClick={toggleExpanded}>
          <span className="filter-toggle-icon">{isExpanded ? '▼' : '▶'}</span>
          <h3>条件筛选</h3>
          {hasActiveFilters && (
            <span className="active-filter-badge">{activeFilterCount}</span>
          )}
        </div>
        <div className="filter-stats">
          <span className="filter-count">
            显示 {filteredCount} / {totalCount} 条结果
          </span>
          {hasActiveFilters && (
            <button className="ghost small clear-filters" onClick={handleClearAll}>
              清除全部
            </button>
          )}
        </div>
      </div>
      
      {isExpanded && (
        <div className="filter-fields">
          {FILTER_FIELDS.map(field => (
            <div key={field.key} className="filter-field">
              <label>{field.label}</label>
              <input
                type="text"
                value={filters[field.key] || ''}
                onChange={(e) => handleFilterUpdate(field.key, e.target.value)}
                placeholder={field.placeholder}
                className={filters[field.key] && filters[field.key].trim() !== '' ? 'has-value' : ''}
              />
            </div>
          ))}
        </div>
      )}

      {isExpanded && hasActiveFilters && (
        <div className="filter-summary">
          <span className="filter-summary-label">当前筛选条件：</span>
          <div className="filter-tags">
            {FILTER_FIELDS.map(field => {
              const value = filters[field.key];
              if (!value || value.trim() === '') return null;
              return (
                <span key={field.key} className="filter-tag">
                  <span className="filter-tag-label">{field.label}:</span>
                  <span className="filter-tag-value">{value}</span>
                  <button 
                    className="filter-tag-remove"
                    onClick={() => handleFilterUpdate(field.key, '')}
                  >
                    ×
                  </button>
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default React.memo(FilterBar);
