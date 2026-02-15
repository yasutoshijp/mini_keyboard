#!/usr/bin/env python3
"""オーディオ再生テスト - 音が出ない原因を切り分ける"""

import subprocess
import os
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(PROJECT_DIR, "audio")

def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")

def run(cmd, show_error=True):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"コマンドが見つかりません: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)

# ========== 1. デバイス確認 ==========
section("1. オーディオデバイス確認")

rc, out, err = run(['aplay', '-l'])
if rc == 0:
    print(out)
else:
    print(f"  ❌ aplay -l 失敗: {err}")

# ========== 2. PulseAudio 確認 ==========
section("2. PulseAudio 確認")

rc, out, err = run(['pulseaudio', '--check'])
if rc == 0:
    print("  ✅ PulseAudio 動作中")
else:
    print(f"  ❌ PulseAudio 停止中 (rc={rc})")
    print("  → pulseaudio --start を試します...")
    run(['pulseaudio', '--start', '-D'])
    time.sleep(1)
    rc2, _, _ = run(['pulseaudio', '--check'])
    if rc2 == 0:
        print("  ✅ PulseAudio 起動成功")
    else:
        print("  ❌ PulseAudio 起動失敗")

rc, out, err = run(['pactl', 'info'])
if rc == 0:
    for line in out.split('\n'):
        if 'Default Sink' in line or 'Server Name' in line:
            print(f"  {line.strip()}")

# ========== 3. ALSA音量確認 ==========
section("3. ALSA音量確認")

# カード番号を自動検出
rc, out, _ = run(['aplay', '-l'])
cards = []
if rc == 0:
    for line in out.split('\n'):
        if line.startswith('card ') or line.startswith('カード'):
            parts = line.split(':')
            num = parts[0].split()[-1]
            name = parts[1].strip() if len(parts) > 1 else ''
            cards.append((num, name))
            print(f"  カード {num}: {name}")

for card_num, card_name in cards:
    print(f"\n  --- カード {card_num} のミキサー ---")
    rc, out, _ = run(['amixer', '-c', card_num, 'scontents'])
    if rc == 0:
        print(f"  {out[:500]}")

# ========== 4. オーディオファイル確認 ==========
section("4. オーディオファイル確認")

if os.path.isdir(AUDIO_DIR):
    wavs = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.wav')]
    print(f"  ✅ {AUDIO_DIR} に {len(wavs)} 個の .wav ファイル")
    for w in wavs[:5]:
        fpath = os.path.join(AUDIO_DIR, w)
        size = os.path.getsize(fpath)
        print(f"     {w} ({size:,} bytes)")
    if len(wavs) > 5:
        print(f"     ... 他 {len(wavs)-5} ファイル")
else:
    print(f"  ❌ ディレクトリなし: {AUDIO_DIR}")

# ========== 5. speaker-test ==========
section("5. ALSA直接テスト (speaker-test)")

print("  2秒間テストトーンを鳴らします...")
for card_num, card_name in cards:
    if 'bcm2835' in card_name.lower() or 'vc4' in card_name.lower():
        continue
    print(f"  → カード {card_num} ({card_name})")
    rc, out, err = run(['speaker-test', '-c2', '-t', 'sine', '-l1',
                        '-D', f'plughw:{card_num},0', '-p', '2'])
    if rc == 0:
        print(f"  ✅ 再生成功")
    else:
        print(f"  ❌ 失敗: {err[:200]}")

# ========== 6. aplay で WAV 再生 ==========
section("6. aplay で WAV 再生テスト")

test_wav = None
if os.path.isdir(AUDIO_DIR):
    for f in ['beep.wav', 'kettei.wav', 'menu_0.wav']:
        fpath = os.path.join(AUDIO_DIR, f)
        if os.path.exists(fpath):
            test_wav = fpath
            break

if test_wav:
    print(f"  再生ファイル: {test_wav}")
    for card_num, card_name in cards:
        if 'bcm2835' in card_name.lower() or 'vc4' in card_name.lower():
            continue
        print(f"  → aplay -D plughw:{card_num},0 {os.path.basename(test_wav)}")
        rc, out, err = run(['aplay', '-D', f'plughw:{card_num},0', test_wav])
        if rc == 0:
            print(f"  ✅ 再生成功!")
        else:
            print(f"  ❌ 失敗: {err[:200]}")
else:
    print("  ⚠️ テスト用WAVファイルが見つかりません")

# ========== 7. pygame テスト ==========
section("7. pygame テスト")

try:
    import pygame

    # PulseAudio優先
    os.environ['SDL_AUDIODRIVER'] = 'pulseaudio'
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        driver = 'pulseaudio'
    except pygame.error:
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        driver = 'alsa'

    print(f"  ✅ pygame.mixer 初期化OK (driver={driver})")
    freq, size, ch = pygame.mixer.get_init()
    print(f"     freq={freq}, size={size}, channels={ch}")

    if test_wav:
        print(f"  再生テスト: {os.path.basename(test_wav)}")
        s = pygame.mixer.Sound(test_wav)
        s.set_volume(1.0)
        s.play()
        time.sleep(2)
        print("  → 音が聞こえましたか？")
    else:
        print("  ⚠️ テスト用WAVなし、スキップ")

    pygame.mixer.quit()

except ImportError:
    print("  ❌ pygame がインストールされていません")
    print("  → pip3 install pygame")
except Exception as e:
    print(f"  ❌ pygameエラー: {e}")

# ========== 8. 前プロセス確認 ==========
section("8. keyboard_test プロセス確認")

rc, out, _ = run(['pgrep', '-af', 'keyboard_test'])
if out:
    print(f"  ⚠️ 動作中のプロセスあり:")
    for line in out.split('\n'):
        print(f"     {line}")
    print("  → kill してから再実行してください")
else:
    print("  ✅ keyboard_test プロセスなし")

section("完了")
print("  上の結果を見て、どこで止まっているか確認してください。")
print("  5, 6, 7 のどれかで音が出れば、そのルートは使えます。\n")
