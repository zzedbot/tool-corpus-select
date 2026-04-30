#!/usr/bin/env python3
"""
DNMOS 批量评分脚本
用法：
    python dnsmos_score.py                  # 对所有 WAV 评分
    python dnsmos_score.py --skip-scored    # 跳过已有评分（增量）
    python dnsmos_score.py --id 123         # 仅对指定编号评分
    python dnsmos_score.py --model utmos22_strong
"""
import torch
import torchaudio
import os
import argparse

WAV_DIR = "wav"
SCORE_FILE = "wav/dnsmos_scores.txt"

predictor = None


def load_existing_scores():
    scores = {}
    if os.path.exists(SCORE_FILE):
        with open(SCORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 2:
                    try:
                        scores[int(parts[0])] = float(parts[1])
                    except ValueError:
                        pass
    return scores


def save_scores(scores):
    os.makedirs(os.path.dirname(SCORE_FILE) or ".", exist_ok=True)
    with open(SCORE_FILE, 'w', encoding='utf-8') as f:
        for cid in sorted(scores.keys()):
            f.write(f"{cid:04d}|{scores[cid]:.2f}\n")


def get_predictor(model_name):
    global predictor
    if predictor is None:
        predictor = torch.hub.load(
            "tarepan/SpeechMOS:v1.2.0",
            model_name,
            trust_repo=True,
            verbose=False,
        )
    return predictor


def score_file(path, model_name="utmos22_strong"):
    """对单个 WAV 文件打分"""
    p = get_predictor(model_name)
    waveform, sr = torchaudio.load(path)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sr != 16000:
        waveform = torchaudio.functional.resample(waveform, sr, 16000)
    return p(waveform, sr=16000).item()


def main():
    parser = argparse.ArgumentParser(description="DNMOS 批量评分")
    parser.add_argument("--model", default="utmos22_strong", help="MOS 模型名称")
    parser.add_argument("--skip-scored", action="store_true", help="跳过已有评分的条目（增量模式）")
    parser.add_argument("--id", type=int, help="仅对指定编号的单条音频评分")
    args = parser.parse_args()

    scores = load_existing_scores()

    if args.id is not None:
        # 单条评分模式
        fname = f"{args.id:04d}.wav"
        path = os.path.join(WAV_DIR, fname)
        if not os.path.exists(path):
            print(f"文件不存在: {path}")
            return
        score = score_file(path, args.model)
        scores[args.id] = score
        save_scores(scores)
        print(f"{fname} → {score:.2f}")
        return

    # 批量评分模式
    if not os.path.exists(WAV_DIR):
        print(f"WAV 目录不存在: {WAV_DIR}")
        return

    wav_files = sorted(
        f for f in os.listdir(WAV_DIR)
        if f.endswith('.wav') and f[:-4].isdigit()
    )

    to_score = []
    for fname in wav_files:
        cid = int(fname[:-4])
        if args.skip_scored and cid in scores:
            continue
        to_score.append((cid, fname))

    if not to_score:
        print("所有音频已有评分，无需重复。")
        return

    print(f"开始评分 {len(to_score)} 条音频...")
    for i, (cid, fname) in enumerate(to_score, 1):
        path = os.path.join(WAV_DIR, fname)
        try:
            score = score_file(path, args.model)
            scores[cid] = score
            print(f"[{i}/{len(to_score)}] {fname} → {score:.2f}")
        except Exception as e:
            print(f"[{i}/{len(to_score)}] {fname} → 评分失败: {e}")
        if i % 10 == 0:
            save_scores(scores)

    save_scores(scores)
    print(f"\n评分完成！共 {len(scores)} 条，结果保存在 {SCORE_FILE}")


if __name__ == "__main__":
    main()
