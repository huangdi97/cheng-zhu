const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('regionCapture', {
  done: (rect) => ipcRenderer.send('region-capture-done', rect),
  cancel: () => ipcRenderer.send('region-capture-cancel'),
});
