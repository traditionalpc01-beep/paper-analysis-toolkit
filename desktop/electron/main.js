const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const isDev = !app.isPackaged;
let mainWindow = null;
let activeAnalysisProcess = null;

function appIconPath() {
  return path.resolve(__dirname, '..', 'assets', 'icon.png');
}

function bundledBackendPath() {
  if (isDev) {
    return path.resolve(__dirname, '..', '..', 'dist', 'PaperInsightBackend.exe');
  }
  return path.join(process.resourcesPath, 'backend', 'PaperInsightBackend.exe');
}

function defaultPythonCommand() {
  if (process.platform === 'win32') {
    return 'python';
  }
  return 'python3';
}

function resolveBackendLaunchOptions(engine = {}) {
  const preferredMode = engine.mode || 'bundled';
  const packagedBackend = bundledBackendPath();
  const bundledExists = fs.existsSync(packagedBackend);
  const overrideBackend = engine.backend_path || engine.backendPath;

  if (overrideBackend && fs.existsSync(overrideBackend)) {
    return {
      command: overrideBackend,
      args: [],
      resolvedMode: 'bundled',
      description: overrideBackend
    };
  }

  if (preferredMode === 'bundled' && bundledExists) {
    return {
      command: packagedBackend,
      args: [],
      resolvedMode: 'bundled',
      description: packagedBackend
    };
  }

  const pythonPath = engine.python_path || engine.pythonPath || process.env.PAPERINSIGHT_PYTHON || defaultPythonCommand();
  return {
    command: pythonPath,
    args: ['-m', 'paperinsight.desktop_bridge'],
    resolvedMode: 'system_python',
    description: pythonPath,
    bundledAvailable: bundledExists
  };
}

function spawnBackend(command, payload, engine = {}) {
  const launch = resolveBackendLaunchOptions(engine);
  const child = spawn(launch.command, [...launch.args, command], {
    cwd: path.resolve(__dirname, '..', '..'),
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8'
    },
    stdio: ['pipe', 'pipe', 'pipe']
  });

  if (payload) {
    child.stdin.write(JSON.stringify(payload));
  }
  child.stdin.end();

  return { child, launch };
}

function collectBackendResponse(command, payload, engine = {}) {
  return new Promise((resolve, reject) => {
    const { child, launch } = spawnBackend(command, payload, engine);
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });

    child.on('error', (error) => {
      reject(new Error(`无法启动后端：${error.message}`));
    });

    child.on('close', (code) => {
      const line = stdout
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean)
        .pop();

      if (code !== 0 && !line) {
        reject(new Error(stderr.trim() || `后端执行失败，退出码 ${code}`));
        return;
      }

      try {
        const data = line ? JSON.parse(line) : {};
        resolve({ ...data, _launch: launch, _stderr: stderr.trim() });
      } catch (error) {
        reject(new Error(`解析后端响应失败：${error.message}`));
      }
    });
  });
}

async function collectEnvironmentInfo(config) {
  try {
    const response = await collectBackendResponse('env-info', {
      config,
      runtime: {
        bundledAvailable: fs.existsSync(bundledBackendPath()),
        bundledPath: bundledBackendPath(),
        isPackaged: app.isPackaged,
        platform: process.platform
      }
    });
    return response.env;
  } catch (error) {
    return {
      pythonExecutable: '',
      pythonVersion: '',
      platform: process.platform,
      version: '',
      engineMode: config?.desktop?.engine?.mode || 'bundled',
      checks: {
        bundledBackend: {
          available: fs.existsSync(bundledBackendPath()),
          current: false,
          path: bundledBackendPath(),
          message: '环境检测未完整返回，请检查后端。'
        },
        network: {
          available: false,
          target: '',
          latencyMs: null,
          message: error.message || '环境检测失败'
        },
        systemPython: {
          available: false,
          command: config?.desktop?.engine?.python_path || '',
          executable: '',
          version: '',
          hasPaperInsight: false,
          message: error.message || '环境检测失败'
        }
      },
      recommendation: {
        engineMode: 'bundled',
        engineLabel: '内置后端',
        engineReason: '环境检测失败时优先保留内置后端。',
        analysisMode: 'regex',
        analysisLabel: '正则兜底',
        analysisReason: '环境检测失败时建议先使用正则兜底。',
        fallbackTool: {
          id: 'regex',
          label: '正则兜底',
          reason: '待环境检测恢复后再切换智能模式。'
        }
      },
      readiness: {
        status: 'limited',
        summary: '环境检测失败，建议先用内置后端和正则模式。'
      },
      diagnosticsError: error.message || '环境检测失败'
    };
  }
}

