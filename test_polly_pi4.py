#!/usr/bin/env python3
import boto3
import os
import sys
import struct
import subprocess
import time
import argparse
from typing import Optional, Tuple

# pygameは環境によって import 自体が重い/不安定なことがあるので、
# 使うときだけ遅延importする（aplayフォールバックを効かせるため）
# import pygame


DEFAULT_REGION = "ap-northeast-1"
DEFAULT_VOICE = "Takumi"
DEFAULT_ENGINE = "neural"          # neural / standard
DEFAULT_SAMPLE_RATE = "16000"      # Polly PCM: 8000 / 16000 / 22050 など

DEFAULT_ALSA_DEVICE = "hw:2,0"     # 変更: hw:2,0
DEFAULT_PREFER = "aplay"  # pygameではなくaplayをデフォルトに

DEFAULT_WAV_PATH = "/tmp/polly_speech.wav"

# 目標音量（PiのPCM）。大きすぎると割れやすいので90%前後推奨
DEFAULT_SET_ALSA_PCM_PERCENT = 90

# pygameのデジタル音量（0.0〜1.0）
DEFAULT_PYGAME_VOLUME = 0.6


def run_cmd(cmd: list, timeout: Optional[int] = None) -> Tuple[int, str, str]:
    """コマンドを実行して (returncode, stdout, stderr) を返す"""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"


def show_aplay_devices() -> None:
    """aplay -l / -L を表示"""
    print("=== aplay -l ===")
    rc, out, err = run_cmd(["aplay", "-l"])
    if rc == 0:
        print(out.rstrip())
    else:
        print(f"(aplay -l failed: rc={rc})")
        if out:
            print(out.rstrip())
        if err:
            print(err.rstrip())

    print("\n=== aplay -L ===")
    rc, out, err = run_cmd(["aplay", "-L"])
    if rc == 0:
        print(out.rstrip())
    else:
        print(f"(aplay -L failed: rc={rc})")
        if out:
            print(out.rstrip())
        if err:
            print(err.rstrip())
    print("")


def alsa_set_pcm_volume(percent: int, card: int = 2) -> None:
    """
    amixerで指定cardのPCM音量を設定。
    """
    percent = max(0, min(100, percent))
    rc, out, err = run_cmd(["amixer", "-c", str(card), "sset", "PCM", f"{percent}%", "unmute"])
    if rc != 0:
        # PCMが存在しない環境もあるので致命にはしない
        print(f"[WARN] amixer set PCM failed (card={card}, rc={rc}).")
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip())


def alsa_get_pcm_volume(card: int = 2) -> None:
    rc, out, err = run_cmd(["amixer", "-c", str(card), "sget", "PCM"])
    if rc != 0:
        print(f"[WARN] amixer get PCM failed (card={card}, rc={rc}).")
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip())
    else:
        print("=== amixer PCM ===")
        print(out.rstrip())
        print("")


def synthesize_polly_pcm(text: str, voice: str, region: str, engine: str, sample_rate: str) -> bytes:
    """PollyでPCMを生成"""
    polly = boto3.client("polly", region_name=region)
    resp = polly.synthesize_speech(
        Text=text,
        VoiceId=voice,
        Engine=engine,
        OutputFormat="pcm",
        SampleRate=sample_rate,
    )
    if "AudioStream" not in resp:
        raise RuntimeError("Polly response has no AudioStream")
    return resp["AudioStream"].read()


def mono_to_stereo_pcm(mono_pcm: bytes) -> bytes:
    """モノラルPCMをステレオに変換（各サンプルを2回繰り返す）"""
    stereo_data = bytearray()
    # 16bit = 2bytes ごとに処理
    for i in range(0, len(mono_pcm), 2):
        sample = mono_pcm[i:i+2]
        stereo_data.extend(sample)  # 左チャンネル
        stereo_data.extend(sample)  # 右チャンネル
    return bytes(stereo_data)


