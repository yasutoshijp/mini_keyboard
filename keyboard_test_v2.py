#!/usr/bin/env python3
import evdev
import pygame
import os
import time
import sys
import subprocess
import threading
import requests
import json
import select
import queue
from datetime import datetime




# ★testtestファンメッセージモジュールをインポート
from fan_messages import get_fan_messages, generate_message_audio, text_to_speech_polly, make_wav_from_pcm, mono_to_stereo_pcm

# ブログ投稿モジュールをインポート
from blog_poster import post_blog

# Flaskモジュールをインポート
from flask import Flask, request, jsonify
app = Flask(__name__)

# 環境変数を読み込み
import os
from dotenv import load_dotenv
load_dotenv()

ENV = os.getenv('ENVIRONMENT', 'jikka')
SPEAKER_CARD = os.getenv('SPEAKER_CARD', '2')
MIC_CARD = os.getenv('MIC_CARD', '3')
MIN_VOLUME = int(os.getenv('MIN_VOLUME', '15'))
DIRECTION_VOLUME = int(os.getenv('DIRECTION_VOLUME', '100'))
DIRECTION_BOOST = float(os.getenv('DIRECTION_BOOST', '4.0'))

# 環境設定の確認
print(f"🌍 環境: {ENV}")
print(f"🔊 スピーカー: hw:{SPEAKER_CARD},0")
print(f"🎤 マイク: hw:{MIC_CARD},0")
print(f"📉 背景音最小音量: {MIN_VOLUME}%")
print(f"🧭 方向通知割り込み音量: {DIRECTION_VOLUME}%")
print(f"🚀 方向通知ベースブースト: {DIRECTION_BOOST}倍")



# ========== 設定 ==========
AUDIO_DIR = "/home/yasutoshi/projects/06.mini_keyboard/audio"
MUKASHIMUKASHI_DIR = "/home/yasutoshi/projects/06.mini_keyboard/mukashimukashi"
TITLES_DIR = os.path.join(MUKASHIMUKASHI_DIR, "titles")

# GitHub情報（Alexa方式と同じ）
FILELIST_URL = "https://raw.githubusercontent.com/HisakoJP/mukashimukashi/main/filelist.txt"
AUDIO_BASE_URL = "https://HisakoJP.github.io/mukashimukashi/"

# PulseAudioソケットをsystemdサービスから見えるようにする
if 'XDG_RUNTIME_DIR' not in os.environ:
    uid = os.getuid()
    os.environ['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'

# オーディオデバイス指定（PulseAudio優先、なければALSA）
os.environ['SDL_AUDIODRIVER'] = 'pulseaudio'





# ========== グローバル変数 ==========
# メニュー項目
menu_items = ["ブログファンからメッセージ", "むかしむかし", "ブログ投稿", "LINEする", "鳥のさえずり"]
current_menu = 0

# 鳥のさえずり用
bird_songs = []
bird_song_index = 0

# むかしむかし用
mukashimukashi_files = []
mukashimukashi_index = 0


# ファンメッセージ用（追加）
fan_messages = []
fan_message_index = 0


# モード管理
mode = "main_menu"  # "main_menu", "fan_message_menu", "playing_message", "mukashimukashi_menu", "playing_story", "blog_ready", "blog_recording", "blog_confirm", "bird_song_menu", "playing_bird_song"


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

# ブログ準備モードタイムアウト用
blog_ready_start_time = 0


# pygame初期化（PulseAudio優先、ALSAフォールバック）
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
    print(f"🔊 オーディオドライバー: {os.environ.get('SDL_AUDIODRIVER', 'auto')}")
except pygame.error:
    print("⚠️ PulseAudioで開けません。ALSAで再試行...")
    os.environ['SDL_AUDIODRIVER'] = 'alsa'
    _audio_devices = ['plug:dmixed', f'plughw:{SPEAKER_CARD},0', f'hw:{SPEAKER_CARD},0', 'default']
    for _dev in _audio_devices:
        try:
            os.environ['AUDIODEV'] = _dev
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            print(f"🔊 オーディオデバイス: {_dev}")
            break
        except pygame.error:
            print(f"⚠️ {_dev} を開けません。次を試します...")
            continue
    else:
        print("❌ 利用可能なオーディオデバイスが見つかりません")
        sys.exit(1)
pygame.mixer.set_num_channels(16) # チャンネル数を増やす

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
        'menu_4': f'{AUDIO_DIR}/menu_4.wav',
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
        'modorimasu': f'{AUDIO_DIR}/modorimasu.wav',      # ← 追加
        'fan_message_arrival': f'{AUDIO_DIR}/fan_message_arrival.wav', # ← 追加
        'fan_message_reminder': f'{AUDIO_DIR}/fan_message_reminder.wav', # ← 追加
        'dir_north': f'{AUDIO_DIR}/direction/north.wav',
        'dir_east': f'{AUDIO_DIR}/direction/east.wav',
        'dir_south': f'{AUDIO_DIR}/direction/south.wav',
        'dir_west': f'{AUDIO_DIR}/direction/west.wav',
    }


    for key, filepath in sound_files.items():
        if os.path.exists(filepath):
            try:
                sounds[key] = pygame.mixer.Sound(filepath)
            except pygame.error as e:
                print(f"警告: {filepath} の読み込み失敗: {e}")
        else:
            print(f"警告: ファイルが見つかりません: {filepath}")