function emitAnalysisEvent(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('analysis:event', payload);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: '#f3efe4',
    title: 'PaperInsight',
    icon: appIconPath(),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

ipcMain.handle('dialog:choose-directory', async (_event, options = {}) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: options.title || '选择文件夹',
    defaultPath: options.defaultPath || undefined,
    properties: ['openDirectory', 'createDirectory']
  });

  if (result.canceled || !result.filePaths.length) {
    return null;
  }

  return result.filePaths[0];
});

ipcMain.handle('config:get', async () => {
  const response = await collectBackendResponse('config-get');
  const envInfo = await collectEnvironmentInfo(response.config);
  return {
    config: response.config,
    meta: response.meta,
    env: envInfo,
    launch: response._launch
  };
});

ipcMain.handle('config:save', async (_event, payload) => {
  const response = await collectBackendResponse('config-save', payload);
  const envInfo = await collectEnvironmentInfo(response.config);
  return {
    config: response.config,
    meta: response.meta,
    env: envInfo,
    launch: response._launch
  };
});

ipcMain.handle('analysis:start', async (_event, payload) => {
  if (activeAnalysisProcess) {
    throw new Error('当前已有任务在运行，请先等待其完成或手动取消。');
  }

  return new Promise((resolve, reject) => {
    const { child, launch } = spawnBackend('analyze', payload, payload?.engine || {});
    activeAnalysisProcess = child;
    let stdoutBuffer = '';
    let stderrBuffer = '';
    let started = false;

    child.stdout.on('data', (chunk) => {
      stdoutBuffer += chunk.toString('utf8');
      const lines = stdoutBuffer.split(/\r?\n/);
      stdoutBuffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }
        try {
          const event = JSON.parse(line);
          emitAnalysisEvent({ ...event, launch });
          if (!started && ['started', 'completed', 'failed'].includes(event.type)) {
            started = true;
            resolve({ ok: true, launch });
          }
        } catch (error) {
          emitAnalysisEvent({ type: 'log', level: 'error', message: `解析消息失败：${error.message}` });
        }
      }
    });

    child.stderr.on('data', (chunk) => {
      stderrBuffer += chunk.toString('utf8');
      const lines = stderrBuffer.split(/\r?\n/);
      stderrBuffer = lines.pop() || '';
      for (const line of lines) {
        if (line.trim()) {
          emitAnalysisEvent({ type: 'log', level: 'info', message: line.trim() });
        }
      }
    });

    child.on('error', (error) => {
      activeAnalysisProcess = null;
      reject(new Error(`无法启动分析后端：${error.message}`));
    });

    child.on('close', (code) => {
      activeAnalysisProcess = null;
      if (stderrBuffer.trim()) {
        emitAnalysisEvent({ type: 'log', level: 'info', message: stderrBuffer.trim() });
      }
      if (!started && code !== 0) {
        reject(new Error(`分析进程异常退出，退出码 ${code}`));
      }
      emitAnalysisEvent({ type: 'process-exit', code });
    });
  });
});

ipcMain.handle('analysis:cancel', async () => {
  if (!activeAnalysisProcess) {
    return { ok: true, cancelled: false };
  }

  activeAnalysisProcess.kill();
  activeAnalysisProcess = null;
  emitAnalysisEvent({ type: 'cancelled', message: '任务已取消。' });
  return { ok: true, cancelled: true };
});

ipcMain.handle('shell:open-path', async (_event, targetPath) => {
  if (!targetPath) {
    return '';
  }
  return shell.openPath(targetPath);
});

ipcMain.handle('shell:open-external', async (_event, targetUrl) => {
  if (!targetUrl) {
    return false;
  }
  await shell.openExternal(targetUrl);
  return true;
});

ipcMain.handle('shell:show-item', async (_event, targetPath) => {
  if (!targetPath) {
    return false;
  }
  shell.showItemInFolder(targetPath);
  return true;
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
