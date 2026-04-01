/**
 * 桌面应用集成测试
 * 
 * 测试内容：
 * - DropZone 组件的文件验证
 * - FilterBar 的筛选逻辑
 * - 历史记录的存储和加载
 * - 反馈数据的保存和导出
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { jest } from '@jest/globals';

const mockFs = {
  existsSync: jest.fn(),
  readFileSync: jest.fn(),
  writeFileSync: jest.fn(),
  mkdirSync: jest.fn(),
};

const mockApp = {
  getPath: jest.fn(() => path.join(os.tmpdir(), 'paperinsight-test')),
};

jest.mock('node:fs', () => mockFs);
jest.mock('electron', () => ({ app: mockApp }));

describe('HistoryManager', () => {
  let historyManager;
  let tempDir;

  beforeEach(() => {
    jest.clearAllMocks();
    tempDir = path.join(os.tmpdir(), 'paperinsight-test-' + Date.now());
    mockApp.getPath.mockReturnValue(tempDir);
    mockFs.existsSync.mockReturnValue(false);
    mockFs.readFileSync.mockReturnValue('{"records":[]}');
    mockFs.writeFileSync.mockReturnValue(undefined);
    mockFs.mkdirSync.mockReturnValue(undefined);
    
    historyManager = require('../desktop/electron/historyManager.js');
  });

  describe('loadHistory', () => {
    test('should return empty records when file does not exist', () => {
      mockFs.existsSync.mockReturnValue(false);
      
      const result = historyManager.loadHistory();
      
      expect(result).toEqual({ records: [] });
    });

    test('should load existing history records', () => {
      const mockData = {
        records: [
          { id: 'test-1', timestamp: '2024-01-01T00:00:00.000Z', fileCount: 5 }
        ]
      };
      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(JSON.stringify(mockData));
      
      const result = historyManager.loadHistory();
      
      expect(result.records).toHaveLength(1);
      expect(result.records[0].id).toBe('test-1');
    });

    test('should handle corrupted history file', () => {
      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue('invalid json');
      
      const result = historyManager.loadHistory();
      
      expect(result).toEqual({ records: [] });
    });
  });

  describe('saveHistory', () => {
    test('should save history to file', () => {
      const history = { records: [{ id: 'test-1' }] };
      
      const result = historyManager.saveHistory(history);
      
      expect(result).toBe(true);
      expect(mockFs.writeFileSync).toHaveBeenCalled();
    });

    test('should handle write errors', () => {
      mockFs.writeFileSync.mockImplementation(() => {
        throw new Error('Write error');
      });
      
      const history = { records: [] };
      const result = historyManager.saveHistory(history);
      
      expect(result).toBe(false);
    });
  });

  describe('addHistoryRecord', () => {
    test('should create and add new record', () => {
      mockFs.readFileSync.mockReturnValue('{"records":[]}');
      
      const event = {
        pdfDir: '/test/pdfs',
        outputDir: '/test/output',
        status: 'completed',
        stats: { pdfCount: 3, successCount: 3, failedCount: 0 },
        files: []
      };
      
      const record = historyManager.addHistoryRecord(event);
      
      expect(record.id).toBeDefined();
      expect(record.timestamp).toBeDefined();
      expect(record.pdfDir).toBe('/test/pdfs');
      expect(record.fileCount).toBe(3);
      expect(record.status).toBe('completed');
    });

    test('should limit records to MAX_HISTORY_RECORDS', () => {
      const existingRecords = Array(100).fill(null).map((_, i) => ({
        id: `old-${i}`,
        timestamp: new Date().toISOString()
      }));
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: existingRecords }));
      
      const event = {
        status: 'completed',
        stats: { pdfCount: 1 }
      };
      
      historyManager.addHistoryRecord(event);
      
      const writeCall = mockFs.writeFileSync.mock.calls[0];
      const savedData = JSON.parse(writeCall[1]);
      expect(savedData.records.length).toBeLessThanOrEqual(100);
    });
  });

  describe('getHistoryList', () => {
    test('should return all records without options', () => {
      const mockRecords = [
        { id: '1', status: 'completed' },
        { id: '2', status: 'failed' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const result = historyManager.getHistoryList();
      
      expect(result.length).toBe(2);
    });

    test('should filter by status', () => {
      const mockRecords = [
        { id: '1', status: 'completed' },
        { id: '2', status: 'failed' },
        { id: '3', status: 'completed' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const result = historyManager.getHistoryList({ status: 'completed' });
      
      expect(result.length).toBe(2);
      expect(result.every(r => r.status === 'completed')).toBe(true);
    });

    test('should limit results', () => {
      const mockRecords = Array(50).fill(null).map((_, i) => ({
        id: `record-${i}`,
        status: 'completed'
      }));
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const result = historyManager.getHistoryList({ limit: 10 });
      
      expect(result.length).toBe(10);
    });
  });

  describe('deleteHistoryRecord', () => {
    test('should delete existing record', () => {
      const mockRecords = [
        { id: '1', status: 'completed' },
        { id: '2', status: 'failed' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const result = historyManager.deleteHistoryRecord('1');
      
      expect(result).toBe(true);
    });

    test('should return false for non-existent record', () => {
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: [] }));
      
      const result = historyManager.deleteHistoryRecord('nonexistent');
      
      expect(result).toBe(false);
    });
  });

  describe('clearHistory', () => {
    test('should clear all records', () => {
      const result = historyManager.clearHistory();
      
      expect(result).toBe(true);
      expect(mockFs.writeFileSync).toHaveBeenCalledWith(
        expect.any(String),
        JSON.stringify({ records: [] }, null, 2),
        'utf-8'
      );
    });
  });
});

describe('FeedbackManager', () => {
  let feedbackManager;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFs.existsSync.mockReturnValue(false);
    mockFs.readFileSync.mockReturnValue('{"records":[]}');
    mockFs.writeFileSync.mockReturnValue(undefined);
    
    feedbackManager = require('../desktop/electron/feedbackManager.js');
  });

  describe('loadFeedback', () => {
    test('should return empty records when file does not exist', () => {
      mockFs.existsSync.mockReturnValue(false);
      
      const result = feedbackManager.loadFeedback();
      
      expect(result).toEqual({ records: [] });
    });

    test('should load existing feedback records', () => {
      const mockData = {
        records: [
          { id: 'fb-1', timestamp: '2024-01-01T00:00:00.000Z', file: 'test.pdf' }
        ]
      };
      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(JSON.stringify(mockData));
      
      const result = feedbackManager.loadFeedback();
      
      expect(result.records).toHaveLength(1);
    });
  });

  describe('addFeedbackRecord', () => {
    test('should create feedback record with changes', () => {
      mockFs.readFileSync.mockReturnValue('{"records":[]}');
      
      const params = {
        originalItem: {
          file: 'test.pdf',
          title: 'Original Title',
          journal: 'Journal A',
          impactFactor: 5.0
        },
        modifiedItem: {
          title: 'Modified Title',
          journal: 'Journal B',
          impactFactor: 10.0
        },
        changes: [
          { key: 'title', label: '标题', original: 'Original Title', modified: 'Modified Title' },
          { key: 'journal', label: '期刊', original: 'Journal A', modified: 'Journal B' }
        ],
        outputDir: '/test/output'
      };
      
      const record = feedbackManager.addFeedbackRecord(params);
      
      expect(record.id).toBeDefined();
      expect(record.id.startsWith('fb-')).toBe(true);
      expect(record.timestamp).toBeDefined();
      expect(record.file).toBe('test.pdf');
      expect(record.changes.length).toBe(2);
    });

    test('should limit feedback records to MAX_FEEDBACK_RECORDS', () => {
      const existingRecords = Array(500).fill(null).map((_, i) => ({
        id: `fb-${i}`,
        timestamp: new Date().toISOString()
      }));
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: existingRecords }));
      
      const params = {
        originalItem: { file: 'test.pdf' },
        modifiedItem: {},
        changes: [],
        outputDir: '/test'
      };
      
      feedbackManager.addFeedbackRecord(params);
      
      const writeCall = mockFs.writeFileSync.mock.calls[0];
      const savedData = JSON.parse(writeCall[1]);
      expect(savedData.records.length).toBeLessThanOrEqual(500);
    });
  });

  describe('getFeedbackList', () => {
    test('should filter by file', () => {
      const mockRecords = [
        { id: '1', file: 'paper1.pdf' },
        { id: '2', file: 'paper2.pdf' },
        { id: '3', file: 'paper1.pdf' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const result = feedbackManager.getFeedbackList({ file: 'paper1.pdf' });
      
      expect(result.length).toBe(2);
    });

    test('should filter by date range', () => {
      const mockRecords = [
        { id: '1', timestamp: '2024-01-01T00:00:00.000Z' },
        { id: '2', timestamp: '2024-06-15T00:00:00.000Z' },
        { id: '3', timestamp: '2024-12-01T00:00:00.000Z' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const result = feedbackManager.getFeedbackList({
        startDate: '2024-04-01',
        endDate: '2024-08-01'
      });
      
      expect(result.length).toBe(1);
      expect(result[0].id).toBe('2');
    });
  });

  describe('getFeedbackStats', () => {
    test('should calculate feedback statistics', () => {
      const mockRecords = [
        {
          id: '1',
          timestamp: new Date().toISOString(),
          file: 'paper1.pdf',
          changes: [
            { field: 'title' },
            { field: 'journal' }
          ]
        },
        {
          id: '2',
          timestamp: new Date().toISOString(),
          file: 'paper2.pdf',
          changes: [{ field: 'title' }]
        }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const stats = feedbackManager.getFeedbackStats();
      
      expect(stats.totalRecords).toBe(2);
      expect(stats.fieldCorrectionCounts.title).toBe(2);
      expect(stats.fieldCorrectionCounts.journal).toBe(1);
      expect(stats.uniqueFilesCount).toBe(2);
      expect(stats.recentCount).toBe(2);
    });
  });

  describe('exportFeedbackToJson', () => {
    test('should export all feedback records', () => {
      const mockRecords = [
        { id: '1', file: 'paper1.pdf' },
        { id: '2', file: 'paper2.pdf' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const exported = feedbackManager.exportFeedbackToJson();
      
      expect(exported.totalRecords).toBe(2);
      expect(exported.records.length).toBe(2);
      expect(exported.exportedAt).toBeDefined();
    });

    test('should export specific records by IDs', () => {
      const mockRecords = [
        { id: '1', file: 'paper1.pdf' },
        { id: '2', file: 'paper2.pdf' },
        { id: '3', file: 'paper3.pdf' }
      ];
      mockFs.readFileSync.mockReturnValue(JSON.stringify({ records: mockRecords }));
      
      const exported = feedbackManager.exportFeedbackToJson({ recordIds: ['1', '3'] });
      
      expect(exported.totalRecords).toBe(2);
      expect(exported.records.map(r => r.id)).toEqual(['1', '3']);
    });
  });

  describe('updateOriginalJsonFile', () => {
    test('should update JSON file with modified data', () => {
      const originalData = {
        title: 'Original Title',
        journal: 'Original Journal',
        impact_factor: 5.0
      };
      mockFs.existsSync.mockReturnValue(true);
      mockFs.readFileSync.mockReturnValue(JSON.stringify(originalData));
      
      const params = {
        outputDir: '/test/output',
        file: 'test.pdf',
        modifiedItem: {
          title: 'Modified Title',
          journal: 'Modified Journal',
          impactFactor: 10.0
        }
      };
      
      const result = feedbackManager.updateOriginalJsonFile(params);
      
      expect(result.success).toBe(true);
      expect(mockFs.writeFileSync).toHaveBeenCalled();
    });

    test('should return error when file not found', () => {
      mockFs.existsSync.mockReturnValue(false);
      
      const params = {
        outputDir: '/test/output',
        file: 'nonexistent.pdf',
        modifiedItem: {}
      };
      
      const result = feedbackManager.updateOriginalJsonFile(params);
      
      expect(result.success).toBe(false);
      expect(result.error).toContain('not found');
    });
  });
});

describe('DropZone Component Logic', () => {
  describe('File Validation', () => {
    const validateFiles = (files, maxFiles = 50, maxSizeMB = 100) => {
      const validFiles = [];
      const errors = [];
      const maxSize = maxSizeMB * 1024 * 1024;

      Array.from(files).forEach((file) => {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          errors.push(`"${file.name}" 不是 PDF 文件`);
          return;
        }

        if (file.size > maxSize) {
          errors.push(`"${file.name}" 超过 ${maxSizeMB}MB 限制`);
          return;
        }

        validFiles.push(file);
      });

      if (validFiles.length > maxFiles) {
        errors.push(`文件数量超过 ${maxFiles} 个限制，已选取前 ${maxFiles} 个`);
        return {
          validFiles: validFiles.slice(0, maxFiles),
          errors
        };
      }

      return { validFiles, errors };
    };

    test('should accept valid PDF files', () => {
      const files = [
        { name: 'paper1.pdf', size: 1024 * 1024 },
        { name: 'paper2.pdf', size: 2 * 1024 * 1024 }
      ];
      
      const result = validateFiles(files);
      
      expect(result.validFiles.length).toBe(2);
      expect(result.errors.length).toBe(0);
    });

    test('should reject non-PDF files', () => {
      const files = [
        { name: 'paper.pdf', size: 1024 },
        { name: 'document.docx', size: 1024 },
        { name: 'image.png', size: 1024 }
      ];
      
      const result = validateFiles(files);
      
      expect(result.validFiles.length).toBe(1);
      expect(result.errors.length).toBe(2);
    });

    test('should reject files exceeding size limit', () => {
      const files = [
        { name: 'small.pdf', size: 1024 },
        { name: 'large.pdf', size: 150 * 1024 * 1024 }
      ];
      
      const result = validateFiles(files, 50, 100);
      
      expect(result.validFiles.length).toBe(1);
      expect(result.errors.length).toBe(1);
      expect(result.errors[0]).toContain('超过');
    });

    test('should limit number of files', () => {
      const files = Array(60).fill(null).map((_, i) => ({
        name: `paper${i}.pdf`,
        size: 1024
      }));
      
      const result = validateFiles(files, 50, 100);
      
      expect(result.validFiles.length).toBe(50);
      expect(result.errors.length).toBe(1);
      expect(result.errors[0]).toContain('文件数量超过');
    });

    test('should accept PDF files with uppercase extension', () => {
      const files = [
        { name: 'paper.PDF', size: 1024 },
        { name: 'document.Pdf', size: 1024 }
      ];
      
      const result = validateFiles(files);
      
      expect(result.validFiles.length).toBe(2);
      expect(result.errors.length).toBe(0);
    });
  });
});

describe('FilterBar Logic', () => {
  const FILTER_FIELDS = [
    { key: 'title', label: '标题', type: 'text' },
    { key: 'journal', label: '期刊', type: 'text' },
    { key: 'year', label: '年份', type: 'text' },
    { key: 'impactFactor', label: '影响因子', type: 'text' },
    { key: 'bestEqe', label: 'EQE/PCE', type: 'text' }
  ];

  const parseYearFilter = (value) => {
    if (!value) return null;
    const trimmed = value.trim();
    
    if (trimmed.startsWith('>')) {
      return { op: 'gt', value: parseInt(trimmed.slice(1)) };
    }
    if (trimmed.startsWith('<')) {
      return { op: 'lt', value: parseInt(trimmed.slice(1)) };
    }
    if (trimmed.includes('-')) {
      const [min, max] = trimmed.split('-').map(v => parseInt(v.trim()));
      return { op: 'range', min, max };
    }
    return { op: 'eq', value: parseInt(trimmed) };
  };

  const parseNumericFilter = (value) => {
    if (!value) return null;
    const trimmed = value.trim();
    
    if (trimmed.startsWith('>')) {
      return { op: 'gt', value: parseFloat(trimmed.slice(1)) };
    }
    if (trimmed.startsWith('<')) {
      return { op: 'lt', value: parseFloat(trimmed.slice(1)) };
    }
    if (trimmed.includes('-')) {
      const [min, max] = trimmed.split('-').map(v => parseFloat(v.trim()));
      return { op: 'range', min, max };
    }
    return { op: 'eq', value: parseFloat(trimmed) };
  };

  const matchesFilter = (item, filters) => {
    for (const [key, value] of Object.entries(filters)) {
      if (!value || value.trim() === '') continue;
      
      const itemValue = item[key];
      
      if (key === 'year') {
        const parsed = parseYearFilter(value);
        if (!parsed) continue;
        
        if (parsed.op === 'gt' && itemValue <= parsed.value) return false;
        if (parsed.op === 'lt' && itemValue >= parsed.value) return false;
        if (parsed.op === 'range' && (itemValue < parsed.min || itemValue > parsed.max)) return false;
        if (parsed.op === 'eq' && itemValue !== parsed.value) return false;
      } else if (key === 'impactFactor' || key === 'bestEqe') {
        const parsed = parseNumericFilter(value);
        if (!parsed) continue;
        
        if (parsed.op === 'gt' && itemValue <= parsed.value) return false;
        if (parsed.op === 'lt' && itemValue >= parsed.value) return false;
        if (parsed.op === 'range' && (itemValue < parsed.min || itemValue > parsed.max)) return false;
        if (parsed.op === 'eq' && itemValue !== parsed.value) return false;
      } else {
        if (!String(itemValue).toLowerCase().includes(value.toLowerCase())) {
          return false;
        }
      }
    }
    return true;
  };

  describe('Year Filter Parsing', () => {
    test('should parse greater than filter', () => {
      expect(parseYearFilter('>2020')).toEqual({ op: 'gt', value: 2020 });
    });

    test('should parse less than filter', () => {
      expect(parseYearFilter('<2025')).toEqual({ op: 'lt', value: 2025 });
    });

    test('should parse range filter', () => {
      expect(parseYearFilter('2020-2024')).toEqual({ op: 'range', min: 2020, max: 2024 });
    });

    test('should parse exact value filter', () => {
      expect(parseYearFilter('2023')).toEqual({ op: 'eq', value: 2023 });
    });

    test('should return null for empty value', () => {
      expect(parseYearFilter('')).toBeNull();
      expect(parseYearFilter(null)).toBeNull();
    });
  });

  describe('Numeric Filter Parsing', () => {
    test('should parse greater than filter', () => {
      expect(parseNumericFilter('>10')).toEqual({ op: 'gt', value: 10 });
    });

    test('should parse range filter with decimals', () => {
      expect(parseNumericFilter('5.5-10.5')).toEqual({ op: 'range', min: 5.5, max: 10.5 });
    });
  });

  describe('Filter Matching', () => {
    const testItems = [
      { title: 'OLED efficiency study', journal: 'Nature', year: 2024, impactFactor: 15.0, bestEqe: 22.5 },
      { title: 'Perovskite solar cells', journal: 'Science', year: 2023, impactFactor: 20.0, bestEqe: 25.0 },
      { title: 'Battery materials', journal: 'Nature Energy', year: 2022, impactFactor: 50.0, bestEqe: null },
      { title: 'OLED device optimization', journal: 'Advanced Materials', year: 2024, impactFactor: 30.0, bestEqe: 18.5 }
    ];

    test('should filter by title keyword', () => {
      const filters = { title: 'OLED' };
      const results = testItems.filter(item => matchesFilter(item, filters));
      
      expect(results.length).toBe(2);
      expect(results.every(r => r.title.includes('OLED'))).toBe(true);
    });

    test('should filter by year range', () => {
      const filters = { year: '2023-2024' };
      const results = testItems.filter(item => matchesFilter(item, filters));
      
      expect(results.length).toBe(3);
    });

    test('should filter by impact factor greater than', () => {
      const filters = { impactFactor: '>20' };
      const results = testItems.filter(item => matchesFilter(item, filters));
      
      expect(results.length).toBe(2);
      expect(results.every(r => r.impactFactor > 20)).toBe(true);
    });

    test('should combine multiple filters', () => {
      const filters = { title: 'OLED', year: '2024' };
      const results = testItems.filter(item => matchesFilter(item, filters));
      
      expect(results.length).toBe(2);
      expect(results.every(r => r.title.includes('OLED') && r.year === 2024)).toBe(true);
    });

    test('should handle null values in items', () => {
      const filters = { bestEqe: '>20' };
      const results = testItems.filter(item => matchesFilter(item, filters));
      
      expect(results.length).toBe(2);
      expect(results.every(r => r.bestEqe !== null && r.bestEqe > 20)).toBe(true);
    });

    test('should be case insensitive for text filters', () => {
      const filters = { journal: 'nature' };
      const results = testItems.filter(item => matchesFilter(item, filters));
      
      expect(results.length).toBe(2);
      expect(results.every(r => r.journal.toLowerCase().includes('nature'))).toBe(true);
    });
  });

  describe('Active Filter Detection', () => {
    const hasActiveFilters = (filters) => {
      return Object.values(filters).some(value => value && value.trim() !== '');
    };

    const getActiveFilterCount = (filters) => {
      return Object.values(filters).filter(value => value && value.trim() !== '').length;
    };

    test('should detect active filters', () => {
      expect(hasActiveFilters({ title: '', journal: '' })).toBe(false);
      expect(hasActiveFilters({ title: 'OLED', journal: '' })).toBe(true);
      expect(hasActiveFilters({ title: 'OLED', journal: 'Nature' })).toBe(true);
    });

    test('should count active filters', () => {
      expect(getActiveFilterCount({ title: '', journal: '' })).toBe(0);
      expect(getActiveFilterCount({ title: 'OLED', journal: '' })).toBe(1);
      expect(getActiveFilterCount({ title: 'OLED', journal: 'Nature' })).toBe(2);
    });
  });
});
