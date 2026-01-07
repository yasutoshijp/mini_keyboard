import os
import json
import requests
import subprocess
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
SONGS_DIR = os.path.join(AUDIO_DIR, "bird_songs")
NAMES_DIR = os.path.join(AUDIO_DIR, "bird_names")

os.makedirs(SONGS_DIR, exist_ok=True)
os.makedirs(NAMES_DIR, exist_ok=True)

# Import polly from fan_messages
sys.path.append(BASE_DIR)
try:
    from fan_messages import text_to_speech_polly
except ImportError:
    print("Error: fan_messages.py not found in current directory.")
    sys.exit(1)

def pcm_to_wav(pcm_data, wav_path):
    """Convert raw PCM data from Polly to WAV using ffmpeg"""
    cmd = [
        'ffmpeg', '-y',
        '-f', 's16le', '-ar', '16000', '-ac', '1',
        '-i', 'pipe:0',
        wav_path
    ]
    try:
        subprocess.run(cmd, input=pcm_data, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error converting {wav_path}: {e.stderr.decode()}")

def generate_voice(text, output_path):
    if os.path.exists(output_path):
        return
    print(f"Generating voice for: {text}")
    try:
        data = text_to_speech_polly(text)
        pcm_to_wav(data, output_path)
    except Exception as e:
        print(f"Error generating voice for {text}: {e}")

def process_song(url, filename_wav):
    wav_path = os.path.join(SONGS_DIR, filename_wav)
    if os.path.exists(wav_path):
        return
    
    mp3_path = wav_path.replace('.wav', '.mp3')
    print(f"Processing: {url}")
    try:
        # Download
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(mp3_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Convert with volume boost (10dB)
        print(f"Converting to WAV (with +10dB boost): {filename_wav}")
        cmd = ['ffmpeg', '-y', '-i', os.path.normpath(mp3_path), '-af', 'volume=10dB', os.path.normpath(wav_path)]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            print(f"FFmpeg error for {filename_wav}: {res.stderr.decode()}")
        else:
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
    except Exception as e:
        print(f"Error processing {url}: {e}")

# 1. Generate Menu Item Voice
generate_voice("鳥のさえずり", os.path.join(AUDIO_DIR, "menu_4.wav"))

# 2. Process Bird Data
with open(os.path.join(BASE_DIR, "bird_songs.json"), 'r', encoding='utf-8') as f:
    birds = json.load(f)

unique_names = set()
for bird in birds:
    process_song(bird['url'], bird['filename'])
    unique_names.add(bird['name'])

for name in sorted(unique_names):
    name_path = os.path.join(NAMES_DIR, f"{name}.wav")
    generate_voice(name, name_path)

print("Audio preparation complete.")
