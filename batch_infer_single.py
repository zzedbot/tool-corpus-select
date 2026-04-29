"""
GPT-SoVITS 单条推理脚本 — 配合网页端使用
用法：
    python batch_infer_single.py --id 123 --ref 100.WAV [--port 9880]
    python batch_infer_single.py --text "你好世界" --ref 100.WAV
"""

import argparse
import requests
import os
import sys

API_BASE = "http://localhost:{port}"
OUTPUT_DIR = "wav"
TEXT_FILE = "wangye_corpus_1000.txt"

# 模型路径
GPT_MODEL = "GPT_weights_v2/wangye-e10.ckpt"
SOVITS_MODEL = "SoVITS_weights_v2/wangye_e8_s1024.pth"

# 推理参数
TEMPERATURE = 0.7
TOP_K = 8
TOP_P = 0.8


def load_corpus():
    with open(TEXT_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def get_ref_info(ref_name, refs_dict):
    """从风格分类中查找参考音频的 prompt text"""
    for style, refs in refs_dict.items():
        for path, text in refs:
            if os.path.basename(path).upper() == ref_name.upper():
                return path, text
    # 如果不在风格分类中，从 wangye.list 查找
    list_path = os.path.join("raw", "wangye.list")
    if os.path.exists(list_path):
        with open(list_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 4 and os.path.basename(parts[0]).upper() == ref_name.upper():
                    return parts[0], parts[3]
    # 兜底：文件存在但无文本
    path = os.path.join("raw", "wangyevoice", ref_name)
    if os.path.exists(path):
        return path, ""
    return None, None


def switch_models(port):
    api = API_BASE.format(port=port)
    resp = requests.get(f"{api}/set_gpt_weights", params={"weights_path": GPT_MODEL})
    if resp.status_code != 200:
        print(f"GPT 模型加载失败: {resp.status_code}")
        return False
    resp = requests.get(f"{api}/set_sovits_weights", params={"weights_path": SOVITS_MODEL})
    if resp.status_code != 200:
        print(f"SoVITS 模型加载失败: {resp.status_code}")
        return False
    return True


def synthesize(text, ref_path, ref_text, out_path, port):
    api = API_BASE.format(port=port)
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
    resp = requests.post(f"{api}/tts", json=data, timeout=60)
    if resp.status_code == 200 and len(resp.content) > 1000:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(resp.content)
        return True, None
    else:
        try:
            err = resp.json()
            msg = err.get("Exception", err.get("message", str(err)))
        except:
            msg = resp.text[:200]
        return False, f"HTTP {resp.status_code}: {msg}"


def main():
    parser = argparse.ArgumentParser(description="GPT-SoVITS 单条推理")
    parser.add_argument("--id", type=int, help="语料编号 (1-1000)")
    parser.add_argument("--text", type=str, help="直接指定文本")
    parser.add_argument("--ref", type=str, required=True, help="参考音频文件名 (如 100.WAV)")
    parser.add_argument("--port", type=int, default=9880, help="API 端口 (默认 9880)")
    args = parser.parse_args()

    if not args.id and not args.text:
        parser.error("需要指定 --id 或 --text")

    # 获取文本
    if args.text:
        text = args.text
    else:
        corpus = load_corpus()
        if args.id < 1 or args.id > len(corpus):
            print(f"编号 {args.id} 超出范围 (1-{len(corpus)})")
            sys.exit(1)
        text = corpus[args.id - 1]

    # 获取参考音频
    ref_path, ref_text = get_ref_info(args.ref, {})
    if ref_path is None:
        print(f"找不到参考音频: {args.ref}")
        sys.exit(1)

    # 输出路径
    if args.id:
        out_path = os.path.join(OUTPUT_DIR, f"{args.id:04d}.wav")
    else:
        out_path = os.path.join(OUTPUT_DIR, f"custom_{args.ref.replace('.', '_')}.wav")

    print(f"合成: {text[:50]}")
    print(f"参考: {ref_path} 「{ref_text[:50]}」")
    print(f"输出: {out_path}")

    # 切换模型
    if not switch_models(args.port):
        print("模型切换失败")
        sys.exit(1)

    import time
    time.sleep(2)

    # 推理
    ok, err = synthesize(text, ref_path, ref_text, out_path, args.port)
    if ok:
        print(f"成功 -> {out_path}")
    else:
        print(f"失败: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
