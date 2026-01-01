#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ブログファンからのメッセージ取得・再生モジュール（キャッシュ版）
"""

import requests
import boto3
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()
SPEAKER_CARD = os.getenv('SPEAKER_CARD', '2')


# Google Apps Script API URL
MESSAGES_API_URL = "https://script.google.com/macros/s/AKfycbwfFiNLr4OAI1aqcn6wdDk_Y9tlTRCxOVNzYkf3XJUqpoeG8GJj9qRJqBWNY1wPZ0uKpg/exec"

# キャッシュディレクトリ
CACHE_DIR = Path("/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages")
NAMES_DIR = CACHE_DIR / "names"
MESSAGES_DIR = CACHE_DIR / "messages"

# Polly設定
DEFAULT_REGION = "ap-northeast-1"
DEFAULT_VOICE = "Takumi"
DEFAULT_ENGINE = "neural"
SAMPLE_RATE = "16000"


def get_fan_messages():
    """ファンメッセージを取得（キャッシュ優先）"""
    import json
    from pathlib import Path
    
    # キャッシュファイルパス
    cache_file = Path("/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages/messages.json")
    
    # キャッシュがあれば、それを返す
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                print(f"✓ キャッシュから{len(messages)}件読み込み")
                return messages
        except Exception as e:
            print(f"⚠️ キャッシュ読み込みエラー: {e}")
    
    # キャッシュがない場合のみAPIから取得
    try:
        response = requests.get(MESSAGES_API_URL, timeout=10)
        response.raise_for_status()
        messages = response.json()
        print(f"✓ APIから{len(messages)}件取得")
        return messages
    except Exception as e:
        print(f"⚠️ メッセージ取得エラー: {e}")
        return []



def text_to_speech_polly(text, voice=DEFAULT_VOICE, engine=DEFAULT_ENGINE, sample_rate=SAMPLE_RATE):
    """Amazon PollyでテキストをPCM音声に変換"""
    polly = boto3.client("polly", region_name=DEFAULT_REGION)
    
    response = polly.synthesize_speech(
        Text=text,
        VoiceId=voice,
        Engine=engine,
        OutputFormat="pcm",
        SampleRate=sample_rate,
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
