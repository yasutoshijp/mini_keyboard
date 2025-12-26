#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音声ファイルをテキストに変換するモジュール
OpenAI Whisper API使用
"""

import os
from openai import OpenAI

def transcribe_audio(audio_file_path, language="ja"):
    """
    音声ファイルをテキストに変換
    
    Args:
        audio_file_path: 音声ファイルのパス
        language: 言語コード（デフォルト: ja）
    
    Returns:
        str: 認識されたテキスト
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    with open(audio_file_path, 'rb') as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language
        )
    
    return transcript.text

if __name__ == '__main__':
    # テスト実行
    import sys
    
    if len(sys.argv) < 2:
        print("使い方: python voice_to_text.py <音声ファイル>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"エラー: ファイルが見つかりません: {audio_path}")
        sys.exit(1)
    
    print(f"音声認識中: {audio_path}")
    text = transcribe_audio(audio_path)
    print(f"\n認識結果:\n{text}")
