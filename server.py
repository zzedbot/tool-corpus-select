"""
TTS 语料挑选工具 — 后端服务
启动: python server.py [--port 8888]
打开: http://localhost:8888
"""

import argparse
import json
import os
import requests
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

HOST = "0.0.0.0"
PORT = 8888
API_BASE = "http://localhost:9880"
OUTPUT_DIR = "wav"
TEXT_FILE = "wangye_corpus_1000.txt"
METADATA_FILE = "wav/metadata.csv"
LOG_FILE = "wav/batch_inference.log"
REFS_FILE = "raw/refs.txt"

# 模型路径
GPT_MODEL = "GPT_weights_v2/wangye-e10.ckpt"
SOVITS_MODEL = "SoVITS_weights_v2/wangye_e8_s1024.pth"

# 推理参数
TEMPERATURE = 0.7
TOP_K = 8
TOP_P = 0.8

STYLE_LABELS = {
    "lazy": "😮‍💨 慵懒/日常",
    "serious": "📜 沉稳/长篇",
    "casual": "💬 对话/轻松",
    "question": "❓ 疑问/反问",
    "strong": "⚡ 严肃/气势",
}

def load_refs():
    """从 raw/refs.txt 加载参考音频配置"""
    refs = {}
    path = os.path.join(ROOT_DIR, REFS_FILE)
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|', 2)
            if len(parts) != 3:
                continue
            style, num, text = parts
            refs.setdefault(style, []).append((f"raw/wangyevoice/{num}.WAV", text))
    return refs

# 初始化
REFS = load_refs()

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_models_loaded = False

# 将参考音频路径转为绝对路径（GPT-SoVITS API 需要绝对路径或相对于其自身工作目录的路径）
for style in REFS:
    REFS[style] = [(os.path.join(ROOT_DIR, p), t) for p, t in REFS[style]]


def load_corpus():
    """从 wangye_corpus_1000.txt 加载全部语料"""
    path = os.path.join(ROOT_DIR, TEXT_FILE)
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def get_generated_status():
    """从 metadata.csv + wav 目录判断哪些语料已生成"""
    ids = set()
    # 从 metadata.csv 读取
    meta_path = os.path.join(ROOT_DIR, METADATA_FILE)
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '|' in line:
                    sid = line.split('|', 1)[0]
                    if sid.isdigit():
                        ids.add(int(sid))
    # 从 wav 目录扫描（兜底）
    wav_dir = os.path.join(ROOT_DIR, OUTPUT_DIR)
    if os.path.exists(wav_dir):
        for f in os.listdir(wav_dir):
            if f.endswith('.wav') and f[:-4].isdigit():
                ids.add(int(f[:-4]))
    return ids


# 参考音频映射数据库文件
REF_MAPPING_FILE = "wav/ref_mapping.txt"
# 锁定状态数据库文件
LOCK_STATUS_FILE = "wav/lock_status.txt"

# 缓存：{ corpus_id: (ref_name, ref_text) }
_ref_cache = None


