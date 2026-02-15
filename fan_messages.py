#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ブログファンからのメッセージ取得・再生モジュール（キャッシュ版）
"""

import requests
import boto3
import os
import subprocess
import struct
import json
from pathlib import Path
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()
SPEAKER_CARD = os.getenv('SPEAKER_CARD', '2')


# Google Apps Script API URL
MESSAGES_API_URL = "https://script.google.com/macros/s/AKfycbwfFiNLr4OAI1aqcn6wdDk_Y9tlTRCxOVNzYkf3XJUqpoeG8GJj9qRJqBWNY1wPZ0uKpg/exec"

# プロジェクトディレクトリ
PROJECT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# キャッシュディレクトリ
CACHE_DIR = PROJECT_DIR / "cache" / "fan_messages"
NAMES_DIR = CACHE_DIR / "names"
MESSAGES_DIR = CACHE_DIR / "messages"

# Polly設定
DEFAULT_REGION = "ap-northeast-1"
DEFAULT_VOICE = "Takumi"
DEFAULT_ENGINE = "neural"
SAMPLE_RATE = "16000"


def get_fan_messages(force_refresh=False):
    """ファンメッセージを取得（キャッシュ優先）"""
    import json
    from pathlib import Path
    
    # キャッシュファイルパス
    cache_file = CACHE_DIR / "messages.json"
    
    # force_refresh が True でない場合はキャッシュを確認
    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                print(f"✓ キャッシュから{len(messages)}件読み込み")
                return messages
        except Exception as e:
            print(f"⚠️ キャッシュ読み込みエラー: {e}")
    
    # APIから取得
    try:
        response = requests.get(MESSAGES_API_URL, timeout=10)
        response.raise_for_status()
        messages = response.json()
        print(f"✓ APIから{len(messages)}件取得")
        
        # 取得成功時はキャッシュを更新
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
            
        return messages
    except Exception as e:
        print(f"⚠️ メッセージ取得エラー: {e}")
        return []



def text_to_speech_polly(text, voice=DEFAULT_VOICE, engine=DEFAULT_ENGINE, sample_rate=SAMPLE_RATE, text_type="text"):
    """Amazon PollyでテキストをPCM音声に変換"""
    polly = boto3.client("polly", region_name=DEFAULT_REGION)
    
    response = polly.synthesize_speech(
        Text=text,
        VoiceId=voice,
        Engine=engine,
        OutputFormat="pcm",
        SampleRate=sample_rate,
        TextType=text_type
    )
    
    if "AudioStream" not in response:
        raise RuntimeError("Polly response has no AudioStream")
    
    return response["AudioStream"].read()



def play_audio_from_cache(filepath: Path):
    """キャッシュから音声ファイルを再生"""
    if not filepath.exists():
        print(f"⚠️ キャッシュファイルが見つかりません: {filepath}")
        return False
    
    try:
        import pygame
        sound = pygame.mixer.Sound(str(filepath))
        sound.play()
        # 再生終了まで待機
        while pygame.mixer.get_busy():
            pygame.time.Clock().tick(10)
        return True
    except Exception as e:
        print(f"⚠️ 音声再生エラー: {e}")
        return False




def play_message_name(timestamp: str, name: str):
    """名前音声を再生（キャッシュから）"""
    # タイムスタンプからファイル名生成
    ts = timestamp.replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')
    name_file = NAMES_DIR / f"{ts}_{name}.wav"
    play_audio_from_cache(name_file)


def play_message_content(timestamp: str, name: str):
    """メッセージ音声を再生（キャッシュから）"""
    # タイムスタンプからファイル名生成
    ts = timestamp.replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')
    message_file = MESSAGES_DIR / f"{ts}_{name}.wav"
    play_audio_from_cache(message_file)


def mono_to_stereo_pcm(mono_pcm: bytes, volume_scale: float = 1.0) -> bytes:
    """モノラルPCMをステレオに変換し、オプションで音量を増幅する"""
    stereo_data = bytearray()
    for i in range(0, len(mono_pcm), 2):
        # 16bit符号付き整数としてパース
        sample_val = struct.unpack("<h", mono_pcm[i:i+2])[0]
        
        # 音量を増幅
        if volume_scale != 1.0:
            sample_val = int(sample_val * volume_scale)
            # クリッピング処理
            if sample_val > 32767: sample_val = 32767
            elif sample_val < -32768: sample_val = -32768
            
        sample = struct.pack("<h", sample_val)
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

def generate_message_audio(msg):
    """メッセージIDを指定して音声ファイルを生成（キャッシュディレクトリ保存）"""
    from datetime import datetime
    
    name = msg['name']
    timestamp_str = msg['timestamp']
    message_text = msg['message']
    
    # タイムスタンプからファイル名用の文字列生成
    ts = timestamp_str.replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')
    
    # タイムスタンプから日付を取得
    if 'T' in timestamp_str or 'Z' in timestamp_str:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    else:
        dt = datetime.strptime(timestamp_str, '%Y/%m/%d %H:%M:%S')
    date_str = dt.strftime('%m月%d日')

    # 名前音声
    name_file = NAMES_DIR / f"{ts}_{name}.wav"
    if not name_file.exists():
        print(f"  生成中(名前): {name_file.name}")
        pcm_mono = text_to_speech_polly(f"{date_str}、{name}さん")
        wav_data = make_wav_from_pcm(mono_to_stereo_pcm(pcm_mono))
        name_file.parent.mkdir(parents=True, exist_ok=True)
        with open(name_file, 'wb') as f:
            f.write(wav_data)

    # メッセージ音声
    message_file = MESSAGES_DIR / f"{ts}_{name}.wav"
    if not message_file.exists():
        print(f"  生成中(本文): {message_file.name}")
        pcm_mono = text_to_speech_polly(message_text)
        wav_data = make_wav_from_pcm(mono_to_stereo_pcm(pcm_mono))
        message_file.parent.mkdir(parents=True, exist_ok=True)
        with open(message_file, 'wb') as f:
            f.write(wav_data)
    
    return True



if __name__ == '__main__':
    # テスト実行
    print("メッセージを取得中...")
    messages = get_fan_messages()
    
    if messages:
        print(f"\n✅ {len(messages)}件のメッセージを取得しました\n")
        for i, msg in enumerate(messages[:3]):
            print(f"{i+1}. {msg['name']}: {msg['message'][:50]}...")
    else:
        print("❌ メッセージが取得できませんでした")
