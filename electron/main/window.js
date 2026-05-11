const { BrowserWindow } = require("electron");

const { WINDOW_OPTIONS, getWebPreferences, shouldOpenDevTools } = require("./config.js");

const CSP_HEADER = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "connect-src 'self' http: https:",
  "object-src 'none'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
].join('; ');

function createMainWindow() {
  const win = new BrowserWindow({
    ...WINDOW_OPTIONS,
    webPreferences: getWebPreferences(),
  });

  win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    const responseHeaders = {
      ...details.responseHeaders,
      "Content-Security-Policy": [CSP_HEADER],
    };
    callback({ responseHeaders });
  });

  win.loadFile("index.html");

  if (shouldOpenDevTools()) {
    win.webContents.openDevTools();
  }

  return win;
}

module.exports = {
  createMainWindow,
};
