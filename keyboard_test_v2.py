
#!/usr/bin/env python3
import evdev
import pygame
import os
import time
import sys
import subprocess
import threading
import requests





# ★testtestファンメッセージモジュールをインポート
from fan_messages import get_fan_messages

# ブログ投稿モジュールをインポート
from blog_poster import post_blog

# 環境変数を読み込み
import os
from dotenv import load_dotenv
load_dotenv()

ENV = os.getenv('ENVIRONMENT', 'jikka')
SPEAKER_CARD = os.getenv('SPEAKER_CARD', '2')
MIC_CARD = os.getenv('MIC_CARD', '3')

print(f"🌍 環境: {ENV}")
print(f"🔊 スピーカー: hw:{SPEAKER_CARD},0")
print(f"🎤 マイク: hw:{MIC_CARD},0")



# ========== 設定 ==========
AUDIO_DIR = "/home/yasutoshi/projects/06.mini_keyboard/audio"
MUKASHIMUKASHI_DIR = "/home/yasutoshi/projects/06.mini_keyboard/mukashimukashi"
TITLES_DIR = os.path.join(MUKASHIMUKASHI_DIR, "titles")

# GitHub情報（Alexa方式と同じ）
FILELIST_URL = "https://raw.githubusercontent.com/HisakoJP/mukashimukashi/main/filelist.txt"
AUDIO_BASE_URL = "https://HisakoJP.github.io/mukashimukashi/"

# オーディオデバイス指定
os.environ['SDL_AUDIODRIVER'] = 'alsa'
os.environ['AUDIODEV'] = f'hw:{SPEAKER_CARD},0'





# ========== グローバル変数 ==========
# メニュー項目
menu_items = ["ブログファンからメッセージ", "むかしむかし", "ブログ投稿", "LINEする"]
current_menu = 0

# むかしむかし用
mukashimukashi_files = []
mukashimukashi_index = 0


# ファンメッセージ用（追加）
fan_messages = []
fan_message_index = 0


# モード管理
mode = "main_menu"  # "main_menu", "fan_message_menu", "playing_message", "mukashimukashi_menu", "playing_story", "blog_ready", "blog_recording", "blog_confirm"


# ブログ投稿用
blog_audio_file = None
blog_recording_process = None
blog_confirm_start_time = 0


# ノブ回転カウント
knob_counter = 0
knob_threshold = 3

# 重複防止用
last_mute_time = 0
mute_debounce = 0.5
last_action_time = 0

# ボタン3長押し検出用
button3_press_time = 0  # ← 追加

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
        'blog_ready': f'{AUDIO_DIR}/blog_ready.wav',
        'blog_record_start': f'{AUDIO_DIR}/blog_record_start.wav',
        'blog_confirm': f'{AUDIO_DIR}/blog_confirm.wav',
        'blog_posted': f'{AUDIO_DIR}/blog_posted.wav',
        'blog_cancel': f'{AUDIO_DIR}/blog_cancel.wav',
        'blog_timeout': f'{AUDIO_DIR}/blog_timeout.wav',
        'saisei': f'{AUDIO_DIR}/saisei.wav',
        'reboot': f'{AUDIO_DIR}/reboot.wav',
        'message_loading': f'{AUDIO_DIR}/message_loading.wav',      # ← 追加
        'preparing_audio': f'{AUDIO_DIR}/preparing_audio.wav',      # ← 追加
        'recording_start': f'{AUDIO_DIR}/recording_start.wav',
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

# ========== ファンメッセージ機能 ==========

def load_fan_messages():
    """ファンメッセージを取得"""
    global fan_messages
    
    ## 「メッセージを取得しています」音声
    #if 'message_loading' in sounds:
    #    sounds['message_loading'].play()
    
    print("ファンメッセージを取得中...")
    
    try:
        fan_messages_raw = get_fan_messages()
        if fan_messages_raw:
            # 新しい順にソート
            from datetime import datetime


            def parse_timestamp(msg):
                ts = msg['timestamp']
                try:
                    # まずスラッシュ形式を試す（最新メッセージ用）
                    if '/' in ts:
                        return datetime.strptime(ts, '%Y/%m/%d %H:%M:%S')
                    # ISO形式
                    elif 'T' in ts or 'Z' in ts:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        return dt.replace(tzinfo=None)
                    else:
                        return datetime.min  # パースできない場合は最古扱い
                except Exception as e:
                    print(f"⚠️ タイムスタンプ解析エラー: {ts} - {e}")
                    return datetime.min


            fan_messages = sorted(fan_messages_raw, key=parse_timestamp, reverse=True)
            print(f"✓ {len(fan_messages)}件のメッセージを読み込みました\n")
            return True

        else:
            print("⚠️ メッセージがありません\n")
            return False
    except Exception as e:
        print(f"⚠️ メッセージ取得エラー: {e}\n")
        return False

