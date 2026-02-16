"""
ネクストエンジン（NE）自動ログイン＆スクリーンショット取得スクリプト

機能:
  1. Seleniumでネクストエンジンにログイン
  2. ログイン後の強制お知らせモーダルを自動で閉じる
  3. ダウンロードページへ遷移しスクリーンショットを取得
"""

import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

NE_LOGIN_URL = "https://base.next-engine.org/users/sign_in/"
NE_DOWNLOAD_URL = "https://odd.next-engine.com/download.html"


def create_driver():
    """ヘッドレスChromeドライバーを作成する"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ja-JP")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver


def login(driver):
    """ネクストエンジンにログインする"""
    ne_company = os.environ.get("NE_COMPANY", "")
    ne_user = os.environ.get("NE_USER", "")
    ne_password = os.environ.get("NE_PASSWORD", "")

    if not all([ne_company, ne_user, ne_password]):
        print("エラー: 環境変数 NE_COMPANY, NE_USER, NE_PASSWORD を設定してください")
        sys.exit(1)

    print(f"ログインページにアクセス: {NE_LOGIN_URL}")
    driver.get(NE_LOGIN_URL)

    wait = WebDriverWait(driver, 20)

    # 企業コード入力
    company_field = wait.until(
        EC.presence_of_element_located((By.ID, "login_company_code"))
    )
    company_field.clear()
    company_field.send_keys(ne_company)

    # ユーザーID入力
    user_field = driver.find_element(By.ID, "login_id")
    user_field.clear()
    user_field.send_keys(ne_user)

    # パスワード入力
    password_field = driver.find_element(By.ID, "login_password")
    password_field.clear()
    password_field.send_keys(ne_password)

    # ログインボタンクリック
    login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
    login_button.click()

    # ログイン後のページ読み込みを待つ
    time.sleep(5)

    driver.save_screenshot("after_login.png")
    print("ログイン完了 → after_login.png 保存")


def dismiss_forced_messages(driver, max_attempts=5):
    """
    ログイン後の強制お知らせモーダルを自動で閉じる

    NEはログイン後に未読の重要なお知らせをモーダルで強制表示することがある。
    モーダル内コンテンツを最下部までスクロールし（「最後まで読まないと閉じるボタンが
    有効にならない」パターンへの対応）、閉じるボタンをクリックする。
    複数のお知らせが連続する場合も max_attempts までループ対応。

    Args:
        driver: Selenium WebDriver インスタンス
        max_attempts: 最大試行回数（デフォルト: 5）
    """
    # スクロール対象のセレクタ候補
    scroll_selectors = [
        ".modal-body",
        ".modal-content",
        "[class*='modal'] [class*='body']",
        "[class*='modal'] [class*='scroll']",
        "[class*='notification'] [class*='body']",
        "[class*='announce']",
        "[class*='info'] [class*='body']",
        "[style*='overflow']",
    ]

    # 閉じるボタンのテキスト候補
    close_button_texts = ["確認しました", "確認", "閉じる", "既読", "了解", "OK"]

    dismissed_count = 0

    for attempt in range(max_attempts):
        print(f"お知らせモーダル確認中... (試行 {attempt + 1}/{max_attempts})")
        time.sleep(2)

        modal_found = False

        # モーダル内のスクロール可能な要素を探してスクロール
        for selector in scroll_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        # 最下部までスクロール
                        driver.execute_script(
                            "arguments[0].scrollTop = arguments[0].scrollHeight;",
                            el,
                        )
                        time.sleep(1)
                        modal_found = True
            except Exception:
                continue

        if not modal_found:
            print("表示中のモーダルが見つかりません。終了します。")
            break

        # 閉じるボタンを探してクリック
        button_clicked = False

        # テキストでボタンを探す
        for text in close_button_texts:
            try:
                buttons = driver.find_elements(
                    By.XPATH,
                    f"//button[contains(text(), '{text}')] | "
                    f"//a[contains(text(), '{text}')] | "
                    f"//input[@value='{text}'] | "
                    f"//span[contains(text(), '{text}')]/ancestor::button",
                )
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        print(f"  「{text}」ボタンをクリックしました")
                        button_clicked = True
                        dismissed_count += 1
                        time.sleep(2)
                        break
            except Exception:
                continue
            if button_clicked:
                break

        # テキストで見つからなければ class*='close' のボタンを探す
        if not button_clicked:
            try:
                close_buttons = driver.find_elements(
                    By.CSS_SELECTOR, "button[class*='close'], [class*='close']"
                )
                for btn in close_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        print("  closeクラスのボタンをクリックしました")
                        button_clicked = True
                        dismissed_count += 1
                        time.sleep(2)
                        break
            except Exception:
                pass

        if not button_clicked:
            print("  閉じるボタンが見つかりませんでした。終了します。")
            break

    print(f"お知らせモーダル処理完了: {dismissed_count}件閉じました")

    driver.save_screenshot("after_dismiss.png")
    print("after_dismiss.png 保存")


def capture_download_page(driver):
    """
    ダウンロードページへ遷移しスクリーンショットを取得する

    https://odd.next-engine.com/download.html に直接遷移し、
    ポップアップがあれば dismiss_forced_messages で閉じてからスクリーンショットを撮る。

    Args:
        driver: Selenium WebDriver インスタンス
    """
    print(f"ダウンロードページにアクセス: {NE_DOWNLOAD_URL}")
    driver.get(NE_DOWNLOAD_URL)

    # ページ読み込みを待つ
    time.sleep(5)

    # ポップアップがあれば閉じる
    dismiss_forced_messages(driver)

    driver.save_screenshot("download_page.png")
    print("download_page.png 保存")


def main():
    """
    メインフロー:
      1. ログイン
      2. お知らせモーダルを閉じる
      3. ダウンロードページへ遷移＆スクリーンショット
    """
    driver = create_driver()

    try:
        # 1. ログイン
        login(driver)

        # 2. お知らせモーダルを閉じる
        dismiss_forced_messages(driver)

        # 3. ダウンロードページへ遷移＆スクリーンショット
        capture_download_page(driver)

        print("すべての処理が完了しました")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        driver.save_screenshot("error.png")
        raise

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
