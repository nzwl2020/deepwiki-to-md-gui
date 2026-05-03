# deepwiki-to-md-gui

![项目封面](docs/images/hero.png)

## 1. 项目简介

`deepwiki-to-md-gui` 是一个用于导出 DeepWiki 内容的桌面图形化工具。

它可以将 DeepWiki 上的内容导出为本地 Markdown 文件，适用于以下两类内容：

1. 仓库解读文档（Wiki）
2. 用户会话记录（Chat）

与原始项目主要面向 Docker / CLI 的使用方式不同，这个 fork 版本面向日常桌面使用场景，重点提供更适合 Windows 用户的 GUI 操作体验。

---

## 2. 功能特性

- 支持导出 DeepWiki Chat 会话内容为 Markdown
- 支持导出 DeepWiki Wiki 内容为 Markdown
- 自动保存 Mermaid 图表为独立 SVG 文件
- 支持在图形界面中输入 URL、选择输出目录并执行导出
- 支持查看导出日志和打开导出目录
- 支持打包为 Windows 可执行程序

---

## 3. 适用场景

这个工具适合以下场景：

- 想将 DeepWiki 的聊天记录保存到本地进行整理
- 想将 DeepWiki 的仓库解读文档离线归档
- 不希望每次都手动执行 Python 命令
- 不希望依赖 Docker 环境
- 希望通过图形界面完成导出操作

---

## 4. 运行环境

### 4.1 开发运行环境

建议使用以下环境：

- Python 3.12
- Windows 10 / Windows 11
- 已安装 Chromium 运行资源（通过 Playwright 安装）

### 4.2 主要依赖

- Playwright
- BeautifulSoup4
- lxml
- markdownify
- PySide6

---

## 5. 安装方式

### 5.1 从源码运行 GUI

进入项目目录后，安装依赖：

```bash
python -m pip install -e .
python -m playwright install chromium
```

安装完成后，启动 GUI：

```bash
python -m src.interface.gui_app
```

本项目已经通过 `pyproject.toml` 注册了 GUI 启动入口，也可以直接运行：

```bash
deepwiki-to-md-gui
```

---

## 6. 使用方式

### 6.1 导出 Chat 会话

1. 启动程序
2. 在 URL 输入框中粘贴 DeepWiki Chat 页面地址，例如：

```text
https://deepwiki.com/search/your-chat-id
```

3. 选择输出目录
4. 点击“Start Export”
5. 等待日志显示导出完成
6. 点击“Open Output”打开导出目录

### 6.2 导出 Wiki 文档

1. 启动程序
2. 在 URL 输入框中粘贴 DeepWiki Wiki 地址，例如：

```text
https://deepwiki.com/your-org/your-repo
```

3. 选择输出目录
4. 点击“Start Export”
5. 等待导出完成

### 6.3 自动识别模式

程序会根据输入的 URL 自动识别导出模式：

- `https://deepwiki.com/search/...` 识别为 Chat
- `https://deepwiki.com/<组织>/<仓库>` 识别为 Wiki

---

## 7. 输出目录结构

### 7.1 Chat 导出结果

```text
输出目录/
└── chat/
    └── <chat_id>/
        ├── chat.md
        └── images/
            ├── 0__diagram_0.svg
            ├── 0__diagram_1.svg
            └── ...
```

### 7.2 Wiki 导出结果

```text
输出目录/
└── wiki/
    └── <organization>/
        └── <repository>/
            ├── index.md
            ├── 1-xxx.md
            ├── 2-xxx.md
            ├── 3-xxx.md
            └── images/
                ├── 1__diagram_0.svg
                ├── 2__diagram_0.svg
                └── ...
```

---

## 8. Windows 打包方式

如果你希望将 GUI 打包成 Windows 可执行程序，可以使用项目内提供的打包脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

打包完成后，可执行程序通常位于：

```text
dist\DeepWikiExporter\
```

你可以直接运行：

```text
dist\DeepWikiExporter\DeepWikiExporter.exe
```

---

## 9. 项目结构说明

```text
src/
├── domain/
│   ├── constants.py
│   ├── entities.py
│   ├── export_models.py
│   └── url_parser.py
│
├── gateway/
│   ├── web_adapter.py
│   ├── html_adapter.py
│   ├── markdown_adapter.py
│   └── file_adapter.py
│
├── repository/
│   ├── web_repository.py
│   ├── html_repository.py
│   ├── markdown_repository.py
│   └── file_repository.py
│
├── usecase/
│   ├── chat_page_usecase.py
│   └── wiki_site_usecase.py
│
└── interface/
    ├── bootstrap.py
    ├── gui_worker.py
    └── gui_app.py
```

各层职责概述如下：

- `domain`：定义核心实体、URL 解析规则、导出结果模型
- `gateway`：封装 Playwright、文件系统、Markdown 转换等外部能力
- `repository`：组织数据访问与转换流程
- `usecase`：实现 chat/wiki 的导出业务流程
- `interface`：提供 GUI 入口、后台任务执行和依赖组装

---

## 10. 常见问题

### 10.1 启动 GUI 时报错：缺少 PySide6

请确认已经安装依赖：

```bash
python -m pip install -e .
```

### 10.2 启动导出时报错：未安装 Chromium

请执行：

```bash
python -m playwright install chromium
```

### 10.3 页面能打开，但没有导出内容

可能原因包括：

- DeepWiki 页面结构发生变化
- 当前页面未完全加载
- 目标页面不是支持的 DeepWiki 页面类型

建议先查看 GUI 日志区输出，再判断是页面结构变化还是网络问题。

### 10.4 导出速度较慢

首次运行时，Playwright 需要启动浏览器环境。  
此外，Wiki 导出通常会抓取多个页面，因此耗时会明显高于单个 Chat 导出。

---

## 11. 开发说明

### 11.1 本地运行

```bash
python -m pip install -e .
python -m playwright install chromium
python -m src.interface.gui_app
```

### 11.2 构建 GUI 可执行程序

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

### 11.3 调试建议

如果导出失败，优先检查：

1. URL 是否为有效的 DeepWiki 页面
2. Chromium 是否已安装
3. 输出目录是否可写
4. 日志区是否出现 HTML 结构解析失败相关提示

---

## 12. 说明

本项目基于原始 `deepwiki-to-md` 项目进行二次开发，目标是提供更适合桌面用户，尤其是 Windows 用户的图形化使用体验。

如果原始 DeepWiki 页面结构发生变化，可能需要同步调整 HTML 解析逻辑。