def make_wav_from_pcm(pcm_bytes: bytes, sample_rate: int, channels: int = 2, sampwidth_bytes: int = 2) -> bytes:
    """
    PCM(16bit little-endian) -> WAV (ヘッダ付与)
    """
    byte_rate = sample_rate * channels * sampwidth_bytes
    block_align = channels * sampwidth_bytes
    data_size = len(pcm_bytes)

    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"

    header += b"fmt "
    header += struct.pack("<I", 16)                  # fmt chunk size
    header += struct.pack("<H", 1)                   # PCM
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", block_align)
    header += struct.pack("<H", sampwidth_bytes * 8) # bits per sample

    header += b"data"
    header += struct.pack("<I", data_size)

    return header + pcm_bytes


def play_with_aplay(wav_path: str, alsa_device: str) -> None:
    """aplayで確実に鳴らす"""
    cmd = ["aplay", "-D", alsa_device, wav_path]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        raise RuntimeError(f"aplay failed (rc={rc})\nstdout:\n{out}\nstderr:\n{err}")


def play_with_pygame(wav_path: str, alsa_device: Optional[str], volume: float,
                     mixer_freq: Optional[int] = None,
                     mixer_channels: Optional[int] = None) -> None:
    """
    pygameでWAV再生。失敗したら例外を投げる。
    mixer_freq/mixer_channelsを指定すると、リサンプル癖の差を減らせる場合あり。
    """
    # 遅延import
    import pygame

    os.environ["SDL_AUDIODRIVER"] = "alsa"
    if alsa_device:
        os.environ["SDL_AUDIODEV"] = alsa_device

    # ここは環境で癖があるので、指定がなければデフォルトに任せる
    if mixer_freq is not None and mixer_channels is not None:
        pygame.mixer.init(frequency=mixer_freq, channels=mixer_channels)
    else:
        pygame.mixer.init()

    pygame.mixer.music.load(wav_path)
    pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
    pygame.mixer.music.play()

    # 再生完了待ち
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    # 念のため停止＆解放
    pygame.mixer.music.stop()
    pygame.mixer.quit()






def speak_stable(
    text: str,
    voice: str,
    region: str,
    engine: str,
    sample_rate: str,
    alsa_device: str,
    pygame_volume: float,
    prefer: str,
    wav_path: str,
    keep_wav: bool,
    set_alsa_pcm_percent: Optional[int],
    alsa_card_for_pcm: int,
    pygame_mixer_match_pcm: bool
) -> None:
    """
    安定版の読み上げ：
    1) Polly PCM生成
    2) ステレオ変換
    3) 48kHzにリサンプリング
    4) WAV化して保存
    5) preferに従って pygame/aplay で再生（pygame失敗ならaplayへフォールバック）
    """
    if set_alsa_pcm_percent is not None:
        alsa_set_pcm_volume(set_alsa_pcm_percent, card=alsa_card_for_pcm)

    print(f"音声生成中(pcm): {text[:30]}...")
    pcm = synthesize_polly_pcm(
        text=text,
        voice=voice,
        region=region,
        engine=engine,
        sample_rate=sample_rate,
    )

    # ステレオ変換
    pcm_stereo = mono_to_stereo_pcm(pcm)

    # 一旦16kHzステレオWAV作成
    wav_16k = make_wav_from_pcm(
        pcm_bytes=pcm_stereo,
        sample_rate=int(sample_rate),
        channels=2,
        sampwidth_bytes=2,
    )

    temp_wav = wav_path + ".tmp"
    with open(temp_wav, "wb") as f:
        f.write(wav_16k)

    # sox で 48kHz に変換
    print("48kHzに変換中...")
    rc, out, err = run_cmd(["sox", temp_wav, "-r", "48000", wav_path])
    if rc != 0:
        print(f"[WARN] sox conversion failed (rc={rc}), using 16kHz")
        if err:
            print(err)
        os.rename(temp_wav, wav_path)
    else:
        try:
            os.remove(temp_wav)
        except:
            pass

    print(f"WAV作成: {wav_path}")
    print(f"再生開始... (prefer={prefer}, device={alsa_device})")

    # pygameのmixerを48kHz/stereoに
    mixer_freq = 48000 if pygame_mixer_match_pcm else None
    mixer_channels = 2 if pygame_mixer_match_pcm else None

    last_err = None

    if prefer == "pygame":
        try:
            play_with_pygame(wav_path, alsa_device, pygame_volume, mixer_freq, mixer_channels)
            print("再生完了（pygame）")
            last_err = None
        except Exception as e:
            last_err = e
            print(f"[WARN] pygame playback failed, fallback to aplay. reason={e}")
            play_with_aplay(wav_path, alsa_device)
            print("再生完了（aplay fallback）")

    elif prefer == "aplay":
        play_with_aplay(wav_path, alsa_device)
        print("再生完了（aplay）")

    else:
        raise ValueError("prefer must be 'pygame' or 'aplay'")

    if not keep_wav:
        try:
            os.remove(wav_path)
        except FileNotFoundError:
            pass










