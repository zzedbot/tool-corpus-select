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
REFS = {
    # 😮‍💨 慵懒/叹气/日常 (王也的招牌风格)
    "lazy": [
        ("wangyevoice/11.WAV", "差不多了吧，老铁。"),
        ("wangyevoice/12.WAV", "哎，真是个会玩的姑娘啊。"),
        ("wangyevoice/19.WAV", "哎，就说没那么容易嘛。"),
        ("wangyevoice/35.WAV", "啊，算了，本就不该来。"),
        ("wangyevoice/60.WAV", "哎，妹子，让我长了不少姿势。"),
        ("wangyevoice/100.WAV", "哎，我是一口都吃不下了，怎么样？张楚兰，能选了吗？"),
        ("wangyevoice/109.WAV", "什么人呐？还以为能给我送机票呢。"),
        ("wangyevoice/118.WAV", "嘿嘿，那是那是，老天师，我也不想没事给自己找事儿。"),
        ("wangyevoice/108.WAV", "你这货居，然用听风萦偷听。"),
        ("wangyevoice/129.WAV", "还是这么狗血呀，这个家"),
    ],
    # 📜 沉稳/论述/长篇 (适合正式内容、成语诗词)
    "serious": [
        ("wangyevoice/70.WAV", "过去无可挽回，未来可以改变。"),
        ("wangyevoice/26.WAV", "既然大家都是术士，就没必要像其他人斗得那么辛苦了。"),
        ("wangyevoice/28.WAV", "术士就要顺势而为，诸葛卿，我没有半点侮辱你的意思。"),
        ("wangyevoice/40.WAV", "身在这个奇门局中，我即是方位，我即是吉凶。"),
        ("wangyevoice/55.WAV", "反正不管懂不懂那规则，你我都和一般人一样被束缚着，不是吗。"),
        ("wangyevoice/87.WAV", "真常应物，真常得性，常应常静，常清静矣"),
        ("wangyevoice/90.WAV", "这就牵扯到另一个概念了，我管它叫，命运的权重。"),
        ("wangyevoice/91.WAV", "这个世界没有一刻是静止的，个体变化的总和，就是整个世界的变化。"),
        ("wangyevoice/93.WAV", "有人殚精竭虑，却掀不起风浪。有人一念之差，却让世界天翻地覆。"),
        ("wangyevoice/86.WAV", "我说的是一直求而不得，一旦得到，要为了他舍弃一切的东西，那，才配称为最想要。"),
    ],
    # 💬 对话/轻松/短句 (适合日常对话、短句)
    "casual": [
        ("wangyevoice/2.WAV", "武当派，王也，施主您怎么称呼？"),
        ("wangyevoice/34.WAV", "这就对了嘛。"),
        ("wangyevoice/64.WAV", "没事儿，就这么比吧。"),
        ("wangyevoice/65.WAV", "是比呀，这罗天大教也没规定非得比打架呀。"),
        ("wangyevoice/66.WAV", "咱们都是道士，又不是战士，我跟这货比谁能吃，不行吗？"),
        ("wangyevoice/107.WAV", "小白，回去记得多练练胆儿啊。"),
        ("wangyevoice/134.WAV", "杜哥，你联络一下金媛媛他们呗。"),
        ("wangyevoice/127.WAV", "六味地黄，枸杞，海马肝，袋鼠精。"),
        ("wangyevoice/13.WAV", "好歹是揉上了。"),
        ("wangyevoice/18.WAV", "昆仑。"),
    ],
    # ❓ 疑问/反问 (适合带问号的句子)
    "question": [
        ("wangyevoice/24.WAV", "诸葛卿，你败过吗？"),
        ("wangyevoice/25.WAV", "那你觉得你能接受自己失败吗？"),
        ("wangyevoice/31.WAV", "诸葛卿，你觉得怎么样？"),
        ("wangyevoice/68.WAV", "张楚岚，知道占卜是怎么一回事吗？"),
        ("wangyevoice/106.WAV", "你们兄弟准备回去了吗？"),
        ("wangyevoice/122.WAV", "我不是已经被武当除名了吗"),
        ("wangyevoice/124.WAV", "杜哥，趁着不堵车，能不能再开快点儿？"),
        ("wangyevoice/130.WAV", "不好说啊，杜哥说正事，怎么样？"),
        ("wangyevoice/10.WAV", "确实有两把刷子，你老爹把你调教的不错。"),
        ("wangyevoice/39.WAV", "懂了吗？和其他术士踏方位巡吉凶不同。"),
    ],
    # ⚡ 严肃/告诫/气势 (适合绕口令、重要宣言)
    "strong": [
        ("wangyevoice/5.WAV", "老天师，武当王也，拜见老天师。"),
        ("wangyevoice/15.WAV", "阴手，逮到你了。"),
        ("wangyevoice/115.WAV", "老天师，千万别，别说做，想都别想。"),
        ("wangyevoice/117.WAV", "您这一劫应在诸葛清的身上了，他的麻烦，我会处理。"),
        ("wangyevoice/120.WAV", "成吧，那就得罪了。"),
        ("wangyevoice/133.WAV", "一般人身手再好也不管用，一定得是圈儿里人，啊，没想到我也有为钱发愁的一天呐。"),
        ("wangyevoice/136.WAV", "咱们也被人盯上了，盯哨的人就在附近。"),
        ("wangyevoice/29.WAV", "这话我只说一次，回去吧，诸葛卿，这对你来说是最好的结果。"),
        ("wangyevoice/131.WAV", "别打听，而且什么细节都别问。"),
        ("wangyevoice/132.WAV", "这样你还愿意帮我吗？雇俩圈里人，暗中照看每个家庭成员，但是不能让他们知道。"),
    ],
}

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
