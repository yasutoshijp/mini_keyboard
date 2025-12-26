#!/usr/bin/env python3
import evdev
import pygame
import os
import time
import sys
import subprocess
import threading

# メニュー項目
menu_items = ["メッセージ再生", "むかしむかし", "ブログ投稿", "LINEする"]
current_menu = 0

# ノブ回転カウント
knob_counter = 0
knob_threshold = 3

# 重複防止用
last_mute_time = 0
mute_debounce = 0.5

# 音量調整
volume_adjusting = False
current_volume = 70  # 初期音量（0-100）

# 音声ファイルディレクトリ
AUDIO_DIR = "/home/yasutoshi/projects/06.mini_keyboard/audio"

# オーディオデバイス指定
os.environ['SDL_AUDIODRIVER'] = 'alsa'
os.environ['AUDIODEV'] = 'hw:2,0'

# pygame初期化
pygame.mixer.init(frequency=48000, channels=2, buffer=1024)

# 音声を事前ロード
sounds = {}

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
        'beep': f'{AUDIO_DIR}/beep.wav',  # ★ この行を追加
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
        
        # ★ ビープ音再生（この3行を追加）
        if 'beep' in sounds:
            sounds['beep'].play()
        
        time.sleep(0.3)  # 0.3秒ごとに5%ずつ変更

def main():
    global current_menu, knob_counter, last_mute_time, volume_adjusting
    
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
                        knob_counter += 1
                        if knob_counter >= knob_threshold:
                            current_menu = (current_menu + 1) % len(menu_items)
                            speak(menu_items[current_menu], index=current_menu)
                            knob_counter = 0
                    
                    # ノブ左回転
                    elif key.keycode == 'KEY_VOLUMEDOWN':
                        knob_counter -= 1
                        if knob_counter <= -knob_threshold:
                            current_menu = (current_menu - 1) % len(menu_items)
                            speak(menu_items[current_menu], index=current_menu)
                            knob_counter = 0
                    
                    # ノブ押下（決定）
                    elif 'KEY_MUTE' in str(key.keycode):
                        current_time = time.time()
                        if current_time - last_mute_time > mute_debounce:
                            print(f"\n✅ 決定: {menu_items[current_menu]}\n")
                            speak("決定")
                            last_mute_time = current_time
                    
                    # ボタン1（戻る）
                    elif key.keycode == 'KEY_UP':
                        print("\n⬅️ 戻る\n")
                        speak("戻る")
                    
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
        if keyboard:
            try:
                keyboard.ungrab()
                print("デバイス占有を解除しました")
            except:
                pass
        pygame.quit()

if __name__ == '__main__':
    main()
