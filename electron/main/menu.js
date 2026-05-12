const path = require("path");
const { app, Menu, dialog, shell } = require("electron");

const PROJECT_GITHUB_URL = "https://github.com/dsw0214/sql-guard";
const DEVELOPER_NAME = "shiwei";
const COPYRIGHT_TEXT = "Copyright (c) 2026 shiwei. All rights reserved.";

function readBuildMetadata() {
  try {
    const pkg = require(path.join(app.getAppPath(), "package.json"));
    const buildDate = typeof pkg.buildDate === "string" ? pkg.buildDate : "";
    const buildRun = typeof pkg.buildRun === "string" ? pkg.buildRun : "";
    return { buildDate, buildRun };
  } catch {
    return { buildDate: "", buildRun: "" };
  }
}

function showAboutDialog(parentWindow) {
  const { buildDate, buildRun } = readBuildMetadata();
  const buildInfo = buildDate ? `${buildDate}${buildRun ? ` (run ${buildRun})` : ""}` : "unknown";

  dialog.showMessageBox(parentWindow, {
    type: "info",
    title: "About SQLGuard",
    message: "sql-guard",
    detail: [
      `Version: ${app.getVersion()}`,
      `Developer: ${DEVELOPER_NAME}`,
      COPYRIGHT_TEXT,
    ].join("\n"),
    buttons: ["OK"],
  });
}

function buildMenuTemplate(mainWindow) {
  const base = [
    {
      label: "File",
      submenu: [{ role: "quit" }],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    {
      label: "Window",
      submenu: [{ role: "minimize" }, { role: "close" }],
    },
    {
      label: "Helper",
      submenu: [
        {
          label: "About",
          click: () => showAboutDialog(mainWindow),
        },
        {
          label: "Open GitHub Repository",
          click: () => shell.openExternal(PROJECT_GITHUB_URL),
        },
      ],
    },
  ];

  if (process.platform === "darwin") {
    base.unshift({
      label: app.name,
      submenu: [
        {
          label: "About",
          click: () => showAboutDialog(mainWindow),
        },
        { type: "separator" },
        { role: "services" },
        { type: "separator" },
        { role: "hide" },
        { role: "hideOthers" },
        { role: "unhide" },
        { type: "separator" },
        { role: "quit" },
      ],
    });
  }

  return base;
}

function registerApplicationMenu(mainWindow) {
  const menu = Menu.buildFromTemplate(buildMenuTemplate(mainWindow));
  Menu.setApplicationMenu(menu);
}

module.exports = {
  registerApplicationMenu,
};
