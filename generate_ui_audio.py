#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI効果音・メニュー音声を AWS Polly で一括生成するスクリプト。
まっさらな環境で audio/ ディレクトリ内の音声ファイルを復元するために使用。

使い方:
  1. .env に AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY を設定
  2. python3 generate_ui_audio.py
"""

import os
import sys
import struct
import boto3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = PROJECT_DIR / "audio"

# Polly設定
REGION = "ap-northeast-1"
VOICE = "Takumi"
ENGINE = "neural"
SAMPLE_RATE = "16000"


def text_to_speech_polly(text, text_type="text"):
    """Amazon PollyでテキストをPCM音声に変換"""
    polly = boto3.client("polly", region_name=REGION)
    response = polly.synthesize_speech(
        Text=text,
        VoiceId=VOICE,
        Engine=ENGINE,
        OutputFormat="pcm",
        SampleRate=SAMPLE_RATE,
        TextType=text_type,
    )
    if "AudioStream" not in response:
        raise RuntimeError("Polly response has no AudioStream")
    return response["AudioStream"].read()


def mono_to_stereo_pcm(mono_pcm, volume_scale=1.0):
    """モノラルPCMをステレオに変換"""
    stereo_data = bytearray()
    for i in range(0, len(mono_pcm), 2):
        sample_val = struct.unpack("<h", mono_pcm[i : i + 2])[0]
        if volume_scale != 1.0:
            sample_val = int(sample_val * volume_scale)
            if sample_val > 32767:
                sample_val = 32767
            elif sample_val < -32768:
                sample_val = -32768
        sample = struct.pack("<h", sample_val)
        stereo_data.extend(sample)
        stereo_data.extend(sample)
    return bytes(stereo_data)


def make_wav_from_pcm(pcm_bytes, sample_rate=16000, channels=2):
    """PCM -> WAV変換"""
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = len(pcm_bytes)

    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)
    header += struct.pack("<H", 1)
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", block_align)
    header += struct.pack("<H", 16)
    header += b"data"
    header += struct.pack("<I", data_size)
    return header + pcm_bytes


def generate_wav(text, filepath, text_type="text", volume_scale=1.0):
    """テキストからWAVファイルを生成"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.exists():
        print(f"  スキップ（既存）: {filepath.name}")
        return

    print(f"  生成中: {filepath.name} ← 「{text}」")
    pcm = text_to_speech_polly(text, text_type=text_type)
    wav = make_wav_from_pcm(mono_to_stereo_pcm(pcm, volume_scale=volume_scale))
    with open(filepath, "wb") as f:
        f.write(wav)
    print(f"  ✓ 完了: {filepath.name}")


def main():
    print("=" * 50)
    print("UI音声ファイル生成スクリプト")
    print("=" * 50)

    # メニュー項目の音声（menu_0〜menu_4）
    menu_items = [
        "ブログファンからメッセージ",
        "むかしむかし",
        "ブログ投稿",
        "LINEする",
        "鳥のさえずり",
    ]

    print("\n--- メニュー項目 ---")
    for i, item in enumerate(menu_items):
        generate_wav(item, AUDIO_DIR / f"menu_{i}.wav")

    # UI効果音
    ui_sounds = {
        "kettei.wav": "決定",
        "modoru.wav": "戻ります",
        "beep.wav": "ピッ",
        "saisei.wav": "再生します",
        "reboot.wav": "再起動します",
        "modorimasu.wav": "戻ります",
        "recording_start.wav": "録音を開始します",
        "message_loading.wav": "メッセージを読み込んでいます",
        "preparing_audio.wav": "音声を準備しています",
    }

    print("\n--- UI効果音 ---")
    for filename, text in ui_sounds.items():
        generate_wav(text, AUDIO_DIR / filename)

    # ブログ投稿関連
    blog_sounds = {
        "blog_ready.wav": "ブログ投稿の準備ができました。決定ボタンで録音を開始します",
        "blog_record_start.wav": "録音を開始します。お話しください",
        "blog_confirm.wav": "録音が完了しました。決定ボタンで投稿、戻るボタンでキャンセルです",
        "blog_posted.wav": "ブログに投稿しました",
        "blog_cancel.wav": "投稿をキャンセルしました",
        "blog_timeout.wav": "タイムアウトしました。キャンセルします",
    }

    print("\n--- ブログ投稿音声 ---")
    for filename, text in blog_sounds.items():
        generate_wav(text, AUDIO_DIR / filename)

    # 通知音声
    notification_sounds = {
        "fan_message_arrival.wav": "新しいブログファンメッセージがあります",
        "fan_message_reminder.wav": "まだ聞いていないメッセージがあります",
    }

    print("\n--- 通知音声 ---")
    for filename, text in notification_sounds.items():
        generate_wav(text, AUDIO_DIR / filename)

    # 方角音声（SSMLで音量アップ）
    direction_sounds = {
        "north.wav": ("北、ひとつ進んでください。", 4.0),
        "east.wav": ("東、右に曲がってください。", 4.0),
        "south.wav": ("南、ひとつもどしてください。", 4.0),
        "west.wav": ("西、ひとつもどしてください。", 4.0),
    }

    direction_dir = AUDIO_DIR / "direction"
    print("\n--- 方角音声 ---")
    for filename, (text, boost) in direction_sounds.items():
        ssml_text = f"<speak><prosody volume='+10dB'>{text}</prosody></speak>"
        generate_wav(ssml_text, direction_dir / filename, text_type="ssml", volume_scale=boost)

    print("\n" + "=" * 50)
    print("生成完了！")
    print(f"出力先: {AUDIO_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
