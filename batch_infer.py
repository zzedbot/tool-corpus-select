"""
GPT-SoVITS 批量推理脚本 — 王也音色知识蒸馏用（串行版）
=================================================
用法：
1. 先启动 API: python api_v2.py --port 9880
2. 再运行此脚本: python batch_infer.py

功能：
- 读取 1000 条语料 (wangye_corpus_1000.txt)
- 智能匹配不同风格的参考音频
- 自动过滤 <3 秒的参考音频
- 批量合成 WAV 音频
- 自动生成 metadata.csv
- 自动生成详细日志文件 (batch_inference.log)

使用前：
- 把此脚本放在 GPT-SoVITS 根目录下
- 确保 wangyevoice/ 文件夹在同一目录
- 确保 wangye_corpus_1000.txt 在同一目录
"""

import requests
import os
import time
import random
import wave
from datetime import datetime

# ===================== 配置区 =====================
API_BASE = "http://localhost:9880"
API_URL = f"{API_BASE}/tts"
OUTPUT_DIR = "distill_output/wav"
TEXT_FILE = "wangye_corpus_1000.txt"
LOG_FILE = "batch_inference.log"

# 参考音频库 — 按风格分类
# 脚本启动时会自动检查音频时长，过滤掉 <3 秒的
REFS_FILE = "raw/refs.txt"

