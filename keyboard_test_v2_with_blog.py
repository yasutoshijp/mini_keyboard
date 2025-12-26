#!/usr/bin/env python3
import evdev
import pygame
import os
import time
import sys
import subprocess
import threading
import requests

# ブログ投稿モジュールをインポート
from blog_poster import post_blog

# ========== 設定 ==========
AUDIO_DIR = "/home/yasutoshi/projects/06.mini_keyboard/audio"
MUKASHIMUKASHI_DIR = "/home/yasutoshi/projects/06.mini_keyboard/mukashimukashi"
TITLES_DIR = os.path.join(MUKASHIMUKASHI_DIR, "titles")

# GitHub情報（Alexa方式と同じ）
FILELIST_URL = "https://raw.githubusercontent.com/HisakoJP/mukashimukashi/main/filelist.txt"
AUDIO_BASE_URL = "https://HisakoJP.github.io/mukashimukashi/"

# オーディオデバイス指定
os.environ['SDL_AUDIODRIVER'] = 'alsa'
os.environ['AUDIODEV'] = 'hw:2,0'

# ========== グローバル変数 ==========
# メニュー項目
menu_items = ["メッセージ再生", "むかしむかし", "ブログ投稿", "LINEする"]
current_menu = 0

# むかしむかし用
mukashimukashi_files = []
mukashimukashi_index = 0

# モード管理
mode = "main_menu"  # "main_menu", "mukashimukashi_menu", "playing_story"

# ノブ回転カウント
knob_counter = 0
knob_threshold = 3

# 重複防止用
last_mute_time = 0
mute_debounce = 0.5

# 音量調整
volume_adjusting = False
current_volume = 70

# pygame初期化
pygame.mixer.init(frequency=48000, channels=2, buffer=1024)

# 音声を事前ロード
sounds = {}

# ffplay再生プロセス管理
ffplay_process = None


# ========== 音声関連 ==========
def load_sounds():
    """起動時に全音声ファイルをロード"""
    global sounds

    sound_files = {
        'menu_0': f'{AUDIO_DIR}/menu_0.wav',
        'menu_1': f'{AUDIO_DIR}/menu_1.wav',
        'menu_2': f'{AUDIO_DIR}/menu_2.wav',
        'menu_3': f'{AUDIO_DIR}/menu_3.wav',
        'kettei': f'{AUDIO_DIR}/kettei.wav',
        'modoru': f'{AUDIO_DIR}/modoru.wav',
        'beep': f'{AUDIO_DIR}/beep.wav',
    }

    for key, filepath in sound_files.items():
        if os.path.exists(filepath):
            try:
                sounds[key] = pygame.mixer.Sound(filepath)
            except pygame.error as e:
                print(f"警告: {filepath} の読み込み失敗: {e}")
        else:
            print(f"警告: ファイルが見つかりません: {filepath}")

def speak(text, index=None):
    """音声再生"""
    print(f"🔊 {text}")

    # 対応する音声を再生
    if index is not None:
        sound_key = f'menu_{index}'
    elif text == "決定":
        sound_key = 'kettei'
    elif text == "戻る":
        sound_key = 'modoru'
    else:
        print(f"⚠️ 未対応の音声: {text}")
        return

    if sound_key in sounds:
        sounds[sound_key].play()
    else:
        print(f"⚠️ 音声未ロード: {sound_key}")


