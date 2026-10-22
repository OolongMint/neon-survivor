"""生成界面截图，便于检查视觉效果。"""
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "tools" / "shots"
OUT.mkdir(exist_ok=True)

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
    audio.init()
    game = Game()
    keys = FakeKeys()
    pygame.key.get_pressed = lambda: keys
    aim = [S.WIDTH / 2, S.HEIGHT / 2]
    pygame.mouse.get_pos = lambda: (int(aim[0]), int(aim[1]))

    # 标题
    game.ui_time = 2.4
    game.update(0)
    game.draw()
    pygame.image.save(game.screen, str(OUT / "1_title.png"))

    # 普通战斗
    game.start_game()
    for i in range(1500):
        w = game.world
        w.player.hp = w.player.max_hp
        w.player.iframes = 0.2
        if w.enemies:
            target = min(w.enemies, key=lambda e: (e.pos - w.player.pos).length_squared())
            aim = [target.pos.x, target.pos.y]
        else:
            aim = [w.player.pos.x + 220, w.player.pos.y]
        ang = i / 60 * 0.8
        keys.down = set()
        if math.cos(ang) > 0.2:
            keys.down.add(pygame.K_d)
        elif math.cos(ang) < -0.2:
            keys.down.add(pygame.K_a)
        if math.sin(ang) > 0.2:
            keys.down.add(pygame.K_s)
        elif math.sin(ang) < -0.2:
            keys.down.add(pygame.K_w)
        game.update(1 / 60)
    # 让一些道具出现
    from entities import Powerup
    w = game.world
    w.powerups.append(Powerup((w.player.pos.x + 160, w.player.pos.y - 90), "rapid"))
    w.powerups.append(Powerup((w.player.pos.x - 200, w.player.pos.y + 110), "shield"))
    w.show_banner("WAVE CLEAR", "+160  //  SECTOR SECURED", 1.3, S.GREEN)
    for _ in range(8):
        game.update(1 / 60)
    game.world.player.hp = 62
    game.world.player.shield = 38
    game.world.player.shield_time = 8
    game.world.player.rapid_time = 7
    game.world.player.spread_time = 5
    game.world.chain = 7
    game.world.chain_timer = 2.0
    game.draw()
    pygame.image.save(game.screen, str(OUT / "2_gameplay.png"))

    # 密集战斗特写
    w = game.world
    w.player.pos.update(S.WIDTH / 2, S.HEIGHT / 2)
    w.player.vel.update(0, 0)
    w.enemies.clear()
    w.bullets.clear()
    w.enemy_bullets.clear()
    keys.down = set()
    for kind, dx, dy in (
        ("drone", 230, -130), ("drone", 300, 90), ("drone", -260, -180),
        ("sprinter", -250, 110), ("sprinter", 180, 210),
        ("tank", -40, 230), ("gunner", 330, -10),
    ):
        w.spawn_enemy_at(kind, (S.WIDTH / 2 + dx, S.HEIGHT / 2 + dy))
    w.enemies[-1].fire_cd = 0.0
    aim = [S.WIDTH / 2 + 230, S.HEIGHT / 2 - 130]
    for _ in range(22):
        game.update(1 / 60)
        w.player.hp = 74
    game.draw()
    pygame.image.save(game.screen, str(OUT / "2b_combat.png"))

    # Boss
    w = game.world
    w.enemies.clear()
    w.spawn_boss(max(5, w.director.wave))
    w.director.state = "clear_wait"
    w.boss.pos.update(S.WIDTH / 2, 160)
    w.boss.entering = False
    for i in range(120):
        game.update(1 / 60)
        w.player.hp = 100
        w.player.iframes = 0.3
    game.draw()
    pygame.image.save(game.screen, str(OUT / "3_boss.png"))

    # 暂停
    game.state = "paused"
    game.draw()
    pygame.image.save(game.screen, str(OUT / "4_pause.png"))

    # 结算
    game.state = "playing"
    w.player.iframes = 0
    w.player.hp = 1
    w.player.shield = 0
    w.player.shield_time = 0
    w._damage_player(999)
    for _ in range(140):
        game.update(1 / 60)
        if game.state == "gameover":
            break
    game.new_record = True
    game.draw()
    pygame.image.save(game.screen, str(OUT / "5_gameover.png"))

    print("saved", sorted(p.name for p in OUT.iterdir()))
    pygame.quit()


if __name__ == "__main__":
    main()
