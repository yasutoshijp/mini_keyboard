#!/usr/bin/env python3
import evdev
import pygame
import time
import sys
import os

# --- 設定 ---
# 周波数はWAVファイルに合わせるのがベストですが、指定通り16000にします
pygame.mixer.init(frequency=16000, channels=1, buffer=1024)

# 音声ファイルパス
WAV_FILE = "/home/yasutoshi/projects/06.mini_keyboard/audio/kettei.wav"

# ファイルの存在確認
if not os.path.exists(WAV_FILE):
    print(f"エラー: 音声ファイルが見つかりません: {WAV_FILE}")
    sys.exit(1)

# 【最適化】: ループ内で毎回ロードせず、メモリに読み込んでおく
# これにより再生の遅延（ラグ）がなくなります
try:
    BUTTON_SOUND = pygame.mixer.Sound(WAV_FILE)
except pygame.error as e:
    print(f"音声ファイルの読み込みに失敗しました: {e}")
    sys.exit(1)

# 重複防止設定
last_press_time = 0
debounce = 0.5

def main():
    global last_press_time
    
    # キーボード検出
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    keyboard = None
    for device in devices:
        if 'Keyboard' in device.name and 'Mouse' not in device.name:
            keyboard = device
            break
    
    if not keyboard:
        print("キーボードが見つかりません")
        return
    
    print(f"使用デバイス: {keyboard.name}")
    print("ノブを押してください (Ctrl+C で終了)\n")
    
    try:
        # 【重要】デバイスを占有する (grab)
        # これにより、OS側（システム音量ミュート機能）にキー入力が渡らなくなります
        keyboard.grab()
        
        for event in keyboard.read_loop():
            if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                key = evdev.categorize(event)
                
                # ノブ押下のみ処理 (KEY_MUTE)
                if 'KEY_MUTE' in str(key.keycode):
                    current_time = time.time()
                    
                    if current_time - last_press_time > debounce:
                        print(f"[{time.strftime('%H:%M:%S')}] ノブ押下検知")
                        
                        # 【最適化】事前ロードした音声を再生
                        BUTTON_SOUND.play()
                        
                        print("→ 音声再生")
                        last_press_time = current_time
    
    except IOError:
        print("エラー: デバイスの占有に失敗しました。")
        print("他のプログラムがこのデバイスを使用している可能性があります。")
        
    except KeyboardInterrupt:
        print("\n終了操作を検知しました。")
        
    finally:
        # 【重要】終了時に必ず占有を解除する
        # これをしないと、プログラム終了後もキーボードが効かなくなる場合があります
        if keyboard:
            try:
                keyboard.ungrab()
                print("デバイスの占有を解除しました。")
            except:
                pass
        pygame.quit()

if __name__ == '__main__':
    main()
