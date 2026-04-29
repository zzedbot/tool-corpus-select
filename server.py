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

# 模型路径
GPT_MODEL = "GPT_weights_v2/wangye-e10.ckpt"
SOVITS_MODEL = "SoVITS_weights_v2/wangye_e8_s1024.pth"

# 推理参数
TEMPERATURE = 0.7
TOP_K = 8
TOP_P = 0.8

# 参考音频风格分类 (与 batch_infer.py 一致)
REFS = {
    "lazy": [
        ("raw/wangyevoice/11.WAV", "差不多了吧，老铁。"),
        ("raw/wangyevoice/12.WAV", "哎，真是个会玩的姑娘啊。"),
        ("raw/wangyevoice/19.WAV", "哎，就说没那么容易嘛。"),
        ("raw/wangyevoice/35.WAV", "啊，算了，本就不该来。"),
        ("raw/wangyevoice/60.WAV", "哎，妹子，让我长了不少姿势。"),
        ("raw/wangyevoice/100.WAV", "哎，我是一口都吃不下了，怎么样？张楚兰，能选了吗？"),
        ("raw/wangyevoice/109.WAV", "什么人呐？还以为能给我送机票呢。"),
        ("raw/wangyevoice/118.WAV", "嘿嘿，那是那是，老天师，我也不想没事给自己找事儿。"),
        ("raw/wangyevoice/108.WAV", "你这货居，然用听风萦偷听。"),
        ("raw/wangyevoice/129.WAV", "还是这么狗血呀，这个家"),
    ],
    "serious": [
        ("raw/wangyevoice/70.WAV", "过去无可挽回，未来可以改变。"),
        ("raw/wangyevoice/26.WAV", "既然大家都是术士，就没必要像其他人斗得那么辛苦了。"),
        ("raw/wangyevoice/28.WAV", "术士就要顺势而为，诸葛卿，我没有半点侮辱你的意思。"),
        ("raw/wangyevoice/40.WAV", "身在这个奇门局中，我即是方位，我即是吉凶。"),
        ("raw/wangyevoice/55.WAV", "反正不管懂不懂那规则，你我都和一般人一样被束缚着，不是吗。"),
        ("raw/wangyevoice/87.WAV", "真常应物，真常得性，常应常静，常清静矣"),
        ("raw/wangyevoice/90.WAV", "这就牵扯到另一个概念了，我管它叫，命运的权重。"),
        ("raw/wangyevoice/91.WAV", "这个世界没有一刻是静止的，个体变化的总和，就是整个世界的变化。"),
        ("raw/wangyevoice/93.WAV", "有人殚精竭虑，却掀不起风浪。有人一念之差，却让世界天翻地覆。"),
        ("raw/wangyevoice/86.WAV", "我说的是一直求而不得，一旦得到，要为了他舍弃一切的东西，那，才配称为最想要。"),
    ],
    "casual": [
        ("raw/wangyevoice/2.WAV", "武当派，王也，施主您怎么称呼？"),
        ("raw/wangyevoice/34.WAV", "这就对了嘛。"),
        ("raw/wangyevoice/64.WAV", "没事儿，就这么比吧。"),
        ("raw/wangyevoice/65.WAV", "是比呀，这罗天大教也没规定非得比打架呀。"),
        ("raw/wangyevoice/66.WAV", "咱们都是道士，又不是战士，我跟这货比谁能吃，不行吗？"),
        ("raw/wangyevoice/107.WAV", "小白，回去记得多练练胆儿啊。"),
        ("raw/wangyevoice/134.WAV", "杜哥，你联络一下金媛媛他们呗。"),
        ("raw/wangyevoice/127.WAV", "六味地黄，枸杞，海马肝，袋鼠精。"),
        ("raw/wangyevoice/13.WAV", "好歹是揉上了。"),
        ("raw/wangyevoice/18.WAV", "昆仑。"),
    ],
    "question": [
        ("raw/wangyevoice/24.WAV", "诸葛卿，你败过吗？"),
        ("raw/wangyevoice/25.WAV", "那你觉得你能接受自己失败吗？"),
        ("raw/wangyevoice/31.WAV", "诸葛卿，你觉得怎么样？"),
        ("raw/wangyevoice/68.WAV", "张楚岚，知道占卜是怎么一回事吗？"),
        ("raw/wangyevoice/106.WAV", "你们兄弟准备回去了吗？"),
        ("raw/wangyevoice/122.WAV", "我不是已经被武当除名了吗"),
        ("raw/wangyevoice/124.WAV", "杜哥，趁着不堵车，能不能再开快点儿？"),
        ("raw/wangyevoice/130.WAV", "不好说啊，杜哥说正事，怎么样？"),
        ("raw/wangyevoice/10.WAV", "确实有两把刷子，你老爹把你调教的不错。"),
        ("raw/wangyevoice/39.WAV", "懂了吗？和其他术士踏方位巡吉凶不同。"),
    ],
    "strong": [
        ("raw/wangyevoice/5.WAV", "老天师，武当王也，拜见老天师。"),
        ("raw/wangyevoice/15.WAV", "阴手，逮到你了。"),
        ("raw/wangyevoice/115.WAV", "老天师，千万别，别说做，想都别想。"),
        ("raw/wangyevoice/117.WAV", "您这一劫应在诸葛清的身上了，他的麻烦，我会处理。"),
        ("raw/wangyevoice/120.WAV", "成吧，那就得罪了。"),
        ("raw/wangyevoice/133.WAV", "一般人身手再好也不管用，一定得是圈儿里人，啊，没想到我也有为钱发愁的一天呐。"),
        ("raw/wangyevoice/136.WAV", "咱们也被人盯上了，盯哨的人就在附近。"),
        ("raw/wangyevoice/29.WAV", "这话我只说一次，回去吧，诸葛卿，这对你来说是最好的结果。"),
        ("raw/wangyevoice/131.WAV", "别打听，而且什么细节都别问。"),
        ("raw/wangyevoice/132.WAV", "这样你还愿意帮我吗？雇俩圈里人，暗中照看每个家庭成员，但是不能让他们知道。"),
    ],
}

STYLE_LABELS = {
    "lazy": "😮‍💨 慵懒/日常",
    "serious": "📜 沉稳/长篇",
    "casual": "💬 对话/轻松",
    "question": "❓ 疑问/反问",
    "strong": "⚡ 严肃/气势",
}

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
            items = []
            for i, text in enumerate(corpus, 1):
                ref_info = ref_map.get(i)
                item = {
                    "id": i,
                    "text": text,
                    "generated": i in generated,
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
            results = {"success": [], "failed": []}

            for cid in ids:
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