def _save_ref_mapping():
    """保存参考音频映射到 txt 数据库文件"""
    global _ref_cache
    path = os.path.join(ROOT_DIR, REF_MAPPING_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for cid in sorted(_ref_cache.keys()):
            ref_name, ref_text = _ref_cache[cid]
            f.write(f"{cid}|{ref_name}|{ref_text}\n")


def load_ref_mapping():
    """加载参考音频映射：
    1. 先从 batch_inference.log 解析初始数据
    2. 再从 ref_mapping.txt 覆盖（用户手动更新过的优先级更高）
    """
    global _ref_cache
    if _ref_cache is not None:
        return _ref_cache

    import re
    _ref_cache = {}

    # 第一步：从日志解析
    log_path = os.path.join(ROOT_DIR, LOG_FILE)
    if os.path.exists(log_path):
        pattern = re.compile(r'\[\d+\]\s*↳\s*参考:(\d+)\.WAV「(.+?)」')
        current_id = None
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                id_match = re.search(r'\[(\d+)/1000\]', line)
                if id_match:
                    current_id = int(id_match.group(1))
                ref_match = pattern.search(line)
                if ref_match and current_id:
                    ref_name = ref_match.group(1)
                    ref_text = ref_match.group(2)
                    _ref_cache[current_id] = (ref_name, ref_text)

    # 第二步：从 ref_mapping.txt 覆盖（优先级更高）
    mapping_path = os.path.join(ROOT_DIR, REF_MAPPING_FILE)
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '|' in line:
                    parts = line.split('|', 2)
                    if len(parts) == 3 and parts[0].isdigit():
                        _ref_cache[int(parts[0])] = (parts[1], parts[2])

    return _ref_cache


def update_ref_mapping(corpus_id, ref_name, ref_text):
    """更新单条语料的参考音频映射"""
    global _ref_cache
    if _ref_cache is None:
        load_ref_mapping()
    _ref_cache[corpus_id] = (ref_name, ref_text)
    _save_ref_mapping()


def get_generated_status():
    wav_dir = os.path.join(ROOT_DIR, OUTPUT_DIR)
    if not os.path.exists(wav_dir):
        return set()
    return set(
        int(f.replace('.wav', ''))
        for f in os.listdir(wav_dir)
        if f.endswith('.wav') and f[:-4].isdigit()
    )


# 锁定状态缓存：{ corpus_id: True }
_lock_cache = None

def load_lock_status():
    """从 lock_status.txt 加载锁定状态"""
    global _lock_cache
    if _lock_cache is not None:
        return _lock_cache
    _lock_cache = set()
    path = os.path.join(ROOT_DIR, LOCK_STATUS_FILE)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    _lock_cache.add(int(line))
    return _lock_cache

def save_lock_status():
    """保存锁定状态到文件"""
    global _lock_cache
    path = os.path.join(ROOT_DIR, LOCK_STATUS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for cid in sorted(_lock_cache):
            f.write(f"{cid}\n")

def toggle_lock(corpus_id, locked):
    """切换锁定状态"""
    global _lock_cache
    if _lock_cache is None:
        load_lock_status()
    if locked:
        _lock_cache.add(corpus_id)
    else:
        _lock_cache.discard(corpus_id)
    save_lock_status()


def switch_models():
    global _models_loaded
    if _models_loaded:
        return True
    try:
        resp = requests.get(f"{API_BASE}/set_gpt_weights", params={"weights_path": GPT_MODEL}, timeout=10)
        if resp.status_code != 200:
            return False
        resp = requests.get(f"{API_BASE}/set_sovits_weights", params={"weights_path": SOVITS_MODEL}, timeout=10)
        if resp.status_code != 200:
            return False
        _models_loaded = True
        return True
    except Exception:
        return False


def synthesize(text, ref_path, ref_text, out_path):
    ref_name = os.path.basename(ref_path)
    print(f"    [推理] 文本: {text[:60]}")
    print(f"    [推理] 参考: {ref_name}「{ref_text[:60]}」")
    print(f"    [推理] 路径: {ref_path}")
    print(f"    [推理] 输出: {out_path}")
    data = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref_path,
        "prompt_text": ref_text,
        "prompt_lang": "zh",
        "top_k": TOP_K,
        "top_p": TOP_P,
        "temperature": TEMPERATURE,
        "streaming_mode": False,
        "text_split_method": "cut5",
    }
    resp = requests.post(f"{API_BASE}/tts", json=data, timeout=120)
    if resp.status_code == 200 and len(resp.content) > 1000:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(resp.content)
        print(f"    [推理] 成功，写入 {os.path.getsize(out_path)} bytes")
        return True, None
    print(f"    [推理] 失败 HTTP {resp.status_code}")
    try:
        err = resp.json()
        msg = err.get("Exception", err.get("message", str(err)))
    except:
        msg = resp.text[:200]
    print(f"    [推理] 错误: {msg[:200]}")
    return False, f"HTTP {resp.status_code}: {msg}"


class TTSHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length).decode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/api/corpus':
            corpus = load_corpus()
            generated = get_generated_status()
            ref_map = load_ref_mapping()
            locked = load_lock_status()
            items = []
            for i, text in enumerate(corpus, 1):
                ref_info = ref_map.get(i)
                item = {
                    "id": i,
                    "text": text,
                    "generated": i in generated,
                    "locked": i in locked,
                }
                if ref_info:
                    item["ref_name"] = ref_info[0]
                    item["ref_text"] = ref_info[1]
                items.append(item)
            self._send_json({"corpus": items, "total": len(items)})

        elif path == '/api/refs':
            result = []
            for style, refs in REFS.items():
                for ref_path, ref_text in refs:
                    ref_name = os.path.basename(ref_path).replace('.WAV', '')
                    # http_path: relative path from web root for <audio src>
                    http_path = os.path.relpath(ref_path, ROOT_DIR).replace(os.sep, '/')
                    result.append({
                        "path": http_path,
                        "abs_path": ref_path,
                        "name": ref_name,
                        "text": ref_text,
                        "style": style,
                        "style_label": STYLE_LABELS.get(style, style),
                    })
            self._send_json({"refs": result, "styles": STYLE_LABELS})

        elif path == '/api/status':
            generated = get_generated_status()
            self._send_json({
                "generated_count": len(generated),
                "total": len(load_corpus()),
            })

        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/regenerate':
            data = self._read_body()
            corpus_id = data.get('id')
            ref_name = data.get('ref')

            print(f"\n===== 重新生成 [单条] =====")
            print(f"  请求参数: id={corpus_id}, ref={ref_name}")

            if not corpus_id or not ref_name:
                self._send_json({"error": "缺少 id 或 ref"}, 400)
                return

            corpus = load_corpus()
            if corpus_id < 1 or corpus_id > len(corpus):
                self._send_json({"error": f"编号 {corpus_id} 超出范围"}, 400)
                return

            # 检查锁定状态
            locked = load_lock_status()
            if corpus_id in locked:
                self._send_json({"error": "该条目已锁定，请先解锁再修改"}, 403)
                return

            text = corpus[corpus_id - 1]
            print(f"  语料文本: {text[:60]}")

            # 查找参考音频
            ref_path = None
            ref_text = None
            found_style = None
            for style_name, style_refs in REFS.items():
                for rp, rt in style_refs:
                    if os.path.basename(rp).replace('.WAV', '') == ref_name.replace('.WAV', ''):
                        ref_path = rp
                        ref_text = rt
                        found_style = style_name
                        break
                if ref_path:
                    break

            if not ref_path:
                print(f"  错误: 找不到参考音频 {ref_name}")
                self._send_json({"error": f"找不到参考音频: {ref_name}"}, 404)
                return

            print(f"  参考音频: {ref_name}.WAV (风格: {found_style})")
            print(f"  绝对路径: {ref_path}")
            print(f"  参考文本: {ref_text[:60]}")

            out_path = os.path.join(ROOT_DIR, OUTPUT_DIR, f"{corpus_id:04d}.wav")
            print(f"  输出文件: {out_path}")

            # 切换模型
            if not switch_models():
                print(f"  错误: 模型切换失败")
                self._send_json({"error": "模型切换失败，请确认 GPT-SoVITS API 正在运行"}, 500)
                return

            time.sleep(1)

            ok, err = synthesize(text, ref_path, ref_text, out_path)
            if ok:
                # 更新参考音频映射数据库
                update_ref_mapping(corpus_id, ref_name, ref_text)
                print(f"  映射已更新: {corpus_id} -> {ref_name}.WAV")
                print(f"  结果: 成功\n")
                self._send_json({"success": True, "id": corpus_id, "ref": ref_name, "ref_text": ref_text})
            else:
                print(f"  结果: 失败 - {err}\n")
                self._send_json({"error": err}, 500)

        elif path == '/api/batch-regenerate':
            data = self._read_body()
            ids = data.get('ids', [])
            ref_name = data.get('ref')

            print(f"\n===== 批量生成: {len(ids)} 条 =====")
            print(f"  参考音频: {ref_name}.WAV")

            if not ids or not ref_name:
                self._send_json({"error": "缺少 ids 或 ref"}, 400)
                return

            # 查找参考音频
            ref_path = None
            ref_text = None
            for style_refs in REFS.values():
                for rp, rt in style_refs:
                    if os.path.basename(rp).replace('.WAV', '') == ref_name.replace('.WAV', ''):
                        ref_path = rp
                        ref_text = rt
                        break
                if ref_path:
                    break

            if not ref_path:
                print(f"  错误: 找不到参考音频 {ref_name}")
                self._send_json({"error": f"找不到参考音频: {ref_name}"}, 404)
                return

            print(f"  绝对路径: {ref_path}")
            print(f"  参考文本: {ref_text[:60]}")

            if not switch_models():
                print(f"  错误: 模型切换失败")
                self._send_json({"error": "模型切换失败"}, 500)
                return

            time.sleep(1)

            corpus = load_corpus()
            locked = load_lock_status()
            results = {"success": [], "failed": [], "skipped_locked": []}

            for cid in ids:
                if cid in locked:
                    results["skipped_locked"].append(cid)
                    continue
                if cid < 1 or cid > len(corpus):
                    results["failed"].append({"id": cid, "error": "超出范围"})
                    continue
                text = corpus[cid - 1]
                out_path = os.path.join(ROOT_DIR, OUTPUT_DIR, f"{cid:04d}.wav")
                print(f"\n  [{cid}] {text[:40]}")
                ok, err = synthesize(text, ref_path, ref_text, out_path)
                if ok:
                    # 更新参考音频映射数据库
                    update_ref_mapping(cid, ref_name, ref_text)
                    results["success"].append(cid)
                    print(f"  [{cid}] 成功 -> 映射已更新: {ref_name}.WAV")
                else:
                    results["failed"].append({"id": cid, "error": err})
                    print(f"  [{cid}] 失败: {err}")
                time.sleep(0.3)

            print(f"\n  批量完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}\n")
            self._send_json(results)

        elif path.startswith('/api/lock/'):
            data = self._read_body()
            try:
                corpus_id = int(path.split('/')[-1])
            except ValueError:
                self._send_json({"error": "无效编号"}, 400)
                return
            locked = data.get('locked', False)
            toggle_lock(corpus_id, locked)
            print(f"\n  [锁定] 第 {corpus_id:04d} 条 {'已锁定' if locked else '已解锁'}")
            self._send_json({"success": True, "id": corpus_id, "locked": locked})

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/wav/'):
            try:
                corpus_id = int(path.split('/')[-1])
            except ValueError:
                self._send_json({"error": "无效编号"}, 400)
                return

            # 检查锁定状态
            locked = load_lock_status()
            if corpus_id in locked:
                self._send_json({"error": "该条目已锁定，请先解锁再删除"}, 403)
                return

            wav_path = os.path.join(ROOT_DIR, OUTPUT_DIR, f"{corpus_id:04d}.wav")
            if os.path.exists(wav_path):
                os.remove(wav_path)
                self._send_json({"success": True, "id": corpus_id})
            else:
                self._send_json({"error": f"文件不存在: {corpus_id:04d}.wav"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)


def main():
    parser = argparse.ArgumentParser(description="TTS 语料挑选工具")
    parser.add_argument("--port", type=int, default=PORT, help=f"端口 (默认 {PORT})")
    parser.add_argument("--api-port", type=int, default=9880, help="GPT-SoVITS API 端口 (默认 9880)")
    args = parser.parse_args()

    global API_BASE
    API_BASE = f"http://localhost:{args.api_port}"

    print(f"🚀 TTS 语料挑选工具")
    print(f"   访问地址: http://localhost:{args.port}")
    print(f"   GPT-SoVITS API: {API_BASE}")
    print()

    server = HTTPServer((HOST, args.port), TTSHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止服务")
        server.shutdown()


if __name__ == "__main__":
    main()
