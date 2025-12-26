#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファンメッセージ音声生成バッチ
1日2回cronで実行して、新しいメッセージの音声を事前生成
"""

import json
import os
import hashlib
from pathlib import Path
from fan_messages import get_fan_messages, text_to_speech_polly
import struct

# Google Apps Script API URL
MESSAGES_API_URL = "https://script.google.com/macros/s/AKfycbwfFiNLr4OAI1aqcn6wdDk_Y9tlTRCxOVNzYkf3XJUqpoeG8GJj9qRJqBWNY1wPZ0uKpg/exec"


# ディレクトリ設定
CACHE_DIR = Path("/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages")
NAMES_DIR = CACHE_DIR / "names"
MESSAGES_DIR = CACHE_DIR / "messages"
JSON_FILE = CACHE_DIR / "messages.json"

# ディレクトリ作成
NAMES_DIR.mkdir(parents=True, exist_ok=True)
MESSAGES_DIR.mkdir(parents=True, exist_ok=True)

def mono_to_stereo_pcm(mono_pcm: bytes) -> bytes:
    """モノラルPCMをステレオに変換"""
    stereo_data = bytearray()
    for i in range(0, len(mono_pcm), 2):
        sample = mono_pcm[i:i+2]
        stereo_data.extend(sample)
        stereo_data.extend(sample)
    return bytes(stereo_data)

def make_wav_from_pcm(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 2) -> bytes:
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

def generate_audio(text: str, output_path: Path):
    """テキストから音声ファイル生成"""
    print(f"  生成中: {output_path.name}")
    
    # Polly PCM生成
    pcm_mono = text_to_speech_polly(text)
    
    # ステレオ変換
    pcm_stereo = mono_to_stereo_pcm(pcm_mono)
    
    # WAV変換
    wav_data = make_wav_from_pcm(pcm_stereo)
    
    # ファイル保存
    with open(output_path, 'wb') as f:
        f.write(wav_data)
    
    print(f"  ✓ 完了: {output_path.name}")

def main():
    print("=" * 60)
    print("ファンメッセージ音声生成バッチ")
    print("=" * 60)



    # 1. メッセージ取得（バッチ実行時は常にAPIから取得）
    print("\n📥 メッセージを取得中...")
    import requests
    try:
        response = requests.get(MESSAGES_API_URL, timeout=10)
        response.raise_for_status()
        new_messages = response.json()
        print(f"✓ APIから{len(new_messages)}件取得\n")
    except Exception as e:
        print(f"⚠️ メッセージ取得エラー: {e}")
        return

    
    # 2. 既存メッセージ読み込み
    if JSON_FILE.exists():
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            old_messages = json.load(f)
    else:
        old_messages = []
    
    # 3. 新しいメッセージを検出
    old_ids = {f"{m['timestamp']}_{m['name']}" for m in old_messages}
    new_ids = {f"{m['timestamp']}_{m['name']}" for m in new_messages}
    added_ids = new_ids - old_ids
    
    print(f"📊 既存: {len(old_messages)}件")
    print(f"📊 現在: {len(new_messages)}件")
    print(f"📊 新規: {len(added_ids)}件\n")
    
    if not added_ids:
        print("✓ 新しいメッセージはありません\n")
        return

    # 4. 新規メッセージの音声生成
    for msg in new_messages:
        msg_id = f"{msg['timestamp']}_{msg['name']}"
        
        if msg_id not in added_ids:
            continue
        
        print(f"🎤 処理中: {msg['name']}さん")
        

        # タイムスタンプからファイル名用の文字列生成
        ts = msg['timestamp'].replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')


        # タイムスタンプから日付を取得
        from datetime import datetime
        timestamp_str = msg['timestamp']
        
        # フォーマット判定（ISO形式 or スラッシュ区切り）
        if 'T' in timestamp_str or 'Z' in timestamp_str:
            # ISO形式: 2025-12-18T18:21:00.000Z
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            # スラッシュ形式: 2025/12/18 18:21:00
            dt = datetime.strptime(timestamp_str, '%Y/%m/%d %H:%M:%S')
        
        date_str = dt.strftime('%m月%d日')

        # 名前音声（タイムスタンプ_名前.wav）
        name_file = NAMES_DIR / f"{ts}_{msg['name']}.wav"
        generate_audio(f"{date_str}、{msg['name']}さん", name_file)
        
        # メッセージ音声（タイムスタンプ_名前.wav）
        message_file = MESSAGES_DIR / f"{ts}_{msg['name']}.wav"
        generate_audio(msg['message'], message_file)
        
        print()

    
    # 5. messages.json更新
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_messages, f, ensure_ascii=False, indent=2)
    
    print("=" * 60)
    print("✅ 完了")
    print("=" * 60)

if __name__ == '__main__':
    main()

