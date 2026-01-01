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
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def post_blog(title, body, username=None, password=None, timeout=60, verbose=True):
    """
    エキサイトブログに投稿する（Render API経由）
    
    Args:
        title (str): 投稿タイトル（使用されない。timestampから自動生成）
        body (str): 投稿本文
        username (str): 未使用（Render側で環境変数から取得）
        password (str): 未使用（Render側で環境変数から取得）
        timeout (int): タイムアウト秒数
        verbose (bool): 詳細ログを出力するか
        
    Returns:
        bool: 成功ならTrue、失敗ならFalse
    """
    from datetime import datetime
    import requests
    
    RENDER_URL = 'https://alexa-blog-poster.onrender.com'
    
    if verbose:
        print("=" * 60)
        print("エキサイトブログ投稿開始（Render API経由）")
        print("=" * 60)
    
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
            print(f"レスポンス: {response.json()}")
        
        if response.status_code == 200:
            if verbose:
                print("✓ 投稿完了！")
                print("=" * 60)
            return True
        else:
            if verbose:
                print(f"⚠️ 投稿失敗: ステータスコード {response.status_code}")
            return False
    
    except requests.exceptions.Timeout:
        if verbose:
            print(f"❌ エラー: タイムアウト（{timeout}秒）")
        return False
    
    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"❌ エラー: {e}")
        return False
    
    except Exception as e:
        if verbose:
            print(f"❌ エラー: {e}")
        return False

if __name__ == '__main__':
    """
    テスト実行用
    
    実行方法:
        export BLOG_USER="your_username"
        export BLOG_PASSWORD="your_password"
        python blog_poster.py
    """
    import os
    from datetime import datetime
    
    username = os.getenv('BLOG_USER')
    password = os.getenv('BLOG_PASSWORD')
    
    if not username or not password:
        print("エラー: 環境変数 BLOG_USER と BLOG_PASSWORD を設定してください")
        print("")
        print("設定方法:")
        print("  export BLOG_USER='your_username'")
        print("  export BLOG_PASSWORD='your_password'")
        exit(1)
    
    # テスト投稿
    test_title = f"テスト投稿 {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"
    test_body = """
これはテスト投稿です。

✅ blog_poster.py モジュールが正常に動作しています
✅ メカニカルキーボードシステムに組み込み可能です
    """
    
    print("\n" + "🧪 " * 20)
    print("  テスト投稿を実行します")
    print("🧪 " * 20 + "\n")
    
    success = post_blog(test_title, test_body, username, password)
    
    if success:
        print("\n✅ テスト成功！")
    else:
        print("\n❌ テスト失敗")
