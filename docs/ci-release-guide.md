# SQL-Guard CI/CD 工作流规则说明

## 一、触发规则（Triggers）

| 事件 | Windows | macOS |
|---|---|---|
| push 到 `main` / `master` / `develop` | ✅ | ✅ |
| push `v*` 格式 tag（如 `v1.0.0`） | ✅ | ✅ |
| 手动触发（`workflow_dispatch`） | ✅ | ✅ |

> **发布分发**：只有 push `v*` tag 才会触发 GitHub Release 上传，普通分支 push 只产出 Artifact。

> **发布权限**：两个工作流都配置了 `permissions: contents: write`，这是 `softprops/action-gh-release` 创建和更新 Release 资产所必需的。

> **发布串行**：两个工作流共享同一个 `concurrency` 组，且 macOS 矩阵使用 `max-parallel: 1`，避免 Win/Mac 或不同架构同时改写同一个 Release。

---

## 二、运行环境

| 项目 | Windows | macOS |
|---|---|---|
| Runner | `windows-2025-vs2026` | `macos-latest` |
| Node.js | 18 | 18 |
| 构建架构 | x64（单一） | arm64 + x64（矩阵并行） |
| 打包格式 | NSIS 安装包 + Portable EXE | DMG |
| Release Action | `softprops/action-gh-release@v3` | `softprops/action-gh-release@v3` |

---

## 三、构建步骤（Build Steps）

### Windows

1. `Checkout` → 拉取代码
2. `Compute build metadata` → 读取 `package.json` 版本号、当前日期、Run 编号（PowerShell）
3. `Setup Node 18` → 安装 Node.js
4. `npm install` → 安装依赖
5. `Build Windows x64` → 生成 NSIS 安装包（`.exe Setup`）
6. `Build Windows portable x64` → 生成便携版（`.exe`，无安装器）
7. `Prepare artifacts` → 重命名并移入 `dist/artifacts/installer/` 与 `dist/artifacts/portable/`，生成 `SHA256SUMS.txt`
8. `Upload installer artifact` → 上传安装包到 Artifact（保留 90 天）
9. `Upload portable artifact` → 上传便携版到 Artifact（保留 90 天）
10. `Create Release`（仅 tag）→ 通过 `softprops/action-gh-release@v3` 上传 installer + portable 目录下所有文件到 GitHub Release；发布阶段由 `concurrency` 串行化，macOS 矩阵使用 `max-parallel: 1`

### macOS（arm64 / x64 并行）

1. `Checkout` → 拉取代码
2. `Compute build metadata` → 读取版本号、日期、Run 编号（bash）
3. `Setup Node 18` → 安装 Node.js
4. `npm install` → 安装依赖
5. `Build macOS {arch} dmg` → 生成对应架构的 DMG 文件
6. `Prepare artifacts` → 重命名至 `dist/artifacts/{arch}/`，生成 `SHA256SUMS.txt`
7. `Upload macOS artifact` → 上传 DMG 到 Artifact（保留 90 天）
8. `Create Release assets`（仅 tag）→ 通过 `softprops/action-gh-release@v3` 上传 DMG + checksum 到 GitHub Release；发布阶段由 `concurrency` 串行化，macOS 矩阵使用 `max-parallel: 1`

---

## 四、产物命名规范（Artifact Naming）

统一格式：

```
sql-guard-{平台}-{架构}-v{version}-{yyyyMMdd}-run{N}.{ext}
```

示例：

| 平台 | 文件名示例 |
|---|---|
| Windows 安装包 | `sql-guard-installer-v1.2.0-20260512-run42.exe` |
| Windows 便携版 | `sql-guard-portable-v1.2.0-20260512-run42.exe` |
| macOS arm64 | `sql-guard-macos-arm64-v1.2.0-20260512-run42.dmg` |
| macOS x64 | `sql-guard-macos-x64-v1.2.0-20260512-run42.dmg` |

每个产物目录下均附按目标命名的 `*-SHA256SUMS.txt`（如 `sql-guard-installer-v1.2.0-20260512-run42-SHA256SUMS.txt`）用于完整性校验。

---

## 五、构建元数据注入

两个工作流都通过 `electron-builder` 的 `--config.extraMetadata` 将以下字段注入应用：

| 字段 | 内容 | 用途 |
|---|---|---|
| `buildDate` | `yyyyMMdd` | 在 Helper > About 中展示构建日期 |
| `buildRun` | GitHub Run 编号 | 追踪具体 CI 构建批次 |

---

## 六、发布流程（Release Flow）

```
git tag v1.2.0 && git push origin v1.2.0
        │
        ├── 触发 build-windows.yml
      │     └── 按共享 `concurrency` 顺序执行 → 上传 installer + portable → GitHub Release v1.2.0
        │
        └── 触发 build-macos.yml（arm64 + x64 顺序执行）
              └── 按共享 `concurrency` 顺序执行 → 上传 arm64 dmg + x64 dmg → GitHub Release v1.2.0
```

一次 tag push，Release 页面最终产出 5 个文件：安装包、便携版、arm64 DMG、x64 DMG、各自的 SHA256SUMS.txt。

---

## 七、相关文件

| 文件 | 说明 |
|---|---|
| [.github/workflows/build-windows.yml](../.github/workflows/build-windows.yml) | Windows 构建工作流 |
| [.github/workflows/build-macos.yml](../.github/workflows/build-macos.yml) | macOS 构建工作流 |
| [electron/package.json](../electron/package.json) | 应用版本号（`version` 字段）即为 Release tag 版本来源 |
