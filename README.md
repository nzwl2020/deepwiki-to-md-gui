# deepwiki-to-md-gui

![项目封面](docs/images/hero.png)

## 1. 项目简介

`deepwiki-to-md-gui` 是一个用于导出 DeepWiki 内容的桌面图形化工具。

它可以将 DeepWiki 上的两类内容导出为本地 Markdown 文件：

1. 仓库解读文档（Wiki）
2. 用户会话记录（Chat）

和原始项目偏向 Docker / CLI 的使用方式不同，这个 fork 版本面向日常桌面场景，重点提供更适合 Windows 用户的 GUI 体验。

---

## 2. 功能特性

- 支持导出 DeepWiki Chat 会话内容为 Markdown
- 支持导出 DeepWiki Wiki 内容为 Markdown
- 支持批量 URL 队列导出
- 支持后台导出、取消导出、失败任务重试
- 支持运行前环境自检
- 支持导出历史记录与历史任务回填
- 支持导出完成后直接预览 Markdown
- 支持增量导出，复用已生成的 Markdown 文件
- 支持选择 Wiki 的部分页面进行导出
- 支持生成 Wiki 目录页 `index.md`
- 支持生成合并版 Wiki 文档 `wiki.md`
- 支持控制 Mermaid 图导出
- 支持控制 Chat 的代码引用区块导出
- 支持打包为 Windows 可执行程序

---

## 3. 适用场景

这个工具适合以下场景：

- 想把 DeepWiki 聊天记录保存到本地整理
- 想把仓库解读文档离线归档
- 想一次性导出多个 DeepWiki 链接
- 不希望每次都手动执行 Python 命令
- 不希望依赖 Docker 环境
- 希望通过图形界面完成导出、预览和重试

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

### 6.1 基础导出流程

1. 启动程序
2. 在 URL 输入框中粘贴一个或多个 DeepWiki URL，每行一个
3. 选择输出目录
4. 根据需要配置导出选项
5. 点击 `Start Export`
6. 在日志区和进度区查看导出状态
7. 导出完成后使用 `Open Output` 或 `Open Markdown`

### 6.2 支持的 URL 形式

程序会根据输入的 URL 自动识别模式：

- `https://deepwiki.com/search/...` 识别为 Chat
- `https://deepwiki.com/<组织>/<仓库>` 识别为 Wiki

### 6.3 队列导出

- 支持一次输入多个 URL
- Worker 会按队列顺序逐个执行导出
- 某个任务失败不会阻止后续任务继续执行
- 失败任务可以通过 `Retry Failed` 重新运行

### 6.4 导出选项说明

- `Incremental export`
  - 如果目标 Markdown 已存在，则优先复用已有文件
  - 对已经导出的 Chat 或 Wiki 页面尤其有用
- `Generate wiki index`
  - 为 Wiki 导出生成 `index.md`
- `Generate merged wiki file`
  - 生成合并版 `wiki.md`
  - 会按照页面顺序拼接所有选中的 Wiki 页面
- `Export Mermaid diagrams`
  - 导出 Mermaid 图为独立 SVG 文件
  - 关闭后会在 Markdown 中保留“已省略图表”的占位提示
- `Include chat code references`
  - 控制 Chat 导出中是否保留代码引用区块

### 6.5 Wiki 页面筛选

当 URL 输入框中只有一个有效的 Wiki URL 时，可以使用：

- `Select Wiki Pages`
  - 先加载当前 Wiki 的导航页面
  - 再勾选需要导出的页面子集
- `Clear Page Filter`
  - 清除当前 Wiki 的页面过滤条件

页面筛选条件会持久化保存，并且会随历史记录一起恢复。

### 6.6 运行辅助能力

- `Run Self-Check`
  - 检查 Chromium
  - 检查输出目录是否可写
  - 检查是否能访问 `deepwiki.com`
- 导出历史
  - 记录 URL、模式、导出结果、复用数量、预览文件、导出选项
- Markdown 预览
  - 最近一次成功导出的 Markdown 会直接显示在预览页

---

## 7. 输出目录结构

### 7.1 Chat 导出结果

默认情况下：

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

如果关闭 `Export Mermaid diagrams`，则不会生成 `images/`。

### 7.2 Wiki 导出结果

典型输出如下：

```text
输出目录/
└── wiki/
    └── <organization>/
        └── <repository>/
            ├── index.md
            ├── wiki.md
            ├── 1-xxx.md
            ├── 2-xxx.md
            ├── 3-xxx.md
            └── images/
                ├── 1__diagram_0.svg
                ├── 2__diagram_0.svg
                └── ...
```

说明：

- `index.md` 只有在启用 `Generate wiki index` 时生成
- `wiki.md` 只有在启用 `Generate merged wiki file` 时生成
- `images/` 只有在启用 `Export Mermaid diagrams` 时生成
- 选择性导出 Wiki 页面时，只会生成被勾选的页面文件

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

- `domain`
  - 定义核心实体、URL 解析规则、任务选项、导出结果模型
- `gateway`
  - 封装 Playwright、文件系统、Markdown 转换等外部能力
- `repository`
  - 负责 HTML 解析结果组装、Markdown 生成、导出过程数据转换
- `usecase`
  - 实现 chat/wiki 的导出业务流程
  - 处理页面筛选、增量导出、合并文档等策略
- `interface`
  - 提供 GUI 入口、后台任务执行、历史记录、预览、自检和依赖组装

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

也可以在 GUI 中先运行 `Run Self-Check`。

### 10.3 页面能打开，但没有导出内容

可能原因包括：

- DeepWiki 页面结构发生变化
- 当前页面未完全加载
- 目标页面不是支持的 DeepWiki 页面类型
- 你启用了 Wiki 页面筛选，但当前筛选条件已经失效

建议先查看 GUI 日志区输出，再判断是页面结构变化、筛选条件问题还是网络问题。

### 10.4 导出速度较慢

首次运行时，Playwright 需要启动浏览器环境。  
此外，Wiki 导出通常会抓取多个页面，因此耗时会明显高于单个 Chat 导出。

如果同一批内容已经导出过，可以启用 `Incremental export` 来减少重复抓取。

### 10.5 为什么没有生成 `index.md` / `wiki.md` / `images`

通常是因为对应导出选项被关闭：

- `Generate wiki index`
- `Generate merged wiki file`
- `Export Mermaid diagrams`

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
5. Wiki 页面筛选条件是否仍对应当前导航
6. 是否启用了增量导出，导致直接复用了已有文件

---

## 12. 说明

本项目基于原始 `deepwiki-to-md` 项目进行二次开发，目标是提供更适合桌面用户，尤其是 Windows 用户的图形化使用体验。

如果 DeepWiki 页面结构发生变化，可能需要同步调整 HTML 解析逻辑和导航提取逻辑。