def load_bird_songs():
    """鳥のさえずりデータをロード"""
    global bird_songs
    json_path = os.path.join(os.path.dirname(__file__), "bird_songs.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                bird_songs = json.load(f)
                print(f"✓ {len(bird_songs)}件の鳥のデータをロードしました")
                return True
        except Exception as e:
            print(f"⚠️ 鳥のデータロードエラー: {e}")
            return False
    else:
        print(f"⚠️ {json_path} が見つかりません")
        return False

def play_bird_name(index):
    """鳥の名前を再生"""
    if 0 <= index < len(bird_songs):
        bird = bird_songs[index]
        name = bird['name']
        filepath = f"{AUDIO_DIR}/bird_names/{name}.wav"
        print(f"🐦 鳥の名前: {name}")
        play_audio_file(filepath)

def play_bird_song_content(index):
    """鳥のさえずりを再生"""
    global mode
    if 0 <= index < len(bird_songs):
        bird = bird_songs[index]
        filepath = f"{AUDIO_DIR}/bird_songs/{bird['filename']}"
        print(f"🎵 鳴き声再生 (2回連続): {bird['name']} ({bird['memo']})")
        mode = "playing_bird_song"
        # 全ての鳥の鳴き声を一律 2回再生（loops=1）にする
        play_audio_file(filepath, wait=False, loops=1, on_finish=stop_bird_song)

def stop_bird_song():
    """鳥の声を停止"""
    global mode
    print("⏹️  鳥の声を停止")
    audio_mgr.stop_immediately()
    mode = "bird_song_menu"


class SequentialAudioManager:
    """音声を順番に再生するマネージャー（最大待ち数2）"""
    def __init__(self):
        self.queue = queue.Queue(maxsize=10) # 内部的には余裕を持たせるが外部から制御
        self.current_process = None
        self.current_sound = None  # 現在再生中の Sound オブジェクト
        self.current_item_type = None # 現在再生中のアイテムタイプ
        self.stop_requested = False
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        while True:
            item = self.queue.get()
            if item is None: break
            
            # 再生開始
            item_type, data, wait, loops, on_finish = item
            print(f"🎬 再生開始 (Queue): {item_type}")
            
            try:
                self.current_item_type = item_type
                if item_type == "sound":
                    self.current_sound = data
                    self.current_sound.play(loops=loops)
                    # 再生終了を待つ
                    while pygame.mixer.get_busy() and not self.stop_requested:
                        time.sleep(0.05)
                
                elif item_type == "file":
                    # wavはpygame、他はffplay
                    if data.endswith('.wav'):
                        self.current_sound = pygame.mixer.Sound(data)
                        self.current_sound.play(loops=loops)
                        while pygame.mixer.get_busy() and not self.stop_requested:
                            time.sleep(0.05)
                    else:
                        env = os.environ.copy()
                        env['SDL_AUDIODRIVER'] = 'alsa'
                        env['AUDIODEV'] = 'plug:dmixed'
                        # ffplay
                        self.current_process = subprocess.Popen(
                            ['ffplay', '-nodisp', '-autoexit', '-af', 'aformat=sample_fmts=s16:sample_rates=48000', data],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        while self.current_process.poll() is None and not self.stop_requested:
                            time.sleep(0.1)
                
                elif item_type == "url":
                    env = os.environ.copy()
                    env['SDL_AUDIODRIVER'] = 'alsa'
                    env['AUDIODEV'] = 'plug:dmixed'
                    # ffplay
                    self.current_process = subprocess.Popen(
                        ['ffplay', '-nodisp', '-autoexit', '-af', 'aformat=sample_fmts=s16:sample_rates=48000', data],
                        env=env, stdout=subprocess.DEVNULL, stderr=None
                    )
                    while self.current_process.poll() is None and not self.stop_requested:
                        time.sleep(0.1)

            except Exception as e:
                print(f"❌ 再生エラー: {e}")
            finally:
                self.current_sound = None
                self.current_item_type = None
            
            # 停止フラグを戻す
            if self.stop_requested:
                print("🛑 再生中断")
                self.stop_requested = False
            
            # 再生後の間隔
            time.sleep(0.2)
            
            # 完了時コールバックの実行
            if on_finish and not self.stop_requested:
                try:
                    on_finish()
                except Exception as e:
                    print(f"❌ 完了コールバックエラー: {e}")
            
            self.queue.task_done()

    def play(self, item_type, data, wait=False, loops=0, urgent=False, on_finish=None):
        """
        音声をキューに追加。
        urgent=True の場合は現在の再生を止めて即座にキューに追加。
        """
        if urgent:
            self.stop_immediately()

        # キューの制限（「次」と「その次」の最大2つにする）
        while self.queue.qsize() >= 2:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        
        self.queue.put((item_type, data, wait, loops, on_finish))

    def stop_immediately(self):
        """現在の再生を強制停止し、キューも空にする"""
        # キューを空にする
        with self.queue.mutex:
            self.queue.queue.clear()
        
        # 実行中の停止指示
        self.stop_requested = True
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=0.5)
            except: pass
            self.current_process = None
        
        self.current_sound = None
        self.current_item_type = None

    def update_volume(self, volume):
        """リアルタイム音量更新（割り込み方式では使用しませんが、互換性のため残す場合は何もしない）"""
        pass

audio_mgr = SequentialAudioManager()


def speak(text, index=None):
    """音声再生（メニュー読み上げ等） - キュー方式"""
    print(f"🔊 {text}")

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
        audio_mgr.play("sound", sounds[sound_key])
    else:
        print(f"⚠️ 音声未ロード: {sound_key}")


def play_audio_file(filepath, wait=False, loops=0, on_finish=None):
    """汎用音声ファイル再生 - キュー方式"""
    if not os.path.exists(filepath):
        print(f"⚠️ ファイルが見つかりません: {filepath}")
        return False
    audio_mgr.play("file", filepath, wait=wait, loops=loops, on_finish=on_finish)
    return True

def play_audio_url(url, wait=False, on_finish=None):
    """URLから直接音声をストリーミング再生 - キュー方式"""
    audio_mgr.play("url", url, wait=wait, on_finish=on_finish)
    return True


# ========== ファンメッセージ機能 ==========

def parse_message_timestamp(msg):
    """メッセージのタイムスタンプをdatetimeオブジェクトに変換"""
    ts = msg['timestamp']
    try:
        if '/' in ts: return datetime.strptime(ts, '%Y/%m/%d %H:%M:%S')
        elif 'T' in ts or 'Z' in ts:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.replace(tzinfo=None)
        else: return datetime.min
    except Exception as e:
        print(f"⚠️ タイムスタンプ解析エラー: {ts} - {e}")
        return datetime.min

def load_fan_messages():
    """ファンメッセージを取得"""
    global fan_messages
    print("ファンメッセージを取得中...")
    
    try:
        fan_messages_raw = get_fan_messages()
        if fan_messages_raw:
            # 新しい順にソート (共通のパース関数を使用)
            fan_messages = sorted(fan_messages_raw, key=parse_message_timestamp, reverse=True)
            print(f"✓ {len(fan_messages)}件のメッセージを読み込みました\n")
            return True
        else:
            print("⚠️ メッセージがありません\n")
            return False
    except Exception as e:
        print(f"⚠️ メッセージ取得エラー: {e}\n")
        return False

def play_fan_message_name(index):
    """送信者名を音声再生（キャッシュから） - キュー方式"""
    if index < 0 or index >= len(fan_messages):
        return
    
    message = fan_messages[index]
    name = message['name']
    timestamp = message['timestamp']
    print(f"💌 [{index + 1}/{len(fan_messages)}] {name}さん")
    
    # ファイルパスを生成してキューへ
    ts = timestamp.replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')
    name_file = f"/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages/names/{ts}_{name}.wav"
    
    # 【追加】ファイルがなければその場で生成（セルフヒーリング）
    if not os.path.exists(name_file):
        try:
            print(f"✨ 案内音声をオンデマンド生成中: {name}")
            from fan_messages import generate_message_audio
            generate_message_audio(message)
        except Exception as e:
            print(f"⚠️ 案内音声の生成に失敗しました: {e}")
    
    play_audio_file(name_file)


def play_fan_message_content(index):
    """メッセージ本文を音声再生（キャッシュから） - キュー方式"""
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
    
    # キャッシュからファイルをキューへ
    from pathlib import Path
    MESSAGES_DIR = Path("/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages/messages")
    ts = timestamp.replace(':', '').replace('-', '').replace('T', '').replace('Z', '').replace('.000', '').replace('/', '').replace(' ', '')
    message_file = MESSAGES_DIR / f"{ts}_{name}.wav"
    
    # 【追加】ファイルがなければその場で生成（セルフヒーリング）
    if not message_file.exists():
        try:
            print(f"✨ メッセージ本文をオンデマンド生成中: {name}")
            from fan_messages import generate_message_audio
            generate_message_audio(message)
        except Exception as e:
            print(f"⚠️ メッセージ本文の生成に失敗しました: {e}")
    
    if message_file.exists():
        play_audio_file(str(message_file), on_finish=stop_fan_message)
    else:
        print(f"⚠️ メッセージファイルが見つかりません: {message_file}")
        mode = "fan_message_menu"
    
    # 既読更新
    if notifier:
        notifier.mark_as_played(timestamp, name)

def stop_fan_message():
    """メッセージ再生を停止"""
    global mode
    print("⏹️  メッセージ再生を停止")
    audio_mgr.stop_immediately()
    mode = "fan_message_menu"


# ========== 通知・リマインド管理 ==========

class NotificationManager:
    STATE_FILE = "/home/yasutoshi/projects/06.mini_keyboard/cache/fan_messages/notification_state.json"
    
    def __init__(self):
        self.last_notified_id = ""
        self.last_played_id = ""
        self.last_poll_time = 0
        self.last_reminder_hour = -1
        self.load_state()

    def load_state(self):
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.last_notified_id = state.get("last_notified_id", "")
                    self.last_played_id = state.get("last_played_id", "")
                    print(f"🔔 通知状態をロード: notified={self.last_notified_id}, played={self.last_played_id}")
            except Exception as e:
                print(f"⚠️ 通知状態ロードエラー: {e}")

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
            with open(self.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "last_notified_id": self.last_notified_id,
                    "last_played_id": self.last_played_id
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 通知状態保存エラー: {e}")

    def get_msg_id(self, msg):
        return f"{msg['timestamp']}_{msg['name']}"

    def ensure_voices(self, paths):
        """通知用音声がない場合に生成"""
        # 1. 新着通知
        arrival_file = paths['fan_message_arrival']
        if not os.path.exists(arrival_file):
            print("🔊 新着通知音を生成中...")
            pcm = text_to_speech_polly("新しいブログファンメッセージがあります")
            wav = make_wav_from_pcm(mono_to_stereo_pcm(pcm))
            with open(arrival_file, 'wb') as f: f.write(wav)
            sounds['fan_message_arrival'] = pygame.mixer.Sound(arrival_file)

        # 2. リマインド通知
        reminder_file = paths['fan_message_reminder']
        if not os.path.exists(reminder_file):
            print("🔊 リマインド音を生成中...")
            pcm = text_to_speech_polly("まだ聞いていないメッセージがあります")
            wav = make_wav_from_pcm(mono_to_stereo_pcm(pcm))
            with open(reminder_file, 'wb') as f: f.write(wav)
            sounds['fan_message_reminder'] = pygame.mixer.Sound(reminder_file)

    def is_within_time_window(self):
        now = datetime.now()
        return 7 <= now.hour < 18

    def check_notifications(self):
        """10分おきの新着チェック"""
        if not self.is_within_time_window():
            return

        now = time.time()
        if now - self.last_poll_time < 600: # 10分
            return
        self.last_poll_time = now

        print("🔍 新着メッセージをチェック中...")
        msgs = get_fan_messages(force_refresh=True)
        if not msgs:
            return

        # 最新メッセージを取得（共通のパース関数を使用）
        latest_msg = sorted(msgs, key=parse_message_timestamp, reverse=True)[0]
        latest_id = self.get_msg_id(latest_msg)

        # 初回起動時対策
        if not self.last_notified_id:
            print(f"ℹ️ 初回起動: ベースラインを {latest_id} に設定")
            self.last_notified_id = latest_id
            if not self.last_played_id:
                self.last_played_id = latest_id
            self.save_state()
            return

        if latest_id != self.last_notified_id:
            print(f"✨ 新着検知: {latest_id}")
            # 音声生成
            from fan_messages import generate_message_audio
            generate_message_audio(latest_msg)
            
            # 通知再生
            if 'fan_message_arrival' in sounds:
                audio_mgr.play("sound", sounds['fan_message_arrival'])
            
            self.last_notified_id = latest_id
            self.save_state()

    def check_reminders(self):
        """定時リマインドチェック (8, 12, 16, 18時)"""
        if not self.is_within_time_window():
            return

        now = datetime.now()
        reminder_hours = [8, 12, 16, 18]
        
        if now.hour in reminder_hours and now.hour != self.last_reminder_hour:
            # 未読確認
            if self.last_notified_id > self.last_played_id:
                print(f"⏰ 定時リマインド ({now.hour}時)")
                if 'fan_message_reminder' in sounds:
                    audio_mgr.play("sound", sounds['fan_message_reminder'])
            
            self.last_reminder_hour = now.hour

    def mark_as_played(self, timestamp, name):
        """再生完了時に更新"""
        played_id = f"{timestamp}_{name}"
        if played_id > self.last_played_id:
            print(f"✅ 既読更新: {played_id}")
            self.last_played_id = played_id
            self.save_state()

notifier = None


# ========== 方角読み上げ機能 (HTTP Server) ==========

def ensure_direction_voices(force=False):
    """方角読み上げ用の音声ファイルを生成"""
    direction_dir = os.path.join(AUDIO_DIR, "direction")
    os.makedirs(direction_dir, exist_ok=True)
    
    directions = {
        'north': '北、ベッド方向です。おしりを前にずらし左手を前に出すとスタート地点があります。',
        'east': '東、食卓です。',
        'south': '南、卵豆腐冷蔵庫前',
        'west': '西、ひとつもどしてください。'
    }
    
    for key, text in directions.items():
        filepath = os.path.join(direction_dir, f"{key}.wav")
        if not os.path.exists(filepath) or force:
            print(f"🔊 方角音声生成中 (SSML/Vol+10dB): {text}")
            try:
                # SSMLを使用して音量を上げる (+10dB)
                ssml_text = f"<speak><prosody volume='+10dB'>{text}</prosody></speak>"
                pcm = text_to_speech_polly(ssml_text, text_type='ssml')
                # ソフトウェア・ブースト (DIRECTION_BOOST倍) を適用
                wav = make_wav_from_pcm(mono_to_stereo_pcm(pcm, volume_scale=DIRECTION_BOOST))
                with open(filepath, 'wb') as f:
                    f.write(wav)
                print(f"✓ 生成完了 (Vol 4.0x): {filepath}")
            except Exception as e:
                print(f"⚠️ 方角音声生成エラー ({key}): {e}")

@app.route('/direction', methods=['POST'])
def handle_direction():
    try:
        data = request.json
        direction = data.get('dir')
        
        if not direction:
            return jsonify({"ok": False, "error": "No direction specified"}), 400
            
        filepath = os.path.join(AUDIO_DIR, "direction", f"{direction}.wav")
        
        # 音声ファイルを再生
        # 実行中に書き換えられた場合に備えて、キャッシュ(sounds)を使わず
        # その都度ファイルを読み込んで再生する
        if os.path.exists(filepath):
            print(f"🧭 方向通知 (詳細デバッグ): {direction} -> {filepath}")
            try:
                # 1. 現在鳴っている全てのチャンネルを特定して一時停止
                paused_channels = []
                for i in range(pygame.mixer.get_num_channels()):
                    c = pygame.mixer.Channel(i)
                    if c.get_busy():
                        print(f"DEBUG: Pausing active channel {i}")
                        c.pause()
                        paused_channels.append(c)
                
                # 2. ハードウェア音量を引き上げる (ブースト)
                target_vol = DIRECTION_VOLUME
                print(f"DEBUG: amixer setting [PCM] volume to {target_vol}% (from variable DIRECTION_VOLUME)")
                res = subprocess.run(
                    ['amixer', '-c', SPEAKER_CARD, 'sset', 'PCM', f'{target_vol}%'],
                    capture_output=True, text=True
                )
                if res.returncode != 0:
                    print(f"⚠️ amixer PCM error: {res.stderr.strip()}")
                    # PCMがなければMasterを試す
                    print(f"DEBUG: amixer trying [Master] volume to {target_vol}%")
                    subprocess.run(['amixer', '-c', SPEAKER_CARD, 'sset', 'Master', f'{target_vol}%'], stdout=subprocess.DEVNULL)
                
                time.sleep(0.2) # 音量切り替えの安定待ち
                
                # 3. paplayで再生（PulseAudio経由で確実に音を出す）
                print(f"DEBUG: paplay で再生開始: {filepath}")
                play_result = subprocess.run(
                    ['paplay', filepath],
                    capture_output=True, text=True
                )
                if play_result.returncode != 0:
                    print(f"⚠️ paplay エラー: {play_result.stderr.strip()}")
                else:
                    print(f"DEBUG: paplay 再生完了")
                
                # 5. 音量を元に戻す
                subprocess.run(
                    ['amixer', '-c', SPEAKER_CARD, 'sset', 'PCM', f'{current_volume}%'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                # Masterも一応戻す
                subprocess.run(['amixer', '-c', SPEAKER_CARD, 'sset', 'Master', f'{current_volume}%'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # 6. 一時停止していたチャンネルを再開
                print(f"DEBUG: Resuming {len(paused_channels)} channels")
                for c in paused_channels:
                    c.unpause()
                
                return jsonify({"ok": True, "direction": direction})
            except Exception as e:
                print(f"⚠️ 再生エラー: {e}")
                # エラー時も復元を試みる
                subprocess.run(['amixer', '-c', SPEAKER_CARD, 'sset', 'PCM', f'{current_volume}%'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pygame.mixer.unpause()
                return jsonify({"ok": False, "error": str(e)}), 500
            
        return jsonify({"ok": False, "error": "Audio file not found"}), 404
        
    except Exception as e:
        print(f"⚠️ 方向通知エラー: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

def run_flask_server():
    """Flaskサーバーを起動"""
    print("🚀 HTTPサーバー起動 (Port: 5000)")
    # debug=False, use_reloader=False は必須（スレッド実行のため）
    app.run(host='::', port=5000, debug=False, use_reloader=False)



# ========== むかしむかし機能 ==========
def load_mukashimukashi_filelist():
    """GitHubからファイルリストを取得"""
    global mukashimukashi_files
    print("むかしむかしファイルリストを取得中...")
    try:
        response = requests.get(FILELIST_URL, timeout=10)
        response.raise_for_status()
        mukashimukashi_files = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"✓ {len(mukashimukashi_files)}個の物語を読み込みました\n")
        return True
    except Exception as e:
        print(f"⚠️ ファイルリスト取得エラー: {e}\n")
        return False

def get_title_from_filename(filename):
    return os.path.splitext(filename)[0]


def play_title(index):
    """タイトル音声を再生 - キュー方式"""
    if index < 0 or index >= len(mukashimukashi_files):
        return
    filename = mukashimukashi_files[index]
    title = get_title_from_filename(filename)
    print(f"📖 [{index + 1}/{len(mukashimukashi_files)}] {title}")
    title_audio_path = os.path.join(TITLES_DIR, f"{title}.wav")
    if os.path.exists(title_audio_path):
        play_audio_file(title_audio_path)

def play_story(index):
    """物語を再生（ストリーミング） - キュー方式"""
    global mode
    if index < 0 or index >= len(mukashimukashi_files):
        return
    filename = mukashimukashi_files[index]
    url = AUDIO_BASE_URL + filename
    print(f"▶️  物語を再生: {get_title_from_filename(filename)}")
    mode = "playing_story"
    play_audio_url(url, on_finish=stop_story)

def stop_story():
    """物語の再生を停止"""
    global mode
    print("⏹️  物語を停止")
    audio_mgr.stop_immediately()
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
            # blog_poster.py の post_blog 関数を使用
            # これにより自動的にMEGAアップロードが行われる
            success = post_blog(
                title="", # 自動生成されるので空でOK
                body=blog_content,
                audio_file_path=blog_audio_file,
                verbose=True
            )

            if success:
                print("\n✅ ブログ投稿成功（音声アップロード含む）\n")
            else:
                print("\n❌ ブログ投稿失敗\n")

        except Exception as e:
            print(f"\n❌ エラー: {e}\n")


    thread = threading.Thread(target=post_in_background, daemon=True)
    thread.start()


# ========== ブログ投稿機能 ==========
def do_blog_post():
    """ブログ投稿開始"""
    global mode

    print("\n📝 ブログ投稿モード開始\n")

    # 音声案内（新モード入り口なので現在再生中を止める）
    if 'blog_ready' in sounds:
        audio_mgr.play("sound", sounds['blog_ready'], urgent=True)

    mode = "blog_ready"
    
    # タイムアウト計測開始（3分）
    global blog_ready_start_time
    blog_ready_start_time = time.time()



# ========== 音量調整 ==========
def adjust_volume_loop(direction):
    """ボタン押しっぱなし中、音量を徐々に変更"""
    global current_volume, volume_adjusting

    while volume_adjusting:
        if direction == "down":
            current_volume = max(MIN_VOLUME, current_volume - 5)  # 設定された下限未満にならないように
        else:  # up
            current_volume = min(100, current_volume + 5)

        # ALSAで音量設定を復元
        subprocess.run(
            ['amixer', '-c', SPEAKER_CARD, 'sset', 'PCM', f'{current_volume}%'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(f"🔊 音量: {current_volume}%")

        # リアルタイム音量反映は amixer 経由になったため、audio_mgr への通知は不要

        # pygameが初期化されている場合のみビープ音再生
        try:
            if pygame.mixer.get_init() and 'beep' in sounds:
                s = sounds['beep']
                s.set_volume(1.0) # システム音量で管理するため 1.0
                s.play()
        except Exception as e:
            print(f"⚠️ ビープ再生エラー: {e}")

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

    elif mode == "bird_song_menu":
        # 鳥のさえずりメニューを循環
        global bird_song_index
        bird_song_index = (bird_song_index + (1 if knob_counter > 0 else -1)) % len(bird_songs)
        play_bird_name(bird_song_index)
        knob_counter = 0

    elif mode == "playing_story":
        # 再生中は回転を無視
        knob_counter = 0

    elif mode == "playing_message":
        # 再生中は回転を無視
        knob_counter = 0


def handle_button_press():
    """ノブ押下（決定）時の処理"""
    global mode, current_menu, last_mute_time, mukashimukashi_index, fan_message_index, blog_confirm_start_time, bird_song_index




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
        
        # 決定時は即座に「決定」と言いたい
        speak("決定")

        # 「決定」音声が終わるまで待機
        time.sleep(0.5)


        if selected == "ブログファンからメッセージ":
            # 毎回ロードを実行する
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

        elif selected == "鳥のさえずり":
            if not bird_songs:
                if not load_bird_songs():
                    return
            mode = "bird_song_menu"
            bird_song_index = 0
            play_bird_name(bird_song_index)

    elif mode == "fan_message_menu":
        print(f"\n✅ メッセージを再生開始\n")

        # 「再生します」音声
        if 'saisei' in sounds:
            audio_mgr.play("sound", sounds['saisei'], urgent=True)
            time.sleep(1.4)

        play_fan_message_content(fan_message_index)

    elif mode == "mukashimukashi_menu":
        print(f"\n✅ 物語を再生開始\n")

        # 「再生します」音声
        if 'saisei' in sounds:
            audio_mgr.play("sound", sounds['saisei'], urgent=True)
            time.sleep(1.4)  # 音声の長さ分待つ

        play_story(mukashimukashi_index)

    elif mode == "bird_song_menu":
        print(f"\n✅ 鳥の声を再生開始\n")
        if 'saisei' in sounds:
            audio_mgr.play("sound", sounds['saisei'], urgent=True)
            time.sleep(1.4)
        play_bird_song_content(bird_song_index)

    elif mode == "playing_story":
        stop_story()

    elif mode == "playing_message":
        stop_fan_message()

    elif mode == "playing_bird_song":
        stop_bird_song()

    elif mode == "blog_ready":
        # 「録音開始」音声
        if 'recording_start' in sounds:
            audio_mgr.play("sound", sounds['recording_start'], urgent=True)
            time.sleep(1.0) 
        
        # ビープ音
        if 'beep' in sounds:
            audio_mgr.play("sound", sounds['beep'])
            time.sleep(0.3)

        start_blog_recording()

    elif mode == "blog_recording":
        # 録音停止 → 即座に投稿
        stop_blog_recording()

        # 「投稿を依頼しました」を再生
        if 'blog_posted' in sounds:
            audio_mgr.play("sound", sounds['blog_posted'], urgent=True)

        mode = "main_menu"
        transcribe_and_post()

    elif mode == "blog_confirm":
        if 'blog_posted' in sounds:
            audio_mgr.play("sound", sounds['blog_posted'], urgent=True)

        mode = "main_menu"
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

    elif mode == "playing_bird_song":
        stop_bird_song()
        speak("戻る")

    elif mode == "blog_ready":
        # ブログ投稿をキャンセル（即座に止める）
        audio_mgr.stop_immediately()
        if 'blog_cancel' in sounds:
            audio_mgr.play("sound", sounds['blog_cancel'])
        mode = "main_menu"
        blog_ready_start_time = 0 # タイマーリセット
        speak(menu_items[current_menu], index=current_menu)

    #elif mode == "blog_recording":
    #    # 録音中は戻れない（無視）
    #    print("⚠️ 録音中は戻れません")

    elif mode == "blog_recording":
        # 録音停止 → 投稿
        stop_blog_recording()

        # 音声を再生（即座に）
        if 'blog_posted' in sounds:
            audio_mgr.play("sound", sounds['blog_posted'], urgent=True)

        mode = "main_menu"
        transcribe_and_post()




    elif mode == "blog_confirm":
        # 投稿をキャンセル
        if 'blog_cancel' in sounds:
            audio_mgr.play("sound", sounds['blog_cancel'], urgent=True)
            # キャンセル音声の再生完了を待つ (manager経由なので大体の待ち)
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

        elif mode == "bird_song_menu":
            mode = "main_menu"
            speak(menu_items[current_menu], index=current_menu)

# ========== メイン処理 ==========
def main():
    global current_menu, knob_counter, volume_adjusting, mode, blog_confirm_start_time, blog_recording_process, last_action_time, button3_press_time, fan_message_index, blog_ready_start_time, notifier, sounds_paths
    
    # パス保持（NotificationManager用）
    sounds_paths = {
        'fan_message_arrival': f'{AUDIO_DIR}/fan_message_arrival.wav',
        'fan_message_reminder': f'{AUDIO_DIR}/fan_message_reminder.wav'
    }

    # 音声事前ロード
    print("音声ファイルをロード中...")
    load_sounds()
    
    # 通知マネージャー初期化
    notifier = NotificationManager()
    notifier.ensure_voices(sounds_paths) # 音声がなければ作成

    # 方角音声を確保
    ensure_direction_voices()
    # 再ロードして方角音声を取り込む
    load_sounds()
    
    print(f"{len(sounds)}個の音声ファイルをロードしました\n")

    # Flaskサーバーを別スレッドで起動
    server_thread = threading.Thread(target=run_flask_server, daemon=True)
    server_thread.start()

    # 初期音量設定
    subprocess.run(
        ['amixer', '-c', SPEAKER_CARD, 'sset', 'PCM', f'{current_volume}%'],
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

    while not keyboard:
        print("\nキーボードが見つかりません。10秒後に再検出します...")
        time.sleep(10)
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for device in devices:
            if 'Keyboard' in device.name and 'Mouse' not in device.name:
                keyboard = device
                break

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

        while True:
            # 0.1秒タイムアウトで入力を待つ
            # タイムアウト時も空リストが返るので、処理は継続してタイムアウト判定を行う
            r, w, x = select.select([keyboard.fd], [], [], 0.1)

            # タイムアウトチェック（ループ毎に実行）
            current_time = time.time()
            if current_time - last_timeout_check > 0.1:
                last_timeout_check = current_time

                # blog_confirm モードのタイムアウト（5秒）
                if mode == "blog_confirm" and blog_confirm_start_time > 0:
                    if current_time - blog_confirm_start_time > 20:
                        print("\n⏱️ タイムアウト: キャンセルします\n")

                        if 'blog_timeout' in sounds:
                            audio_mgr.play("sound", sounds['blog_timeout'], urgent=True)
                            # タイムアウト音声の再生完了を待つ
                            time.sleep(3.5)

                        mode = "main_menu"
                        blog_confirm_start_time = 0

                        # タイムアウト後、2秒間ボタンを無視
                        last_action_time = time.time()

                # blog_ready モードのタイムアウト（3分 = 180秒）
                if mode == "blog_ready" and blog_ready_start_time > 0:
                    if current_time - blog_ready_start_time > 180:
                        print("\n⏱️ タイムアウト: メインメニューに戻ります\n")
                        
                        # 「戻ります」または「戻る」音声
                        if 'modorimasu' in sounds:
                            audio_mgr.play("sound", sounds['modorimasu'], urgent=True)
                            time.sleep(1.5) # 音声の長さ分待つ（概算）
                        elif 'modoru' in sounds:
                            audio_mgr.play("sound", sounds['modoru'], urgent=True)
                            time.sleep(0.5)

                        mode = "main_menu"
                        blog_ready_start_time = 0
                        
                        # メニュー名を読み上げ（復帰確認）
                        speak(menu_items[current_menu], index=current_menu)

                # blog_recording モードの自動停止（60秒）
                if mode == "blog_recording" and blog_recording_process:
                    if blog_recording_process.poll() is not None:
                        # プロセスが終了した（60秒経過）
                        print("\n⏱️ 録音時間上限（60秒）に達しました\n")
                        stop_blog_recording()

                        if 'blog_confirm' in sounds:
                            audio_mgr.play("sound", sounds['blog_confirm'], urgent=True)

                        mode = "blog_confirm"
                        blog_confirm_start_time = time.time()

                # 再生完了チェック（非ブロッキング再生の事後処理）
                if mode == "playing_bird_song" or mode == "playing_message":
                    if not pygame.mixer.get_busy():
                        print(f"\n✅ 再生完了: メニューに戻ります (mode: {mode})\n")
                        if mode == "playing_bird_song":
                            mode = "bird_song_menu"
                        else:
                            mode = "fan_message_menu"

                # 通知・リマインドチェック
                if notifier:
                    notifier.check_notifications()
                    notifier.check_reminders()

            # イベント処理
            if r:
                for event in keyboard.read():
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

                            # ボタン3（音量UP & 再起動）
                            elif key.keycode == 'KEY_DOWN':
                                button3_press_time = time.time()
                                print("\n🔊 音量UP開始 (兼 ボタン3)\n")
                                volume_adjusting = True
                                threading.Thread(
                                    target=adjust_volume_loop,
                                    args=("up",),
                                    daemon=True
                                ).start()

                            # ボタン4（音量UP - 故障中につき無効化検討）
                            elif key.keycode == 'KEY_RIGHT':
                                print("\n⚠️ ボタン4は故障中です\n")
                                # volume_adjusting = True
                                # threading.Thread(
                                #     target=adjust_volume_loop,
                                #     args=("up",),
                                #     daemon=True
                                # ).start()

                        # キーを離した時（value == 0）
                        elif event.value == 0:
                            # ボタン3または4を離した = 音量調整停止
                            if key.keycode in ['KEY_LEFT', 'KEY_RIGHT', 'KEY_DOWN']:
                                volume_adjusting = False
                                print(f"\n音量調整完了: {current_volume}%\n")


                            # ボタン3を離した = 長押しチェック
                            if key.keycode == 'KEY_DOWN':
                                if button3_press_time > 0:
                                    press_duration = time.time() - button3_press_time
                                    if press_duration >= 5.0:
                                        print("\n🔄 5秒長押し検出！再起動します...\n")

                                        # 「再起動します」音声
                                        if 'reboot' in sounds:
                                            s = sounds['reboot']
                                            s.set_volume(1.0)
                                            s.play()
                                            time.sleep(2.0)

                                        if 'beep' in sounds:
                                            s = sounds['beep']
                                            s.set_volume(1.0)
                                            s.play()
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



