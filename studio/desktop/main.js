const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const isDev = require('electron-is-dev');

let mainWindow;
let backendProcess;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#101622'
    });

    // In production, we'd serve the built React app.
    // In dev, we can point to the dev server or a local file.
    const startUrl = isDev
        ? 'http://localhost:3000'
        : `file://${path.join(__dirname, '../frontend/dist/index.html')}`;

    mainWindow.loadURL(startUrl);

    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

let llamaServerProcess;

function startBackend() {
    console.log("Starting FastAPI Backend...");
    
    let exePath;
    let args = [];
    
    if (isDev) {
        exePath = process.platform === 'win32' ? 'python' : 'python3';
        args = [path.join(__dirname, '../backend/main.py')];
    } else {
        // PyInstaller bundles the backend binary into the resources/python-runtime folder
        const resourcesPath = process.resourcesPath;
        exePath = process.platform === 'win32'
            ? path.join(resourcesPath, 'python-runtime', 'backend.exe')
            : path.join(resourcesPath, 'python-runtime', 'backend');
    }

    console.log(`Spawning backend: ${exePath} with args: ${args.join(' ')}`);
    backendProcess = spawn(exePath, args);

    backendProcess.stdout.on('data', (data) => {
        console.log(`Backend stdout: ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`Backend stderr: ${data}`);
    });
}

function startLlamaServer() {
    if (isDev) {
        console.log("llama-server is skipped in dev mode.");
        return;
    }
    
    const fs = require('fs');
    const resourcesPath = process.resourcesPath;
    const llamaServerPath = process.platform === 'win32'
        ? path.join(resourcesPath, 'llama-server.exe')
        : path.join(resourcesPath, 'llama-server');
        
    const modelPath = path.join(resourcesPath, 'models', 'qwen2.5-coder-3b-q4.gguf');
    
    if (fs.existsSync(llamaServerPath) && fs.existsSync(modelPath)) {
        console.log("Starting embedded llama-server...");
        llamaServerProcess = spawn(llamaServerPath, [
            '-m', modelPath,
            '-c', '2048',
            '--port', '11434' // Run on mock Ollama port
        ]);
        
        llamaServerProcess.stdout.on('data', (data) => {
            console.log(`llama-server: ${data}`);
        });
        
        llamaServerProcess.stderr.on('data', (data) => {
            console.error(`llama-server stderr: ${data}`);
        });
    } else {
        console.log("llama-server or model file not found in extraResources. Skipping embedded llama-server startup.");
    }
}

app.on('ready', () => {
    startBackend();
    startLlamaServer();
    createWindow();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('will-quit', () => {
    if (backendProcess) {
        backendProcess.kill();
    }
    if (llamaServerProcess) {
        llamaServerProcess.kill();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

