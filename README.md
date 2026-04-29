# TTS 语料挑选工具

GPT-SoVITS TTS 语料挑选与优化工具，提供 Web UI 用于浏览、对比、筛选和重新生成语音语料。

## 功能

- **语料浏览** — 查看所有语料（编号 + 文本），支持搜索和状态过滤
- **对比播放** — 并排播放参照语音和生成语音，直观对比效果
- **切换参考音频** — 按 5 种风格分类选择不同参考音频重新生成
- **删除语料** — 删除不满意的生成音频
- **批量操作** — 勾选多条语料统一重新生成或删除

## 快速开始

### 1. 启动 GPT-SoVITS API

```bash
# 在 GPT-SoVITS 根目录下启动 API
python api_v2.py --port 9880
```

### 2. 启动语料挑选工具

```bash
python server.py
```

打开浏览器访问 http://localhost:8888

### 3. 批量合成（可选）

```bash
python batch_infer.py
```

### 4. 单条合成（可选）

```bash
python batch_infer_single.py --id 123 --ref 100.WAV
```

## 项目结构

```
├── index.html                  # Web UI (纯 JS，无框架)
├── server.py                   # 后端服务 (Python 标准库)
├── batch_infer.py              # 批量推理脚本
├── batch_infer_single.py       # 单条推理脚本
├── wangye_corpus_1000.txt      # 1000 条目标语料文本
├── raw/
│   ├── wangyevoice/*.WAV       # 128 条参考音频
│   └── wangye.list             # 参考音频元数据
└── wav/                        # 生成音频输出目录 (不在版本控制中)
    ├── *.wav                   # 生成的 WAV 文件
    ├── metadata.csv            # 已生成语料索引
    ├── ref_mapping.txt         # 语料-参考音频映射数据库
    └── batch_inference.log     # 推理日志
```

## 参考音频风格

| 风格 | 标签 | 说明 |
|------|------|------|
| lazy | 😮‍💨 慵懒/日常 | 王也的招牌慵懒风格，适合日常对话 |
| serious | 📜 沉稳/长篇 | 正式内容、成语诗词、长篇论述 |
| casual | 💬 对话/轻松 | 短句、轻松对话 |
| question | ❓ 疑问/反问 | 带问号的疑问句 |
| strong | ⚡ 严肃/气势 | 严肃宣言、气势磅礴的内容 |

## 技术栈

- **前端** — 纯 HTML + CSS + JavaScript (无框架)
- **后端** — Python `http.server` (标准库，零依赖)
- **推理** — GPT-SoVITS API (`localhost:9880`)
