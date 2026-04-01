const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('paperInsight', {
  getConfig: () => ipcRenderer.invoke('config:get'),
  saveConfig: (config) => ipcRenderer.invoke('config:save', { config }),
  chooseDirectory: (options) => ipcRenderer.invoke('dialog:choose-directory', options),
  startAnalysis: (payload) => ipcRenderer.invoke('analysis:start', payload),
  cancelAnalysis: () => ipcRenderer.invoke('analysis:cancel'),
  openPath: (targetPath) => ipcRenderer.invoke('shell:open-path', targetPath),
  openExternal: (targetUrl) => ipcRenderer.invoke('shell:open-external', targetUrl),
  showItem: (targetPath) => ipcRenderer.invoke('shell:show-item', targetPath),
  onAnalysisEvent: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on('analysis:event', handler);
    return () => ipcRenderer.removeListener('analysis:event', handler);
  },
  getHistoryList: (options) => ipcRenderer.invoke('history:list', options),
  getHistoryRecord: (recordId) => ipcRenderer.invoke('history:get', recordId),
  deleteHistoryRecord: (recordId) => ipcRenderer.invoke('history:delete', recordId),
  clearHistory: () => ipcRenderer.invoke('history:clear'),
  saveFeedback: (params) => ipcRenderer.invoke('feedback:save', params),
  getFeedbackList: (options) => ipcRenderer.invoke('feedback:list', options),
  getFeedbackRecord: (recordId) => ipcRenderer.invoke('feedback:get', recordId),
  deleteFeedbackRecord: (recordId) => ipcRenderer.invoke('feedback:delete', recordId),
  clearFeedback: () => ipcRenderer.invoke('feedback:clear'),
  exportFeedback: (options) => ipcRenderer.invoke('feedback:export', options),
  getFeedbackStats: () => ipcRenderer.invoke('feedback:stats')
});
