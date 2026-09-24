const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('briskDexAPI', {
  openSavDialog: () => ipcRenderer.invoke('open-sav'),
  writeSav: (filePath, bytes) => ipcRenderer.invoke('write-sav', filePath, bytes),
  loadStorage: () => ipcRenderer.invoke('load-storage'),
  saveStorage: (data) => ipcRenderer.invoke('save-storage', data),
  openIconFolderDialog: () => ipcRenderer.invoke('open-icon-folder')
});
