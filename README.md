# TTS 语料挑选工具

GPT-SoVITS TTS 语料挑选与优化工具，提供 Web UI 用于浏览、对比、筛选和重新生成语音语料。

## 功能

| 功能 | 说明 |
|------|------|
| 语料浏览 | 1000 条语料列表，支持搜索、锁定状态切换、评级筛选 |
| 对比播放 | 并排播放参照语音和生成语音，互斥播放，进度重置 |
| 参考音频切换 | 按 5 种风格分类选择参考音频，点击即播放 |
| 重新生成 | 选定参考音频后调用 GPT-SoVITS API 重新合成 |
| 随机生成 | 随机选择一条参考音频重新生成 |
| 删除 | 删除不满意的生成音频文件 |
| 语音质量评级 | 优秀/良好/一般/差 四级评级 |
| 锁定/解锁 | 锁定已确认语料防止误改，评级优秀/良好/一般时自动锁定 |
| 多选操作 | Ctrl+点击切换单选，Shift+点击范围选择 |
| 批量操作 | 勾选多条统一重新生成、删除或清空评级 |
| Zen 模式 | 键盘驱动的批量筛选模式，自动播放+倒计时评级 |

## 快速开始

```bash
# 1. 启动 GPT-SoVITS API (在 GPT-SoVITS 根目录)
python api_v2.py --port 9880

# 2. 启动语料挑选工具
python server.py [--port 8888] [--api-port 9880]
```

访问 http://localhost:8888

## 项目结构

```
├── index.html                  # Web UI (纯 HTML 结构)
├── server.py                   # 后端服务 (Python 标准库 http.server)
├── batch_infer.py              # 批量推理脚本
├── batch_infer_single.py       # CLI 单条推理脚本
├── wangye_corpus_1000.txt      # 1000 条目标语料文本
├── raw/
│   ├── wangyevoice/*.WAV       # 128 条参考音频
│   ├── wangye.list             # 参考音频元数据 (path|speaker|lang|text)
│   └── refs.txt                # 参考音频配置 (style|num|text)
├── static/
│   ├── style.css               # 所有样式
│   ├── state.js                # 全局状态变量
│   ├── api.js                  # API 请求封装
│   ├── utils.js                # 工具函数 (toast, escHtml)
│   ├── render.js               # 列表/详情/参考音频渲染
│   ├── actions.js              # 用户操作 (生成/删除/评级/批量)
│   ├── zen.js                  # Zen 模式逻辑
│   └── main.js                 # 事件绑定 & 入口
└── wav/                        # 生成音频输出目录 (不在 git 中)
    ├── *.wav                   # 生成的 WAV 文件
    ├── metadata.csv            # 已生成语料索引 (id|text)
    ├── ref_mapping.txt         # 语料-参考音频映射 (id|ref_name|ref_text)
    ├── rating.txt              # 评级数据库 (id|level)
    ├── lock_status.txt         # 锁定状态 (每行一个 id)
    └── batch_inference.log     # 推理日志
```

## 后端 API

### 静态文件服务
`server.py` 基于 `http.server.SimpleHTTPRequestHandler`，提供根目录的静态文件服务。`/static/` 路径自动映射到 `static/` 目录。

### REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/corpus` | 返回所有语料列表，含生成状态、锁定状态、评级、参考音频 |
| GET | `/api/refs` | 返回所有参考音频，按风格分组 |
| GET | `/api/status` | 返回已生成数量统计 |
| POST | `/api/regenerate` | 单条重新生成 `{id, ref}` |
| POST | `/api/batch-regenerate` | 批量重新生成 `{ids[], ref}` |
| POST | `/api/lock/{id}` | 切换锁定 `{locked}` |
| POST | `/api/rating/{id}` | 设置评级 `{rating}`，rating 可选: excellent/good/fair/poor/none |
| DELETE | `/api/wav/{id}` | 删除生成音频 |

### 外部依赖
- GPT-SoVITS API (`localhost:9880`) — 实际的 TTS 推理服务
- `requests` — Python 第三方库

### 数据库文件
所有状态持久化为纯文本文件，格式为 `id|field1|field2` 每行一条。

## 前端架构

前端为纯 JavaScript 实现，无框架依赖。通过 `<script>` 标签按顺序加载，共享全局状态：

```
state.js → api.js → utils.js → render.js → actions.js → zen.js → main.js
```

### 模块职责

| 文件 | 行数 | 职责 |
|------|------|------|
| `state.js` | 12 | 全局状态：corpusData, refsData, selectedId, checkedIds 等 |
| `api.js` | 5 | `api(path, opts)` — fetch 封装 |
| `utils.js` | 13 | `toast()` 通知、`escHtml()` HTML 转义 |
| `render.js` | 389 | 列表渲染、详情渲染、参考音频选择器、音频控制、选择/锁定逻辑 |
| `actions.js` | 264 | 重新生成、随机生成、评级、删除、批量操作、评级筛选 |
| `zen.js` | 239 | Zen 模式：队列管理、自动播放、倒计时、键盘事件、评级 |
| `main.js` | 26 | 事件绑定、数据加载入口 |

## Zen 模式

键盘驱动的快速筛选工作流，用于大批量语料初筛。

### 入口
点击页面右上角 `🎧 Zen模式` 按钮。

### 工作流程
1. 从第一个 **未锁定且未评级** 的已生成语料开始
2. 自动播放生成语音
3. 播放完成后开始 **5 秒倒计时**
4. 倒计时期间操作：

### 快捷键

| 按键 | 操作 |
|------|------|
| `←` / `→` | 上一条 / 下一条 |
| `A` | 评级 **优秀** → 锁定 → 下一条 |
| `S` | 评级 **良好** → 锁定 → 下一条 |
| `D` | 评级 **一般** → 锁定 → 下一条 |
| `F` | 评级 **差** → 不锁定 → 下一条 |
| `R` | 重播生成语音 |
| `Q` | 播放参照语音 |
| `空格` | 随机参照生成 |
| `ESC` | 退出 Zen 模式 |

### 倒计时规则
- 5 秒内未评级 → 不锁定 → 自动切换下一条
- 倒计时区域始终可见，初始显示"等待播放完成..."
- 播放结束后才开始计时，避免界面抖动

## 参考音频风格

| 风格 | 数量 | 标签 | 适用场景 |
|------|------|------|----------|
| lazy | 20 | 😮‍💨 慵懒/日常 | 日常对话、慵懒语气 |
| serious | 39 | 📜 沉稳/长篇 | 长篇论述、成语诗词、正式内容 |
| casual | 21 | 💬 对话/轻松 | 短句、轻松对话 |
| question | 13 | ❓ 疑问/反问 | 带问号的疑问句 |
| strong | 16 | ⚡ 严肃/气势 | 严肃宣言、气势磅礴 |
| **总计** | **109** | | |

配置在 `raw/refs.txt` 中，格式：`style|编号|文本`

## 技术栈

- **前端** — 纯 HTML + CSS + JavaScript (无框架)
- **后端** — Python `http.server` + `requests`
- **推理** — GPT-SoVITS API (`localhost:9880`)