def load_refs():
    """从 raw/refs.txt 加载参考音频配置"""
    refs = {}
    with open(REFS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|', 2)
            if len(parts) != 3:
                continue
            style, num, text = parts
            refs.setdefault(style, []).append((f"wangyevoice/{num}.WAV", text))
    return refs

REFS = load_refs()

# 模型路径
GPT_MODEL = "GPT_weights_v2/wangye-e10.ckpt"
SOVITS_MODEL = "SoVITS_weights_v2/wangye_e8_s1024.pth"

# 推理参数
TEMPERATURE = 0.7
TOP_K = 8
TOP_P = 0.8

# 参考音频最短时长（秒），API 要求 >= 3 秒
MIN_REF_DURATION = 3.0
# ================================================

# 全局统计
_success_count = 0
_fail_count = 0
_skip_count = 0
_log_handle = None
_total = 0


def get_timestamp():
    """获取当前时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_print(msg=""):
    """同时输出到控制台和日志文件"""
    print(msg)
    if _log_handle is not None:
        _log_handle.write(msg + "\n")
        _log_handle.flush()


def open_log():
    """打开日志文件"""
    global _log_handle
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, LOG_FILE)
    _log_handle = open(log_path, 'w', encoding='utf-8')
    return log_path


def close_log():
    """关闭日志文件"""
    global _log_handle
    if _log_handle is not None:
        _log_handle.close()
        _log_handle = None


def get_wav_duration(filepath):
    """获取 WAV 文件时长（秒）"""
    try:
        with wave.open(filepath, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate
    except Exception as e:
        print(f"  ⚠️ 无法读取 {filepath}: {e}")
        return 0


def filter_refs_by_duration():
    """检查所有参考音频时长，过滤掉 < MIN_REF_DURATION 秒的"""
    global REFS

    print("🔍 检查参考音频时长...")
    total_before = sum(len(v) for v in REFS.values())
    filtered_out = []

    for style_name in REFS:
        valid_refs = []
        for ref_path, ref_text in REFS[style_name]:
            if os.path.exists(ref_path):
                duration = get_wav_duration(ref_path)
                if duration >= MIN_REF_DURATION:
                    valid_refs.append((ref_path, ref_text))
                else:
                    filtered_out.append((style_name, ref_path, duration))
            else:
                print(f"  ⚠️ 文件不存在: {ref_path}")
                filtered_out.append((style_name, ref_path, -1))
        REFS[style_name] = valid_refs

    total_after = sum(len(v) for v in REFS.values())

    if filtered_out:
        print(f"\n🚫 过滤掉 {len(filtered_out)} 条 <{MIN_REF_DURATION}s 的参考音频:")
        for style, path, dur in filtered_out:
            dur_str = f"{dur:.1f}s" if dur >= 0 else "文件不存在"
            print(f"   ❌ {path} ({dur_str}) [{style}]")
            print()

    print(f"📊 参考音频: {total_before} → {total_after} 条 (过滤 {total_before - total_after} 条)")

    empty_styles = [name for name, refs in REFS.items() if len(refs) == 0]
    if empty_styles:
        print(f"\n⚠️ 以下风格类别已全部被过滤: {', '.join(empty_styles)}")
        return False

    return True


def switch_models():
    """切换到王也训练好的模型"""
    print(f"\n🔄 切换到 GPT 模型: {GPT_MODEL}")
    resp = requests.get(f"{API_BASE}/set_gpt_weights", params={"weights_path": GPT_MODEL})
    if resp.status_code == 200:
        print("✅ GPT 模型加载成功")
    else:
        print(f"❌ GPT 模型加载失败: {resp.status_code} {resp.text}")
        return False

    print(f"🔄 切换到 SoVITS 模型: {SOVITS_MODEL}")
    resp = requests.get(f"{API_BASE}/set_sovits_weights", params={"weights_path": SOVITS_MODEL})
    if resp.status_code == 200:
        print("✅ SoVITS 模型加载成功")
    else:
        print(f"❌ SoVITS 模型加载失败: {resp.status_code} {resp.text}")
        return False

    return True


def get_ref_for_text(text):
    """根据文本内容自动选择最合适的参考音频风格"""
    text_len = len(text)
    candidates = []

    if '？' in text or '?' in text or text.endswith('吗') or text.endswith('呢') or text.endswith('？'):
        candidates.append("question")
    if text_len > 25:
        candidates.append("serious")
    if text_len < 8:
        candidates.append("casual")
    candidates.append("lazy")

    for style in candidates:
        if REFS.get(style):
            return random.choice(REFS[style])

    for style, refs in REFS.items():
        if refs:
            return random.choice(refs)

    return None, None


def main():
    global _total, _success_count, _fail_count, _skip_count

    # 打开日志
    log_path = open_log()
    safe_print(f"📝 日志文件: {log_path}")
    safe_print(f"{'='*60}")
    safe_print(f"  GPT-SoVITS 批量推理 — 王也音色知识蒸馏")
    safe_print(f"  开始时间: {get_timestamp()}")
    safe_print(f"{'='*60}")
    safe_print()

    # 1. 过滤短音频
    if not filter_refs_by_duration():
        safe_print("❌ 有效参考音频不足，退出")
        close_log()
        return

    # 2. 切换模型
    if not switch_models():
        safe_print("❌ 模型切换失败，退出")
        close_log()
        return

    # 3. 等待模型加载
    safe_print("⏳ 等待模型加载...")
    time.sleep(3)

    # 4. 测试推理
    safe_print("🧪 测试推理...")
    for style, refs in REFS.items():
        if refs:
            test_ref, test_text = refs[0]
            break
    else:
        safe_print("❌ 没有有效的参考音频")
        close_log()
        return

    test_data = {
        "text": "你好，我是王也。",
        "text_lang": "zh",
        "ref_audio_path": test_ref,
        "prompt_text": test_text,
        "prompt_lang": "zh",
        "streaming_mode": False,
    }
    resp = requests.post(API_URL, json=test_data, timeout=30)
    if resp.status_code == 200:
        safe_print("✅ 测试成功\n")
    else:
        safe_print(f"❌ 测试失败: HTTP {resp.status_code}")
        try:
            err = resp.json()
            safe_print(f"   错误: {err}")
        except:
            safe_print(f"   错误: {resp.text[:200]}")
        close_log()
        return

    # 5. 读取语料
    with open(TEXT_FILE, 'r', encoding='utf-8') as f:
        texts = [line.strip() for line in f if line.strip()]

    _total = len(texts)
    safe_print(f"📋 待合成: {_total} 条")
    safe_print(f"🎤 可用参考: {sum(len(v) for v in REFS.values())} 条 ({len(REFS)} 种风格)")
    safe_print(f"\n{'='*60}")
    safe_print(f"  开始批量合成")
    safe_print(f"{'='*60}\n")

    style_emoji = {
        "lazy": "😮‍💨",
        "serious": "📜",
        "casual": "💬",
        "question": "❓",
        "strong": "⚡"
    }

    metadata_lines = []

    # 6. 串行批量合成
    for i, text in enumerate(texts, 1):
        out_path = os.path.join(OUTPUT_DIR, f"{i:04d}.wav")
        ts = get_timestamp()

        # 跳过已合成的
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            _skip_count += 1
            safe_print(f"[{ts}] ⏭️  [{i}/{_total}] 已存在，跳过: {text[:30]}")
            metadata_lines.append(f"{i:04d}|{text}")
            continue

        # 选择参考音频
        ref_path, ref_text = get_ref_for_text(text)
        if ref_path is None:
            _fail_count += 1
            safe_print(f"[{ts}] ❌ [{i}/{_total}] 没有可用参考音频 | {text[:30]}")
            continue

        # API 请求
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

        try:
            resp = requests.post(API_URL, json=data, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(out_path, 'wb') as f:
                    f.write(resp.content)

                _success_count += 1
                metadata_lines.append(f"{i:04d}|{text}")

                # 风格标签
                style_tag = ""
                for style_name, style_refs in REFS.items():
                    if (ref_path, ref_text) in style_refs:
                        style_tag = f" [{style_emoji.get(style_name, '')}{style_name}]"
                        break
                ref_name = os.path.splitext(os.path.basename(ref_path))[0]
                safe_print(f"[{ts}] ✅ [{i}/{_total}] {text[:30]}...{style_tag}")
                safe_print(f"         ↳ 参考:{ref_name}.WAV「{ref_text[:30]}」")
            else:
                _fail_count += 1
                try:
                    err = resp.json()
                    err_msg = err.get("Exception", err.get("message", str(err)))
                except:
                    err_msg = resp.text[:100]
                safe_print(f"[{ts}] ❌ [{i}/{_total}] HTTP {resp.status_code}: {err_msg} | {text[:30]}")
        except Exception as e:
            _fail_count += 1
            safe_print(f"[{ts}] ❌ [{i}/{_total}] 错误: {e} | {text[:30]}")

        # 控制节奏
        time.sleep(0.3)

    # 7. 保存 metadata
    with open(os.path.join(OUTPUT_DIR, "metadata.csv"), 'w', encoding='utf-8') as f:
        for line in metadata_lines:
            f.write(line + '\n')

    # 8. 最终统计
    safe_print(f"\n{'='*60}")
    safe_print(f"  批量合成完成！")
    safe_print(f"{'='*60}")
    safe_print(f"  ✅ 成功: {_success_count} 条")
    safe_print(f"  ❌ 失败: {_fail_count} 条")
    safe_print(f"  ⏭️  跳过: {_skip_count} 条")
    safe_print(f"  📁 输出目录: {OUTPUT_DIR}/")
    safe_print(f"  📄 metadata: {OUTPUT_DIR}/metadata.csv")
    safe_print(f"  📝 日志文件: {log_path}")
    safe_print(f"  ⏰ 结束时间: {get_timestamp()}")
    safe_print(f"{'='*60}")

    close_log()


if __name__ == "__main__":
    main()
