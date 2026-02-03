#!/usr/bin/env python3
"""
ポッドキャスト再生モジュール
"""

import xml.etree.ElementTree as ET
import requests
import subprocess
from pathlib import Path

import json
import os

# チャンネル設定ファイル名
CHANNELS_FILE = 'podcast_channels.json'

def get_channels():
    """番組リストを取得（JSONファイルから読み込み）"""
    try:
        # スクリプトと同じディレクトリのJSONファイルを参照
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, CHANNELS_FILE)
        
        if not os.path.exists(json_path):
            print(f"⚠️ 設定ファイルが見つかりません: {json_path}")
            return []
            
        with open(json_path, 'r', encoding='utf-8') as f:
            channels = json.load(f)
            
        return channels
        
    except Exception as e:
        print(f"⚠️ 設定読み込みエラー: {e}")
        return []

def get_episodes(rss_url):
    """指定番組のエピソード一覧を取得"""
    try:
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()
        
        tree = ET.fromstring(response.content)
        episodes = []
        
        for item in tree.findall('.//item'):
            title_elem = item.find('title')
            enclosure_elem = item.find('enclosure')
            
            if title_elem is not None and enclosure_elem is not None:
                title = title_elem.text
                audio_url = enclosure_elem.get('url')
                
                if audio_url:
                    episodes.append({
                        'title': title,
                        'url': audio_url
                    })
        
        print(f"✓ {len(episodes)}エピソード取得")
        return episodes
        
    except Exception as e:
        print(f"⚠️ エピソード取得エラー: {e}")
        return []

def play_episode(audio_url, device='hw:2,0'):
    """エピソードをストリーミング再生"""
    try:
        import os
        env = os.environ.copy()
        env['SDL_AUDIODRIVER'] = 'alsa'
        env['AUDIODEV'] = f'{device}'
        
        # ffplayでストリーミング再生
        process = subprocess.Popen(
            ['ffplay', '-nodisp', '-autoexit', audio_url],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return process
        
    except Exception as e:
        print(f"⚠️ 再生エラー: {e}")
        return None

def stop_playback():
    """再生停止"""
    try:
        subprocess.run(['pkill', 'ffplay'], check=False)
    except:
        pass

if __name__ == '__main__':
    # テスト
    print("=" * 60)
    print("ポッドキャスト再生テスト")
    print("=" * 60)
    
    channels = get_channels()
    for i, ch in enumerate(channels):
        print(f"{i}: {ch['name']}")
