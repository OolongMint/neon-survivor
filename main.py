"""霓虹射手 NEON SURVIVOR —— 入口。

运行：python main.py
"""
import pygame

# 必须在 pygame.init 之前设置混音参数
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

import audio  # noqa: E402
from app import Game  # noqa: E402


def main():
    audio.init()
    try:
        Game().run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
