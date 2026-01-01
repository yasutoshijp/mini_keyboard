#!/usr/bin/env python3
import boto3
import requests
import os
import subprocess

FILELIST_URL = "https://raw.githubusercontent.com/HisakoJP/mukashimukashi/main/filelist.txt"
TITLES_DIR = "/home/yasutoshi/projects/06.mini_keyboard/mukashimukashi/titles"

# Pollyクライアント作成
polly = boto3.client('polly', region_name='ap-northeast-1')

# ファイルリスト取得
print("ファイルリストを取得中...")
response = requests.get(FILELIST_URL)
files = [line.strip() for line in response.text.split('\n') if line.strip()]
print(f"✓ {len(files)}個のタイトルを取得\n")

os.makedirs(TITLES_DIR, exist_ok=True)

for i, filename in enumerate(files):
    title = filename.replace('.m4a', '')
    output_path = f"{TITLES_DIR}/{title}.wav"
    
    # すでに存在する場合はスキップ
    if os.path.exists(output_path):
        print(f"[{i+1}/{len(files)}] スキップ: {title}")
        continue
    
    print(f"[{i+1}/{len(files)}] 生成中: {title}")
    
    try:
        # Pollyで音声生成
        polly_response = polly.synthesize_speech(
            Text=title,
            OutputFormat='pcm',
            VoiceId='Takumi',
            Engine='neural',
            SampleRate='16000'
        )
        
        # PCMデータを取得
        pcm_data = polly_response['AudioStream'].read()
        
        # PCMをWAVに変換
        pcm_file = '/tmp/polly_temp.pcm'
        with open(pcm_file, 'wb') as f:
            f.write(pcm_data)
        
        # ffmpegでWAVに変換
        subprocess.run([
            'ffmpeg', '-f', 's16le', '-ar', '16000', '-ac', '1',
            '-i', pcm_file, '-ar', '48000', '-ac', '2', output_path, '-y'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        os.remove(pcm_file)
        print(f"  ✓ 完了")
        
    except Exception as e:
        print(f"  ⚠️ エラー: {e}")

print("\n完了！")
