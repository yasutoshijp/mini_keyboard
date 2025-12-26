import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import datetime
import time
import re
import os

# --- 設定 ---
BLOG_URL = "https://hisakobaab.exblog.jp/"

# スプレッドシートID
SPREADSHEET_KEY = "1VJFQK3RWW1aH2FdH7P5it6EsgP4PmxKIlXdXDen7TzQ"

# サービスアカウント鍵のパス
SERVICE_ACCOUNT_FILE = "/home/yasutoshi/projects/06.mini_keyboard/service_account.json" 

# 最新の何記事分をチェックするか
LATEST_ARTICLE_LIMIT = 5

def get_soup(url):
    headers = {"User-Agent": "Mozilla/5.0 (RaspberryPi) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    except Exception as e:
        print(f"Error accessing {url}: {e}")
        return None

def parse_excite_date(date_text):
    """
    ブログの日付文字列から YYYY/MM/DD HH:MM:SS 形式を作成する
    入力例: "... at 2025-12-25 14:24"
    出力例: "2025/12/25 14:24:00"
    """
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})\s(\d{2}):(\d{2})", date_text)
    if match:
        y, m, d, H, M = match.groups()
        return f"{y}/{m}/{d} {H}:{M}:00"
    
    return datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')

def scrape_blog_comments():
    print("🌐 ブログにアクセス中...")
    soup = get_soup(BLOG_URL)
    if not soup:
        return []

    # 最新記事URLを取得
    article_urls = []
    
    for a in soup.find_all("a", href=True):
        href = a['href']
        if "hisakobaab.exblog.jp" in href and re.search(r'/\d+/', href):
            if "#" not in href:
                if href not in article_urls:
                    article_urls.append(href)
        
        if len(article_urls) >= LATEST_ARTICLE_LIMIT:
            break
            
    print(f"📄 直近 {len(article_urls)} 件の記事をチェックします。")

    comments_found = []

    for url in article_urls:
        art_soup = get_soup(url)
        if not art_soup:
            continue

        tails = art_soup.select(".COMMENT_TAIL")

        for tail in tails:
            try:
                # 1. 名前取得
                name_tag = tail.select_one("b")
                author_name = name_tag.text.strip() if name_tag else "名無し"

                # 2. 日付取得 (フォーマット変換済み)
                tail_text = tail.get_text()
                formatted_date = parse_excite_date(tail_text)

                # 3. 本文取得
                body_div = tail.find_next_sibling("div", class_="COMMENT_BODY")
                
                if body_div:
                    for tool in body_div.select(".xbg-comment-tools"):
                        tool.decompose() 
                    
                    message_body = body_div.get_text("\n").strip()

                    if message_body:
                        # 【修正】名前の後ろの (ブログより) を削除しました
                        comments_found.append({
                            "timestamp": formatted_date,
                            "name": author_name, 
                            "message": message_body
                        })
            except Exception as e:
                print(f"解析エラー: {e}")
                continue
        
        time.sleep(1) 

    return comments_found

def update_spreadsheet(new_comments):
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("\n⚠️ 【重要】サービスアカウントのJSONファイルが見つかりません！")
        return

    print("📊 スプレッドシートに接続中...")
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(SPREADSHEET_KEY).sheet1
        
        existing_rows = sheet.get_all_values()
        
        existing_signatures = set()
        for row in existing_rows:
            if len(row) >= 3:
                # 重複チェック用
                sig = f"{row[0]}_{row[1]}_{row[2]}"
                existing_signatures.add(sig)

        rows_to_add = []
        for comment in new_comments:
            row_data = [comment["timestamp"], comment["name"], comment["message"]]
            sig = f"{row_data[0]}_{row_data[1]}_{row_data[2]}"
            
            if sig not in existing_signatures:
                rows_to_add.append(row_data)
                existing_signatures.add(sig)

        if rows_to_add:
            print(f"🚀 {len(rows_to_add)} 件の新規コメントを書き込みます...")
            sheet.append_rows(rows_to_add)
            print("✅ 書き込み完了")
        else:
            print("✨ 新しいコメントはありませんでした。")

    except Exception as e:
        print(f"❌ スプレッドシートのエラー: {e}")

def main():
    print("=== ブログコメント収集開始 ===")
    comments = scrape_blog_comments()
    print(f"🔍 スキャン結果: 合計 {len(comments)} 件のコメントを検出")
    
    if comments:
        update_spreadsheet(comments)
    
    print("=== 完了 ===")

if __name__ == "__main__":
    main()
