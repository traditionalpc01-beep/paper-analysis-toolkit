import fs from 'node:fs';
import path from 'node:path';
import { app } from 'electron';

const HISTORY_FILE_NAME = 'analysis_history.json';
const MAX_HISTORY_RECORDS = 100;

function getHistoryFilePath() {
  const userDataPath = app.getPath('userData');
  return path.join(userDataPath, HISTORY_FILE_NAME);
}

function loadHistory() {
  const historyPath = getHistoryFilePath();
  
  if (!fs.existsSync(historyPath)) {
    return { records: [] };
  }
  
  try {
    const content = fs.readFileSync(historyPath, 'utf-8');
    const data = JSON.parse(content);
    return { records: Array.isArray(data.records) ? data.records : [] };
  } catch (error) {
    console.error('Failed to load history:', error.message);
    return { records: [] };
  }
}

function saveHistory(history) {
  const historyPath = getHistoryFilePath();
  
  try {
    const content = JSON.stringify(history, null, 2);
    fs.writeFileSync(historyPath, content, 'utf-8');
    return true;
  } catch (error) {
    console.error('Failed to save history:', error.message);
    return false;
  }
}

function generateRecordId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function createHistoryRecord(event) {
  const stats = event.stats || {};
  const files = event.files || [];
  
  return {
    id: generateRecordId(),
    timestamp: new Date().toISOString(),
    pdfDir: event.pdfDir || '',
    outputDir: event.outputDir || '',
    fileCount: stats.pdfCount || 0,
    successCount: stats.successCount || 0,
    failedCount: stats.failedCount || 0,
    status: event.status || 'completed',
    mode: event.mode || 'auto',
    files: files.map(f => ({
      name: f.name || f.file || '',
      status: f.status || 'unknown',
      journal: f.journal || ''
    })),
    stats: {
      total: stats.pdfCount || 0,
      success: stats.successCount || 0,
      failed: stats.failedCount || 0
    }
  };
}

function addHistoryRecord(event) {
  const history = loadHistory();
  const record = createHistoryRecord(event);
  
  history.records.unshift(record);
  
  if (history.records.length > MAX_HISTORY_RECORDS) {
    history.records = history.records.slice(0, MAX_HISTORY_RECORDS);
  }
  
  saveHistory(history);
  return record;
}

function getHistoryList(options = {}) {
  const history = loadHistory();
  let records = history.records;
  
  if (options.limit) {
    records = records.slice(0, options.limit);
  }
  
  if (options.status) {
    records = records.filter(r => r.status === options.status);
  }
  
  return records;
}

function getHistoryRecord(recordId) {
  const history = loadHistory();
  return history.records.find(r => r.id === recordId) || null;
}

function deleteHistoryRecord(recordId) {
  const history = loadHistory();
  const index = history.records.findIndex(r => r.id === recordId);
  
  if (index === -1) {
    return false;
  }
  
  history.records.splice(index, 1);
  saveHistory(history);
  return true;
}

function clearHistory() {
  const history = { records: [] };
  saveHistory(history);
  return true;
}

export {
  loadHistory,
  saveHistory,
  addHistoryRecord,
  getHistoryList,
  getHistoryRecord,
  deleteHistoryRecord,
  clearHistory,
  getHistoryFilePath
};
