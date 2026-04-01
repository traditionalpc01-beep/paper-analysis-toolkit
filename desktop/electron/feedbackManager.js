import fs from 'node:fs';
import path from 'node:path';
import { app } from 'electron';

const FEEDBACK_FILE_NAME = 'feedback_records.json';
const MAX_FEEDBACK_RECORDS = 500;

function getFeedbackFilePath() {
  const userDataPath = app.getPath('userData');
  return path.join(userDataPath, FEEDBACK_FILE_NAME);
}

function loadFeedback() {
  const feedbackPath = getFeedbackFilePath();
  
  if (!fs.existsSync(feedbackPath)) {
    return { records: [] };
  }
  
  try {
    const content = fs.readFileSync(feedbackPath, 'utf-8');
    const data = JSON.parse(content);
    return { records: Array.isArray(data.records) ? data.records : [] };
  } catch (error) {
    console.error('Failed to load feedback:', error.message);
    return { records: [] };
  }
}

function saveFeedback(feedback) {
  const feedbackPath = getFeedbackFilePath();
  
  try {
    const content = JSON.stringify(feedback, null, 2);
    fs.writeFileSync(feedbackPath, content, 'utf-8');
    return true;
  } catch (error) {
    console.error('Failed to save feedback:', error.message);
    return false;
  }
}

function generateFeedbackId() {
  return `fb-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function createFeedbackRecord(params) {
  const { originalItem, modifiedItem, changes, outputDir } = params;
  
  return {
    id: generateFeedbackId(),
    timestamp: new Date().toISOString(),
    file: originalItem?.file || '',
    outputDir: outputDir || '',
    originalData: {
      title: originalItem?.title || '',
      journal: originalItem?.journal || '',
      year: originalItem?.year || null,
      impactFactor: originalItem?.impactFactor || null,
      bestEqe: originalItem?.bestEqe || ''
    },
    modifiedData: {
      title: modifiedItem?.title || '',
      journal: modifiedItem?.journal || '',
      year: modifiedItem?.year || null,
      impactFactor: modifiedItem?.impactFactor || null,
      bestEqe: modifiedItem?.bestEqe || ''
    },
    changes: changes.map(c => ({
      field: c.key,
      label: c.label,
      original: c.original,
      modified: c.modified
    })),
    metadata: {
      fileSource: originalItem?.file || '',
      correctionCount: changes.length
    }
  };
}

function addFeedbackRecord(params) {
  const feedback = loadFeedback();
  const record = createFeedbackRecord(params);
  
  feedback.records.unshift(record);
  
  if (feedback.records.length > MAX_FEEDBACK_RECORDS) {
    feedback.records = feedback.records.slice(0, MAX_FEEDBACK_RECORDS);
  }
  
  saveFeedback(feedback);
  return record;
}

function getFeedbackList(options = {}) {
  const feedback = loadFeedback();
  let records = feedback.records;
  
  if (options.limit) {
    records = records.slice(0, options.limit);
  }
  
  if (options.file) {
    records = records.filter(r => r.file === options.file);
  }
  
  if (options.startDate) {
    const startDate = new Date(options.startDate);
    records = records.filter(r => new Date(r.timestamp) >= startDate);
  }
  
  if (options.endDate) {
    const endDate = new Date(options.endDate);
    records = records.filter(r => new Date(r.timestamp) <= endDate);
  }
  
  return records;
}

function getFeedbackRecord(recordId) {
  const feedback = loadFeedback();
  return feedback.records.find(r => r.id === recordId) || null;
}

function deleteFeedbackRecord(recordId) {
  const feedback = loadFeedback();
  const index = feedback.records.findIndex(r => r.id === recordId);
  
  if (index === -1) {
    return false;
  }
  
  feedback.records.splice(index, 1);
  saveFeedback(feedback);
  return true;
}

function clearFeedback() {
  const feedback = { records: [] };
  saveFeedback(feedback);
  return true;
}

function updateOriginalJsonFile(params) {
  const { outputDir, file, modifiedItem } = params;
  
  if (!outputDir || !file) {
    return { success: false, error: 'Missing outputDir or file' };
  }
  
  const jsonFileName = file.replace(/\.pdf$/i, '.json');
  const jsonFilePath = path.join(outputDir, jsonFileName);
  
  if (!fs.existsSync(jsonFilePath)) {
    return { success: false, error: `JSON file not found: ${jsonFilePath}` };
  }
  
  try {
    const content = fs.readFileSync(jsonFilePath, 'utf-8');
    const data = JSON.parse(content);
    
    data.title = modifiedItem.title || data.title;
    data.journal = modifiedItem.journal || data.journal;
    data.year = modifiedItem.year !== undefined ? modifiedItem.year : data.year;
    data.impact_factor = modifiedItem.impactFactor !== undefined ? modifiedItem.impactFactor : data.impact_factor;
    data.best_eqe = modifiedItem.bestEqe || data.best_eqe;
    data.corrected_at = new Date().toISOString();
    data.correction_source = 'user_feedback';
    
    fs.writeFileSync(jsonFilePath, JSON.stringify(data, null, 2), 'utf-8');
    
    return { success: true, path: jsonFilePath };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

function exportFeedbackToJson(options = {}) {
  const feedback = loadFeedback();
  const records = options.recordIds
    ? feedback.records.filter(r => options.recordIds.includes(r.id))
    : feedback.records;
  
  const exportData = {
    exportedAt: new Date().toISOString(),
    totalRecords: records.length,
    records: records
  };
  
  return exportData;
}

function getFeedbackStats() {
  const feedback = loadFeedback();
  const records = feedback.records;
  
  const stats = {
    totalRecords: records.length,
    fieldCorrectionCounts: {},
    recentCount: 0,
    filesCorrected: new Set()
  };
  
  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
  
  for (const record of records) {
    for (const change of record.changes) {
      stats.fieldCorrectionCounts[change.field] = (stats.fieldCorrectionCounts[change.field] || 0) + 1;
    }
    
    if (new Date(record.timestamp) >= oneWeekAgo) {
      stats.recentCount++;
    }
    
    if (record.file) {
      stats.filesCorrected.add(record.file);
    }
  }
  
  stats.uniqueFilesCount = stats.filesCorrected.size;
  delete stats.filesCorrected;
  
  return stats;
}

export {
  loadFeedback,
  saveFeedback,
  addFeedbackRecord,
  getFeedbackList,
  getFeedbackRecord,
  deleteFeedbackRecord,
  clearFeedback,
  updateOriginalJsonFile,
  exportFeedbackToJson,
  getFeedbackStats,
  getFeedbackFilePath
};