def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Amazon Polly (PCM->WAV) を安定再生（pygame / aplay）するテストスクリプト"
    )
    p.add_argument("text", nargs="?", help="読み上げるテキスト")
    p.add_argument("voice", nargs="?", default=DEFAULT_VOICE, help=f"Polly VoiceId (default: {DEFAULT_VOICE})")

    p.add_argument("--region", default=DEFAULT_REGION, help=f"AWS region (default: {DEFAULT_REGION})")
    p.add_argument("--engine", default=DEFAULT_ENGINE, help=f"Polly engine neural/standard (default: {DEFAULT_ENGINE})")
    p.add_argument("--sample-rate", default=DEFAULT_SAMPLE_RATE, help=f"Polly PCM sample rate (default: {DEFAULT_SAMPLE_RATE})")

    p.add_argument("--device", default=DEFAULT_ALSA_DEVICE, help=f"ALSA device for playback (default: {DEFAULT_ALSA_DEVICE})")
    #p.add_argument("--prefer", choices=["pygame", "aplay"], default="pygame", help="Prefer playback method (default: pygame)")


    p.add_argument("--prefer", choices=["pygame", "aplay"], default="aplay", help="Prefer playback method (default: aplay)")


    p.add_argument("--pygame-volume", type=float, default=DEFAULT_PYGAME_VOLUME, help=f"pygame volume 0.0-1.0 (default: {DEFAULT_PYGAME_VOLUME})")

    p.add_argument("--wav-path", default=DEFAULT_WAV_PATH, help=f"WAV output path (default: {DEFAULT_WAV_PATH})")
    p.add_argument("--keep-wav", action="store_true", help="Keep generated WAV file")

    p.add_argument("--set-pcm", type=int, default=None,
                   help=f"Set ALSA PCM percent on card before playback (e.g. {DEFAULT_SET_ALSA_PCM_PERCENT})")
    p.add_argument("--pcm-card", type=int, default=2, help="ALSA card number for PCM volume (default: 2)")

    p.add_argument("--match-mixer", action="store_true",
                   help="Match pygame mixer freq/channels to Polly PCM (can reduce distortion on some envs)")

    p.add_argument("--list", action="store_true", help="Show aplay device list and exit")
    p.add_argument("--show-pcm", action="store_true", help="Show current amixer PCM status and exit")
    return p


def main() -> int:
    parser = build_argparser()
    args = parser.parse_args()

    if args.list:
        show_aplay_devices()
        return 0

    if args.show_pcm:
        alsa_get_pcm_volume(card=args.pcm_card)
        return 0

    if not args.text:
        parser.print_help()
        return 1

    speak_stable(
        text=args.text,
        voice=args.voice,
        region=args.region,
        engine=args.engine,
        sample_rate=args.sample_rate,
        alsa_device=args.device,
        pygame_volume=args.pygame_volume,
        prefer=args.prefer,
        wav_path=args.wav_path,
        keep_wav=args.keep_wav,
        set_alsa_pcm_percent=args.set_pcm,
        alsa_card_for_pcm=args.pcm_card,
        pygame_mixer_match_pcm=args.match_mixer
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
