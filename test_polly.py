import sys
import os
sys.path.append(os.getcwd())
try:
    from fan_messages import text_to_speech_polly
    data = text_to_speech_polly("テスト")
    print(f"Polly OK, received {len(data)} bytes")
except Exception as e:
    print(f"Polly Error: {e}")
