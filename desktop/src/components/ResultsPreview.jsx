import React, { useState, useMemo, useCallback } from 'react';
import { formatImpactFactor } from '../utils';

const TABLE_COLUMNS = [
  { key: 'title', label: '标题', type: 'text', width: '300px' },
  { key: 'journal', label: '期刊', type: 'text', width: '150px' },
  { key: 'year', label: '年份', type: 'number', width: '80px' },
  { key: 'impactFactor', label: '影响因子', type: 'number', width: '100px' },
  { key: 'bestEqe', label: '最佳 EQE/PCE', type: 'number', width: '120px' },
  { key: 'file', label: '文件名', type: 'text', width: '200px' }
];

function parseNumericValue(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const num = parseFloat(String(value).replace(/[^\d.-]/g, ''));
  return isNaN(num) ? null : num;
}

function sortData(data, sortConfig) {
  if (!sortConfig.key) {
    return data;
  }

  const { key, direction } = sortConfig;
  const column = TABLE_COLUMNS.find(col => col.key === key);
  const isNumeric = column?.type === 'number';

  return [...data].sort((a, b) => {
    let valueA = a[key];
    let valueB = b[key];

    if (isNumeric) {
      valueA = parseNumericValue(valueA);
      valueB = parseNumericValue(valueB);

      if (valueA === null && valueB === null) return 0;
      if (valueA === null) return direction === 'asc' ? 1 : -1;
      if (valueB === null) return direction === 'asc' ? -1 : 1;

      return direction === 'asc' ? valueA - valueB : valueB - valueA;
    }

    valueA = String(valueA || '').toLowerCase();
    valueB = String(valueB || '').toLowerCase();

    if (valueA < valueB) return direction === 'asc' ? -1 : 1;
    if (valueA > valueB) return direction === 'asc' ? 1 : -1;
    return 0;
  });
}

const SortIcon = React.memo(({ direction, active }) => (
  <span className={`sort-icon ${active ? 'active' : ''}`}>
    {direction === 'asc' ? '↑' : direction === 'desc' ? '↓' : '↕'}
  </span>
));

const TableCell = React.memo(({ value, type, width }) => {
  if (type === 'number') {
    const displayValue = value !== null && value !== undefined && value !== '' 
      ? value 
      : '-';
    return (
      <td style={{ minWidth: width }} className="cell-numeric">
        {displayValue}
      </td>
    );
  }
  
  return (
    <td style={{ minWidth: width }} title={value || ''}>
      <div className="cell-text">
        {value || '-'}
      </div>
    </td>
  );
});

const TableRow = React.memo(({ item, columns, onClick, isSelected }) => (
  <tr 
    className={`result-row ${isSelected ? 'selected' : ''}`}
    onClick={() => onClick(item)}
  >
    {columns.map(column => (
      <TableCell
        key={column.key}
        value={column.key === 'impactFactor' && item[column.key] !== null && item[column.key] !== undefined
          ? formatImpactFactor(item[column.key])
          : item[column.key]}
        type={column.type}
        width={column.width}
      />
    ))}
  </tr>
));

function ResultsPreview({ items, onRowClick, onEditClick }) {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [selectedItem, setSelectedItem] = useState(null);

  const sortedItems = useMemo(() => {
    return sortData(items, sortConfig);
  }, [items, sortConfig]);

  const handleSort = useCallback((key) => {
    setSortConfig(prev => {
      if (prev.key === key) {
        return {
          key,
          direction: prev.direction === 'asc' ? 'desc' : 'asc'
        };
      }
      return { key, direction: 'asc' };
    });
  }, []);

  const handleRowClick = useCallback((item) => {
    setSelectedItem(item);
    if (onRowClick) {
      onRowClick(item);
    }
  }, [onRowClick]);

  if (!items || items.length === 0) {
    return (
      <div className="results-preview-empty">
        <p>暂无数据</p>
      </div>
    );
  }

  return (
    <div className="results-preview">
      <div className="table-container">
        <table className="results-table">
          <thead>
            <tr>
              {TABLE_COLUMNS.map(column => (
                <th
                  key={column.key}
                  className={`sortable ${sortConfig.key === column.key ? 'sorted' : ''}`}
                  onClick={() => handleSort(column.key)}
                  style={{ minWidth: column.width }}
                >
                  <div className="th-content">
                    <span>{column.label}</span>
                    <SortIcon
                      direction={sortConfig.key === column.key ? sortConfig.direction : null}
                      active={sortConfig.key === column.key}
                    />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedItems.map((item, index) => (
              <TableRow
                key={index}
                item={item}
                columns={TABLE_COLUMNS}
                onClick={handleRowClick}
                isSelected={selectedItem === item}
              />
            ))}
          </tbody>
        </table>
      </div>
      
      {selectedItem && (
        <div className="result-detail-panel">
          <div className="detail-header">
            <h3>详细信息</h3>
            <div className="detail-actions">
              {onEditClick && (
                <button className="ghost small" onClick={() => onEditClick(selectedItem)}>
                  修正
                </button>
              )}
              <button className="ghost small" onClick={() => setSelectedItem(null)}>
                关闭
              </button>
            </div>
          </div>
          <div className="detail-content">
            {TABLE_COLUMNS.map(column => (
              <div key={column.key} className="detail-item">
                <span className="detail-label">{column.label}:</span>
                <span className="detail-value">
                  {column.key === 'impactFactor' && selectedItem[column.key] !== null && selectedItem[column.key] !== undefined
                    ? formatImpactFactor(selectedItem[column.key])
                    : selectedItem[column.key] || '-'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default React.memo(ResultsPreview);
