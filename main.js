const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs/promises');
const fsSync = require('fs');

let mainWindow;

function createWindow(){
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 720,
    minHeight: 560,
    backgroundColor: '#0d1811',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  mainWindow.loadFile(path.join(__dirname, 'index.html'));
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

function storagePath(){
  return path.join(app.getPath('userData'), 'briskdex-storage.json');
}

/* ---- Open a .sav file via native dialog, return its path + raw bytes ---- */
ipcMain.handle('open-sav', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open a Brisk Emerald save file',
    filters: [{ name: 'Game Boy Advance Save', extensions: ['sav'] }],
    properties: ['openFile']
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  const filePath = result.filePaths[0];
  const buffer = await fs.readFile(filePath);
  return { filePath, buffer: new Uint8Array(buffer) };
});

/* ---- Write modified save bytes back to disk, keeping a timestamped backup ---- */
ipcMain.handle('write-sav', async (event, filePath, bytes) => {
  try{
    const dir = path.dirname(filePath);
    const base = path.basename(filePath, path.extname(filePath));
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupPath = path.join(dir, `${base}.backup-${stamp}.sav`);
    if (fsSync.existsSync(filePath)){
      await fs.copyFile(filePath, backupPath);
    }
    await fs.writeFile(filePath, Buffer.from(bytes));
    return { ok: true, backupPath };
  }catch(err){
    return { ok: false, error: err.message };
  }
});

/* ---- External storage persisted as a JSON file outside the app bundle ---- */
ipcMain.handle('load-storage', async () => {
  try{
    const raw = await fs.readFile(storagePath(), 'utf8');
    return JSON.parse(raw);
  }catch(err){
    return [];
  }
});

ipcMain.handle('save-storage', async (event, data) => {
  await fs.writeFile(storagePath(), JSON.stringify(data));
  return { ok: true };
});

/* ---- Load a folder of icon images. Supports two layouts:
   1) flat: <folder>/<speciesId>.png   (output of tools/extract_data.py)
   2) source tree: <folder>/<name>/icon.png (a graphics/pokemon checkout) --
      in this case we key by folder name; the renderer matches names to ids. */
ipcMain.handle('open-icon-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Choose an icon folder (brisk-dex-icons, or graphics/pokemon)',
    properties: ['openDirectory']
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  const folderPath = result.filePaths[0];
  const icons = {};

  const entries = await fs.readdir(folderPath, { withFileTypes: true });

  const toDataUrl = async (filePath) => {
    const buf = await fs.readFile(filePath);
    const ext = path.extname(filePath).toLowerCase();
    const mime = ext === '.gif' ? 'image/gif' : ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg' : 'image/png';
    return `data:${mime};base64,${buf.toString('base64')}`;
  };

  for (const entry of entries){
    if (entry.isFile() && /^\d+\.(png|gif|jpg|jpeg)$/i.test(entry.name)){
      const id = entry.name.replace(/\.[^.]+$/, '');
      icons[id] = await toDataUrl(path.join(folderPath, entry.name));
    } else if (entry.isDirectory()){
      const iconFile = path.join(folderPath, entry.name, 'icon.png');
      if (fsSync.existsSync(iconFile)){
        icons['name:' + entry.name.toLowerCase()] = await toDataUrl(iconFile);
      }
    }
  }
  return { folderPath, icons };
});