def play_fan_message_name(index):
    """送信者名を音声再生（キャッシュから）"""
    if index < 0 or index >= len(fan_messages):
        return
    
    message = fan_messages[index]
    name = message['name']
    timestamp = message['timestamp']
    print(f"💌 [{index + 1}/{len(fan_messages)}] {name}さん")
    
    # キャッシュから再生
    from fan_messages import play_message_name
    play_message_name(timestamp, name)


def play_fan_message_content(index):
    """メッセージ本文を音声再生（キャッシュから）"""
    global mode
    
    if index < 0 or index >= len(fan_messages):
        return
    
    message = fan_messages[index]
    name = message['name']
    timestamp = message['timestamp']
    content = message['message']
    
    print(f"▶️  メッセージ再生: {name}さん")
    print(f"    内容: {content[:50]}...")
    
    mode = "playing_message"
    
    # キャッシュからファイルパスを取得して再生
    from pathlib import Path
    MESSAGES_DIR = Path("/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages/messages")
    ts = timestamp.replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')
    message_file = MESSAGES_DIR / f"{ts}_{name}.wav"
    
    if message_file.exists():
        import pygame
        sound = pygame.mixer.Sound(str(message_file))
        channel = sound.play()
        # 再生終了まで待機
        while channel.get_busy():
            pygame.time.Clock().tick(10)
        # 再生完了後、メニューに戻る
        mode = "fan_message_menu"
    else:
        print(f"⚠️ メッセージファイルが見つかりません: {message_file}")
        mode = "fan_message_menu"

