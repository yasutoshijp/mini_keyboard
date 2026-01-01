#!/usr/bin/env python3
import pygame
import sys

if len(sys.argv) < 2:
    print("Usage: play_audio.py <wav_file>")
    sys.exit(1)

wav_file = sys.argv[1]

pygame.mixer.init(frequency=16000, channels=1)
pygame.mixer.music.load(wav_file)
pygame.mixer.music.play()

while pygame.mixer.music.get_busy():
    pygame.time.Clock().tick(10)
