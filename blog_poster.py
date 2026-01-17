#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エキサイトブログ投稿モジュール（組み込み用・軽量版）

Flask不要、requestsのみで動作
メカニカルキーボードシステムに組み込んで使用

使い方:
    from blog_poster import post_blog
    
    success = post_blog(
        title="投稿タイトル",
        body="投稿本文",
        username="your_username",
        password="your_password"
    )
"""

import re
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import asyncio
import types

# Python 3.11+ で削除された asyncio.coroutine の互換性を確保
# mega.py が依存する古い tenacity がこれを使用するため、インポート前にパッチを当てる
if not hasattr(asyncio, 'coroutine'):
    asyncio.coroutine = types.coroutine
    # 一部のライブラリ向けに asyncio.tasks にも設定
    try:
        import asyncio.tasks
        if not hasattr(asyncio.tasks, 'coroutine'):
            asyncio.tasks.coroutine = types.coroutine
    except ImportError:
        pass


def upload_to_mega(file_path, verbose=True):
    """
    megatools を使用してファイルをMEGAにアップロードし、共有リンクを取得する
    """
    import os
    import subprocess
    from dotenv import load_dotenv
    load_dotenv()
    
    email = os.getenv('MEGA_EMAIL')
    password = os.getenv('MEGA_PASSWORD')
    
    if not email or not password:
        if verbose:
            print("⚠️ MEGAの資格情報が設定されていません (.envの MEGA_EMAIL, MEGA_PASSWORD)")
        return None
        
    try:
        from datetime import datetime
        if verbose:
            print(f"MEGAにアップロード中（megatoolsを使用）: {file_path}")
        
        # 1. アップロード実行 (megaput)
        # 同名ファイルエラーを避けるため、MEGA上のファイル名にタイムスタンプを付与
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        local_filename = os.path.basename(file_path)
        base, ext = os.path.splitext(local_filename)
        mega_filename = f"{base}_{now_str}{ext}"
        mega_path = f"/Root/{mega_filename}"
        
        upload_cmd = [
            'megaput',
            '--username', email,
            '--password', password,
            '--path', mega_path, # MEGA上の保存先を指定
            file_path
        ]
        
        result = subprocess.run(upload_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            if verbose:
                print(f"❌ アップロード失敗: {result.stderr or result.stdout}")
            return None
            
        # 2. 公開リンクの取得 (megaexport)
        # megaexport /Root/ファイル名 で公開リンクを表示
        export_cmd = [
            'megaexport',
            '--username', email,
            '--password', password,
            mega_path
        ]

        
        result = subprocess.run(export_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # 出力からリンクを抽出
            output = result.stdout.strip()
            parts = output.split()
            if parts:
                link = parts[-1]
                if link.startswith('http'):
                    if verbose:
                        print(f"✓ アップロード完了: {link}")
                    return link
        
        if verbose:
            print(f"❌ リンク取得失敗: {result.stderr or result.stdout}")
        return None

        
    except Exception as e:
        if verbose:
            print(f"❌ MEGAツール実行エラー: {e}")
        return None


def post_blog(title, body, username=None, password=None, timeout=60, verbose=True, audio_file_path=None):
    """
    エキサイトブログに投稿する（Render API経由）
    
    Args:
        title (str): 投稿タイトル
        body (str): 投稿本文
        username (str): 未使用
        password (str): 未使用
        timeout (int): タイムアウト秒数
        verbose (bool): 詳細ログを出力するか
        audio_file_path (str): MEGAにアップロードする音声ファイルのパス（任意）
        
    Returns:
        bool: 成功ならTrue、失敗ならFalse
    """
    from datetime import datetime
    import requests
    
    RENDER_URL = 'https://alexa-blog-poster.onrender.com'
    
    if verbose:
        print("=" * 60)
        print("エキサイトブログ投稿準備開始")
        print("=" * 60)
        
    # 音声ファイルがあればアップロード
    if audio_file_path and os.path.exists(audio_file_path):
        # --- 音量の正規化（Normalize）処理を追加 ---
        if verbose:
            print(f"🎙️ 音声の音量を調整中（正規化）: {audio_file_path}")
        
        normalized_file = audio_file_path.replace(".wav", "_norm.wav")
        try:
            # ffmpeg を使って音量を正規化 (loudnormフィルターを使用)
            # -af loudnorm は放送基準の音量調整を行うフィルターです
            subprocess.run([
                'ffmpeg', '-y', 
                '-i', audio_file_path,
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
                normalized_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            upload_target = normalized_file
            if verbose:
                print("✓ 音量の調整が完了しました")
        except Exception as e:
            if verbose:
                print(f"⚠️ 音量の調整に失敗しました（元のファイルをアップロードします）: {e}")
            upload_target = audio_file_path

        mega_link = upload_to_mega(upload_target, verbose=verbose)
        
        # 正規化した一時ファイルを削除
        if upload_target != audio_file_path and os.path.exists(upload_target):
            os.remove(upload_target)

        if mega_link:
            # HTMLリンクとして埋め込み
            body += f"\n\n---\n🎙️ 録音された音声:\n<a href=\"{mega_link}\" target=\"_blank\">音声を聞く（MEGA）</a>"


    
    try:
        # Alexa形式のペイロード
        payload = {
            'text': body,
            'timestamp': datetime.now().isoformat() + 'Z'
        }
        
        if verbose:
            print(f"投稿先: {RENDER_URL}")
            print(f"本文: {body[:50]}...")
            print("投稿中...")
        
        response = requests.post(
            RENDER_URL,
            json=payload,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=timeout
        )
        
        response.raise_for_status()
        
        if verbose:
            print(f"ステータスコード: {response.status_code}")
        
        if response.status_code == 200:
            if verbose:
                print("✓ 投稿完了！")
                print("=" * 60)
            return True
        else:
            if verbose:
                print(f"⚠️ 投稿失敗: ステータスコード {response.status_code}")
            return False
    
    except Exception as e:
        if verbose:
            print(f"❌ エラー: {e}")
        return False

if __name__ == '__main__':
    """
    テスト実行用
    """
    import os
    import sys
    from datetime import datetime
    
    # --test-upload 引数があれば、ダミーファイルでテスト
    if len(sys.argv) > 1 and sys.argv[1] == '--test-upload':
        test_file = "mega_test.txt"
        with open(test_file, "w") as f:
            f.write("MEGA Upload Test Content")
        
        print("🧪 MEGAアップロード単体テスト")
        link = upload_to_mega(test_file)
        if link:
            print(f"✅ テスト成功: {link}")
        else:
            print("❌ テスト失敗")
        
        if os.path.exists(test_file):
            os.remove(test_file)
        exit(0)

    # 通常のテスト投稿
    username = os.getenv('BLOG_USER')
    password = os.getenv('BLOG_PASSWORD')
    
    if not username or not password:
        print("エラー: 環境変数 BLOG_USER と BLOG_PASSWORD を設定してください")
        exit(1)
    
    test_title = f"テスト投稿 {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"
    test_body = """
これはテスト投稿です。
✅ blog_poster.py に MEGAアップロード機能が追加されました。
    """
    
    print("\n" + "🧪 " * 20)
    print("  テスト投稿を実行します")
    print("🧪 " * 20 + "\n")
    
    success = post_blog(test_title, test_body, username, password)
    
    if success:
        print("\n✅ テスト成功！")
    else:
        print("\n❌ テスト失敗")