def stop_fan_message():
    """メッセージ再生を停止"""
    global mode
    
    print("⏹️  メッセージ再生を停止")
    
    # pygame音声を停止
    import pygame
    pygame.mixer.stop()
    
    mode = "fan_message_menu"




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
        env['AUDIODEV'] = f'hw:{SPEAKER_CARD},0'

        # Popenでバックグラウンド再生
        ffplay_process = subprocess.Popen(
            ['ffplay', '-nodisp', '-autoexit', '-af', f'aformat=sample_fmts=s16:sample_rates=48000', encoded_url],
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
def start_blog_recording():
    """録音開始"""
    global blog_recording_process, blog_audio_file, mode

    blog_audio_file = "/home/yasutoshi/projects/06.mini_keyboard/blog_input.wav"

    # 既存ファイルを削除
    if os.path.exists(blog_audio_file):
        os.remove(blog_audio_file)

    print("🎙️ 録音開始（最大60秒）")

    # バックグラウンドで録音開始
    blog_recording_process = subprocess.Popen([
        'arecord',
        '-D', f'plughw:{MIC_CARD},0',
        '-d', '60',  # 最大60秒
        '-f', 'S16_LE',
        '-r', '16000',
        '-c', '1',
        blog_audio_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    mode = "blog_recording"

def stop_blog_recording():
    """録音停止"""
    global blog_recording_process

    if blog_recording_process:
        blog_recording_process.terminate()
        blog_recording_process.wait()
        blog_recording_process = None
        print("✅ 録音停止")



def transcribe_and_post():
    """音声認識してブログ投稿"""
    global blog_audio_file

    from voice_to_text import transcribe_audio
    from datetime import datetime, timezone
    import requests
    import threading

    print("🗣️ 音声をテキストに変換中...")

    try:
        blog_content = transcribe_audio(blog_audio_file)
        print(f"📝 認識されたテキスト:\n{blog_content}\n")
    except Exception as e:
        print(f"❌ 音声認識エラー: {e}")
        return

    # バックグラウンドで投稿
    def post_in_background():
        try:
            response = requests.post(
                'https://alexa-blog-poster.onrender.com',
                json={
                    'text': blog_content,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=120
            )

            if response.status_code == 200:
                print("\n✅ ブログ投稿成功\n")
            else:
                print(f"\n❌ ブログ投稿失敗: {response.status_code}\n")

        except Exception as e:
            print(f"\n❌ エラー: {e}\n")

    thread = threading.Thread(target=post_in_background, daemon=True)
    thread.start()


# ========== ブログ投稿機能 ==========
def do_blog_post():
    """ブログ投稿開始"""
    global mode

    print("\n📝 ブログ投稿モード開始\n")

    # 音声案内
    if 'blog_ready' in sounds:
        sounds['blog_ready'].play()

    mode = "blog_ready"


# ========== 音量調整 ==========
def adjust_volume_loop(direction):
    """ボタン押しっぱなし中、音量を徐々に変更"""
    global current_volume, volume_adjusting

    while volume_adjusting:
        if direction == "down":
            current_volume = max(30, current_volume - 5)  # 55%未満にならないように
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
    global current_menu, mukashimukashi_index, fan_message_index, knob_counter, mode
    


    knob_counter += direction

    # しきい値チェック
    if abs(knob_counter) < knob_threshold:
        return

    if mode == "main_menu":
        # メインメニューを循環
        current_menu = (current_menu + (1 if knob_counter > 0 else -1)) % len(menu_items)
        speak(menu_items[current_menu], index=current_menu)
        knob_counter = 0


    elif mode == "fan_message_menu":
        # ファンメッセージメニューを循環
        fan_message_index = (fan_message_index + (1 if knob_counter > 0 else -1)) % len(fan_messages)
        play_fan_message_name(fan_message_index)
        knob_counter = 0


    elif mode == "mukashimukashi_menu":
        # むかしむかしメニューを循環
        mukashimukashi_index = (mukashimukashi_index + (1 if knob_counter > 0 else -1)) % len(mukashimukashi_files)
        play_title(mukashimukashi_index)
        knob_counter = 0

    elif mode == "playing_story":
        # 再生中は回転を無視
        knob_counter = 0

    elif mode == "playing_message":
        # 再生中は回転を無視
        knob_counter = 0


def handle_button_press():
    """ノブ押下（決定）時の処理"""
    global mode, current_menu, last_mute_time, mukashimukashi_index, fan_message_index, blog_confirm_start_time




    current_time = time.time()
    if current_time - last_mute_time < mute_debounce:
        return
    last_mute_time = current_time


    # タイムアウト後2秒間は無視
    if current_time - last_action_time < 2.0:
        print("⚠️ 処理中です。お待ちください")
        return

    if mode == "main_menu":
        selected = menu_items[current_menu]
        print(f"\n✅ 決定: {selected}\n")
        speak("決定")

        # 「決定」音声が終わるまで待機
        time.sleep(0.5)


        if selected == "ブログファンからメッセージ":
            if not fan_messages:
                if not load_fan_messages():
                    print("メッセージの取得に失敗しました")
                    return

            mode = "fan_message_menu"
            fan_message_index = 0
            play_fan_message_name(fan_message_index)

        elif selected == "むかしむかし":

            if not mukashimukashi_files:
                if not load_mukashimukashi_filelist():
                    print("ファイルリストの取得に失敗しました")
                    return

            mode = "mukashimukashi_menu"
            mukashimukashi_index = 0
            play_title(mukashimukashi_index)

        elif selected == "ブログ投稿":
            do_blog_post()


    elif mode == "fan_message_menu":
        print(f"\n✅ メッセージを再生開始\n")

        # 「再生します」音声
        if 'saisei' in sounds:
            sounds['saisei'].play()
            time.sleep(1.4)

        play_fan_message_content(fan_message_index)

    elif mode == "mukashimukashi_menu":
        print(f"\n✅ 物語を再生開始\n")

        # 「再生します」音声
        if 'saisei' in sounds:
            sounds['saisei'].play()
            time.sleep(1.4)  # 音声の長さ分待つ


        play_story(mukashimukashi_index)



    elif mode == "playing_story":
        stop_story()

    elif mode == "blog_ready":
        # 「録音開始」音声
        if 'recording_start' in sounds:
            sounds['recording_start'].play()
            time.sleep(1.0)  # 音声の長さ分待つ
        
        # ビープ音
        if 'beep' in sounds:
            sounds['beep'].play()
            time.sleep(0.3)

        start_blog_recording()

    elif mode == "blog_recording":
        # 録音停止 → 即座に投稿
        stop_blog_recording()

        # 「投稿を依頼しました」を再生
        if 'blog_posted' in sounds:
            sounds['blog_posted'].play()

        # メインメニューに戻る
        mode = "main_menu"

        # バックグラウンドで音声認識と投稿
        transcribe_and_post()

    elif mode == "blog_confirm":
        # 先に「投稿を依頼しました」を再生
        if 'blog_posted' in sounds:
            sounds['blog_posted'].play()
            ## 音声再生完了を待つ（約5秒）
            #time.sleep(5.5)

        # メインメニューに戻る
        mode = "main_menu"

        # バックグラウンドで音声認識と投稿
        transcribe_and_post()






def handle_back_button():
    """戻るボタンの処理"""
    global mode

    print("\n⬅️ 戻る\n")

    if mode == "playing_message":
        stop_fan_message()
        speak("戻る")

    elif mode == "playing_story":
        stop_story()
        speak("戻る")

    elif mode == "blog_ready":
        # ブログ投稿をキャンセル
        if 'blog_cancel' in sounds:
            sounds['blog_cancel'].play()
        mode = "main_menu"
        speak(menu_items[current_menu], index=current_menu)

    #elif mode == "blog_recording":
    #    # 録音中は戻れない（無視）
    #    print("⚠️ 録音中は戻れません")

    elif mode == "blog_recording":
        # 録音停止 → 投稿
        stop_blog_recording()

        if 'blog_posted' in sounds:
            sounds['blog_posted'].play()

        mode = "main_menu"
        transcribe_and_post()




    elif mode == "blog_confirm":
        # 投稿をキャンセル
        if 'blog_cancel' in sounds:
            sounds['blog_cancel'].play()
            # キャンセル音声の再生完了を待つ
            time.sleep(2.0)

        mode = "main_menu"


    else:
        speak("戻る")


        if mode == "mukashimukashi_menu":
            mode = "main_menu"
            speak(menu_items[current_menu], index=current_menu)

        elif mode == "fan_message_menu":
            mode = "main_menu"
            speak(menu_items[current_menu], index=current_menu)

# ========== メイン処理 ==========
def main():
    global current_menu, knob_counter, volume_adjusting, mode, blog_confirm_start_time, blog_recording_process, last_action_time, button3_press_time, fan_message_index
    
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

        # 前回のチェック時刻
        last_timeout_check = time.time()

        for event in keyboard.read_loop():
            # タイムアウトチェック（0.1秒ごと）
            current_time = time.time()
            if current_time - last_timeout_check > 0.1:
                last_timeout_check = current_time


                # blog_confirm モードのタイムアウト（5秒）

                if mode == "blog_confirm" and blog_confirm_start_time > 0:
                    if current_time - blog_confirm_start_time > 20:
                        print("\n⏱️ タイムアウト: キャンセルします\n")

                        if 'blog_timeout' in sounds:
                            sounds['blog_timeout'].play()
                            # タイムアウト音声の再生完了を待つ
                            time.sleep(3.5)

                        mode = "main_menu"
                        blog_confirm_start_time = 0

                        # タイムアウト後、2秒間ボタンを無視
                        last_action_time = time.time()



                # blog_recording モードの自動停止（60秒）
                if mode == "blog_recording" and blog_recording_process:
                    if blog_recording_process.poll() is not None:
                        # プロセスが終了した（60秒経過）
                        print("\n⏱️ 録音時間上限（60秒）に達しました\n")
                        stop_blog_recording()

                        if 'blog_confirm' in sounds:
                            sounds['blog_confirm'].play()

                        mode = "blog_confirm"
                        blog_confirm_start_time = time.time()



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
                        button3_press_time = time.time()
                        print("\n⚙️ ボタン3 押下開始\n")

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


                    # ボタン3を離した = 長押しチェック
                    elif key.keycode == 'KEY_DOWN':
                        if button3_press_time > 0:
                            press_duration = time.time() - button3_press_time
                            if press_duration >= 5.0:
                                print("\n🔄 5秒長押し検出！再起動します...\n")

                                # 「再起動します」音声
                                if 'reboot' in sounds:
                                    sounds['reboot'].play()
                                    time.sleep(2.0)  # 音声の長さ分待つ

                                if 'beep' in sounds:
                                    sounds['beep'].play()
                                    time.sleep(0.3)
                                subprocess.run(['sudo', 'reboot'])
                            else:
                                print(f"\n⚙️ ボタン3 ({press_duration:.1f}秒)\n")
                            button3_press_time = 0

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
