import React, { useCallback, useMemo } from 'react';

const FILTER_FIELDS = [
  { key: 'title', label: '标题', placeholder: '输入标题关键词...' },
  { key: 'journal', label: '期刊', placeholder: '输入期刊名称...' },
  { key: 'year', label: '年份', placeholder: '如: 2024' },
  { key: 'impactFactor', label: '影响因子', placeholder: '如: >10 或 5-10' },
  { key: 'bestEqe', label: 'EQE/PCE', placeholder: '如: >20 或 15-25' }
];

function FilterBar({ filters, onFilterChange, totalCount, filteredCount }) {
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

  return (
    <div className="filter-bar">
      <div className="filter-header">
        <h3>条件筛选</h3>
        <div className="filter-stats">
          <span className="filter-count">
            显示 {filteredCount} / {totalCount} 条结果
          </span>
          {hasActiveFilters && (
            <button className="ghost small clear-filters" onClick={handleClearAll}>
              清除全部 ({activeFilterCount})
            </button>
          )}
        </div>
      </div>
      
      <div className="filter-fields">
        {FILTER_FIELDS.map(field => (
          <div key={field.key} className="filter-field">
            <label>{field.label}</label>
            <input
              type="text"
              value={filters[field.key] || ''}
              onChange={(e) => handleFilterUpdate(field.key, e.target.value)}
              placeholder={field.placeholder}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export default React.memo(FilterBar);