def play_audio_file(filepath, wait=False):
    """汎用音声ファイル再生（wavはpygameで再生）"""
    if not os.path.exists(filepath):
        print(f"⚠️ ファイルが見つかりません: {filepath}")
        return False

    try:
        # wavファイルはpygameで再生
        if filepath.endswith('.wav'):
            sound = pygame.mixer.Sound(filepath)
            sound.play()
            if wait:
                # 再生終了まで待機
                while pygame.mixer.get_busy():
                    pygame.time.Clock().tick(10)
            return True
        else:
            # m4aなどはffplayで再生
            if wait:
                subprocess.run(['ffplay', '-nodisp', '-autoexit', filepath],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(['ffplay', '-nodisp', '-autoexit', filepath],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            return True
    except Exception as e:
        print(f"⚠️ 音声再生エラー: {e}")
        return False



# ========== むかしむかし機能 ==========
def load_mukashimukashi_filelist():
    """GitHubからファイルリストを取得"""
    global mukashimukashi_files

    print("むかしむかしファイルリストを取得中...")

    try:
        response = requests.get(FILELIST_URL, timeout=10)
        response.raise_for_status()

        # ファイルリストを取得（空行を除く）
        mukashimukashi_files = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"✓ {len(mukashimukashi_files)}個の物語を読み込みました\n")
        return True

    except Exception as e:
        print(f"⚠️ ファイルリスト取得エラー: {e}\n")
        return False

def get_title_from_filename(filename):
    """ファイル名からタイトルを取得（拡張子を除く）"""
    return os.path.splitext(filename)[0]


def play_title(index):
    """タイトル音声を再生"""
    if index < 0 or index >= len(mukashimukashi_files):
        return

    filename = mukashimukashi_files[index]
    title = get_title_from_filename(filename)
    print(f"📖 [{index + 1}/{len(mukashimukashi_files)}] {title}")

    # タイトル音声ファイルのパス
    title_audio_path = os.path.join(TITLES_DIR, f"{title}.wav")

    # デバッグ出力を追加
    print(f"   探しているパス: {title_audio_path}")
    print(f"   ファイル存在: {os.path.exists(title_audio_path)}")

    if os.path.exists(title_audio_path):
        print(f"   再生開始...")
        play_audio_file(title_audio_path, wait=True)
        print(f"   再生完了")
    else:
        # タイトル音声がない場合は、テキスト読み上げで代替
        # （Pollyスクリプトがある場合）
        print(f"   タイトル音声なし（テキスト表示のみ）")


def play_story(index):
    """物語を再生（完全ストリーミング）"""
    global mode

    if index < 0 or index >= len(mukashimukashi_files):
        return

    filename = mukashimukashi_files[index]
    url = AUDIO_BASE_URL + filename

    # URLから直接ストリーミング再生
    print(f"▶️  物語を再生: {get_title_from_filename(filename)}")
    print(f"    URL: {url}")
    mode = "playing_story"

    # バックグラウンドで再生（wait=Falseで即座にreturn）
    play_audio_url(url, wait=False)

    # すぐにreturnするので、再生終了は検知しない
    # 再生中はmodeが"playing_story"のままなので、ボタンで停止可能



def play_audio_url(url, wait=False):
    """URLから直接音声をストリーミング再生"""
    global ffplay_process

    try:
        from urllib.parse import quote
        if '://' in url:
            protocol, rest = url.split('://', 1)
            if '/' in rest:
                domain, path = rest.split('/', 1)
                encoded_url = f"{protocol}://{domain}/{quote(path)}"
            else:
                encoded_url = url
        else:
            encoded_url = quote(url)

        print(f"🌐 ストリーミング再生: {encoded_url}")

        # pygameを停止してオーディオデバイスを解放
        pygame.mixer.quit()

        # 環境変数設定
        env = os.environ.copy()
        env['SDL_AUDIODRIVER'] = 'alsa'
        env['AUDIODEV'] = 'hw:2,0'

        # Popenでバックグラウンド再生
        ffplay_process = subprocess.Popen(
            ['ffplay', '-nodisp', '-autoexit', encoded_url],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return True
    except Exception as e:
        print(f"⚠️ ストリーミング再生エラー: {e}")
        return False

def stop_story():
    """物語の再生を停止"""
    global mode, ffplay_process

    print("⏹️  再生を停止")

    # ffplayプロセスを終了
    if ffplay_process:
        ffplay_process.terminate()
        ffplay_process.wait()
        ffplay_process = None

    # pygameを再初期化
    pygame.mixer.init(frequency=48000, channels=2, buffer=1024)

    mode = "mukashimukashi_menu"


# ========== ブログ投稿機能 ==========
def do_blog_post():
    """
    ブログ投稿処理
    
    TODO: 将来的に実装する機能
    1. 「内容をお話しください」と音声案内
    2. マイク録音開始
    3. 録音終了（ダイヤルボタン押下）
    4. 音声→テキスト変換（Whisper等）
    5. 「投稿しますか？」確認
    6. はい→投稿、いいえ→キャンセル
    
    現在の実装: テスト用固定値で投稿
    """
    print("\n" + "📝 " * 20)
    print("  ブログ投稿機能")
    print("📝 " * 20 + "\n")
    
    # TODO: 音声案内を追加
    # speak("内容をお話しください。終わったらダイヤルボタンを押してください")
    
    # TODO: マイク録音を追加
    # recorded_audio = record_audio()
    
    # TODO: 音声→テキスト変換を追加
    # transcribed_text = transcribe_audio(recorded_audio)
    
    # TODO: 確認処理を追加
    # speak("投稿しますか？")
    # if not confirm():
    #     speak("キャンセルしました")
    #     return
    
    # ========== 現在はテスト用固定値 ==========
    from datetime import datetime
    
    test_title = f"テスト投稿 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}"
    test_body = """
これはメカニカルキーボードからのテスト投稿です。

✅ システムは正常に動作しています
✅ Pi3で快適に動作中
    """
    
    print(f"タイトル: {test_title}")
    print(f"本文: {test_body[:50]}...")
    print("\n投稿中...\n")
    
    # 環境変数からログイン情報を取得
    username = os.getenv('BLOG_USER')
    password = os.getenv('BLOG_PASSWORD')
    
    if not username or not password:
        print("❌ エラー: 環境変数 BLOG_USER と BLOG_PASSWORD が設定されていません")
        print("   .envファイルを作成してください")
        # TODO: 音声エラー案内
        # speak("エラーが発生しました")
        return
    
    # ブログ投稿実行
    success = post_blog(
        title=test_title,
        body=test_body,
        username=username,
        password=password,
        verbose=True
    )
    
    if success:
        print("\n✅ ブログ投稿成功！\n")
        # TODO: 成功音声を追加
        # speak("投稿完了しました")
    else:
        print("\n❌ ブログ投稿失敗\n")
        # TODO: 失敗音声を追加
        # speak("投稿に失敗しました")


# ========== 音量調整 ==========
def adjust_volume_loop(direction):
    """ボタン押しっぱなし中、音量を徐々に変更"""
    global current_volume, volume_adjusting

    while volume_adjusting:
        if direction == "down":
            current_volume = max(0, current_volume - 5)
        else:  # up
            current_volume = min(100, current_volume + 5)

        # ALSAで音量設定
        subprocess.run(
            ['amixer', '-c', '2', 'sset', 'PCM', f'{current_volume}%'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(f"🔊 音量: {current_volume}%")

        # pygameが初期化されている場合のみビープ音再生
        try:
            if pygame.mixer.get_init() and 'beep' in sounds:
                sounds['beep'].play()
        except:
            pass  # pygameが停止中の場合は無視

        time.sleep(0.3)


# ========== イベントハンドラ ==========
def handle_rotate(direction):
    """ノブ回転時の処理"""
    global current_menu, mukashimukashi_index, knob_counter, mode

    knob_counter += direction

    # しきい値チェック
    if abs(knob_counter) < knob_threshold:
        return

    if mode == "main_menu":
        # メインメニューを循環
        current_menu = (current_menu + (1 if knob_counter > 0 else -1)) % len(menu_items)
        speak(menu_items[current_menu], index=current_menu)
        knob_counter = 0

    elif mode == "mukashimukashi_menu":
        # むかしむかしメニューを循環
        mukashimukashi_index = (mukashimukashi_index + (1 if knob_counter > 0 else -1)) % len(mukashimukashi_files)
        play_title(mukashimukashi_index)
        knob_counter = 0

    elif mode == "playing_story":
        # 再生中は回転を無視
        knob_counter = 0

def handle_button_press():
    """ノブ押下（決定）時の処理"""
    global mode, current_menu, last_mute_time, mukashimukashi_index

    current_time = time.time()
    if current_time - last_mute_time < mute_debounce:
        return
    last_mute_time = current_time

    if mode == "main_menu":
        selected = menu_items[current_menu]
        print(f"\n✅ 決定: {selected}\n")
        speak("決定")

        if selected == "むかしむかし":
            # むかしむかしモードに移行
            if not mukashimukashi_files:
                if not load_mukashimukashi_filelist():
                    print("ファイルリストの取得に失敗しました")
                    return

            mode = "mukashimukashi_menu"
            mukashimukashi_index = 0
            play_title(mukashimukashi_index)
        
        elif selected == "ブログ投稿":
            # ブログ投稿処理を実行
            do_blog_post()

    elif mode == "mukashimukashi_menu":
        # 物語を再生（スレッドを使わない）
        print(f"\n✅ 物語を再生開始\n")
        play_story(mukashimukashi_index)

    elif mode == "playing_story":
        # 再生中に押下 = 停止
        stop_story()

def handle_back_button():
    """戻るボタンの処理"""
    global mode

    print("\n⬅️ 戻る\n")

    if mode == "playing_story":
        # 再生停止してメニューに戻る
        stop_story()
        speak("戻る")
    else:
        speak("戻る")

        if mode == "mukashimukashi_menu":
            # メインメニューに戻る
            mode = "main_menu"
            speak(menu_items[current_menu], index=current_menu)


# ========== メイン処理 ==========
def main():
    global current_menu, knob_counter, volume_adjusting

    # 音声事前ロード
    print("音声ファイルをロード中...")
    load_sounds()
    print(f"{len(sounds)}個の音声ファイルをロードしました\n")

    # 初期音量設定
    subprocess.run(
        ['amixer', '-c', '2', 'sset', 'PCM', f'{current_volume}%'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"初期音量: {current_volume}%\n")

    # デバイス検出
    print("利用可能なデバイス:")
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for i, device in enumerate(devices):
        print(f"{i}: {device.path} - {device.name}")

    keyboard = None
    for device in devices:
        if 'Keyboard' in device.name and 'Mouse' not in device.name:
            keyboard = device
            break

    if not keyboard:
        print("\nキーボードが見つかりません")
        return

    print(f"\n使用デバイス: {keyboard.name}")
    print(f"パス: {keyboard.path}")
    print("\n起動完了。操作してください。")
    print("ボタン1: 戻る")
    print("ボタン2: 音量DOWN（押しっぱなし）")
    print("ボタン4: 音量UP（押しっぱなし）\n")

    try:
        # デバイス占有
        keyboard.grab()

        for event in keyboard.read_loop():
            if event.type == evdev.ecodes.EV_KEY:
                key = evdev.categorize(event)

                # キー押下時（value == 1）
                if event.value == 1:
                    # ノブ右回転
                    if key.keycode == 'KEY_VOLUMEUP':
                        handle_rotate(1)

                    # ノブ左回転
                    elif key.keycode == 'KEY_VOLUMEDOWN':
                        handle_rotate(-1)

                    # ノブ押下（決定）
                    elif 'KEY_MUTE' in str(key.keycode):
                        handle_button_press()

                    # ボタン1（戻る）
                    elif key.keycode == 'KEY_UP':
                        handle_back_button()

                    # ボタン2（音量DOWN）
                    elif key.keycode == 'KEY_LEFT':
                        print("\n🔉 音量DOWN開始\n")
                        volume_adjusting = True
                        threading.Thread(
                            target=adjust_volume_loop,
                            args=("down",),
                            daemon=True
                        ).start()

                    # ボタン3（予備）
                    elif key.keycode == 'KEY_DOWN':
                        print("\n⚙️ ボタン3（予備）\n")

                    # ボタン4（音量UP）
                    elif key.keycode == 'KEY_RIGHT':
                        print("\n🔊 音量UP開始\n")
                        volume_adjusting = True
                        threading.Thread(
                            target=adjust_volume_loop,
                            args=("up",),
                            daemon=True
                        ).start()

                # キーを離した時（value == 0）
                elif event.value == 0:
                    # ボタン2または4を離した = 音量調整停止
                    if key.keycode in ['KEY_LEFT', 'KEY_RIGHT']:
                        volume_adjusting = False
                        print(f"\n音量調整完了: {current_volume}%\n")




    except KeyboardInterrupt:
        print("\n終了")
    finally:
        # ffplayプロセスを確実に終了
        global ffplay_process
        if ffplay_process:
            ffplay_process.terminate()
            ffplay_process.wait()

        if keyboard:
            try:
                keyboard.ungrab()
                print("デバイス占有を解除しました")
            except:
                pass
        pygame.quit()



if __name__ == '__main__':
    main()
