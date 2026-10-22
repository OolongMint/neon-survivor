"""无头冒烟测试：驱动游戏数百秒，覆盖波次、Boss、暂停、死亡与重开。

运行：python tools/smoke_test.py
"""
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

import audio
import settings as S
from app import Game


class FakeKeys:
    def __init__(self):
        self.down = set()

    def __getitem__(self, key):
        return key in self.down


def main():
    t0 = time.time()
    audio.init()
    print(f"[smoke] audio ready={audio.available()} init={time.time() - t0:.2f}s")

    game = Game()
    game.draw()
    pygame.display.flip()

    fake_keys = FakeKeys()
    pygame.key.get_pressed = lambda: fake_keys
    aim = [S.WIDTH / 2, S.HEIGHT / 2]
    pygame.mouse.get_pos = lambda: (int(aim[0]), int(aim[1]))

    game.start_game()
    print("[smoke] state:", game.state)

    max_wave = 0
    saw_boss = False
    states = set()

    frames = 6000
    for i in range(frames):
        world = game.world
        # 无敌，保证能跑到 Boss 波次
        world.player.hp = world.player.max_hp
        if world.player.iframes < 0.1:
            world.player.iframes = 0.1

        # 自动瞄准最近的敌人
        if world.enemies:
            target = min(world.enemies, key=lambda e: (e.pos - world.player.pos).length_squared())
            aim = [target.pos.x, target.pos.y]
        elif world.boss is not None:
            aim = [world.boss.pos.x, world.boss.pos.y]
        else:
            aim = [world.player.pos.x + 200, world.player.pos.y]

        # 绕圈走位
        ang = i / 60 * 0.9
        fake_keys.down = set()
        if math.cos(ang) > 0.25:
            fake_keys.down.add(pygame.K_d)
        elif math.cos(ang) < -0.25:
            fake_keys.down.add(pygame.K_a)
        if math.sin(ang) > 0.25:
            fake_keys.down.add(pygame.K_s)
        elif math.sin(ang) < -0.25:
            fake_keys.down.add(pygame.K_w)

        game.update(1 / 60)
        max_wave = max(max_wave, game.world.director.wave)
        if game.world.boss is not None:
            saw_boss = True
        states.add(game.state)

        if i % 3 == 0:
            game.draw()

        if game.state == "gameover":
            print("[smoke] unexpected death at frame", i)
            break

    game.draw()
    print(
        f"[smoke] after {frames} frames: wave={game.world.director.wave} "
        f"max_wave={max_wave} boss_seen={saw_boss} score={game.world.score} "
        f"kills={game.world.kills} enemies={len(game.world.enemies)} "
        f"bullets={len(game.world.bullets)} powerups={len(game.world.powerups)} "
        f"particles={len(game.world.particles.items)}"
    )

    # 暂停界面
    game.state = "paused"
    game.draw()
    pygame.display.flip()
    game.state = "playing"

    # 强制死亡 → 结算界面
    game.world.player.iframes = 0
    game.world.player.hp = 1
    game.world.player.shield = 0
    game.world.player.shield_time = 0
    game.world._damage_player(999)
    assert game.world.player.dead, "player should be dead"
    for _ in range(200):
        game.update(1 / 60)
        game.draw()
        if game.state == "gameover":
            break
    print("[smoke] state after death:", game.state, "finished:", game.world.finished)
    assert game.state == "gameover"
    assert game.best >= 0

    # 重开
    game.start_game()
    for _ in range(120):
        game.update(1 / 60)
        game.draw()
    print("[smoke] restart ok, wave", game.world.director.wave, "hp", game.world.player.hp)
    print(f"[smoke] total {time.time() - t0:.2f}s")
    pygame.quit()
    print("[smoke] PASS")


if __name__ == "__main__":
    main()
