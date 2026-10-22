"""游戏世界：波次调度、实体管理、碰撞、计分与特效。"""
from __future__ import annotations

import math
import random

import pygame
from pygame.math import Vector2

import audio
import settings as S
from entities import Boss, Bullet, Enemy, EnemyBullet, Player, Powerup
from utils import Background, Particles, from_angle, seg_circle_hit


class World:
    def __init__(self):
        self.background = Background()
        self.particles = Particles()
        self.reset()

    # ------------------------------------------------------------ 生命周期
    def reset(self):
        self.player = Player(S.CENTER)
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.enemy_bullets: list[EnemyBullet] = []
        self.powerups: list[Powerup] = []
        self.boss = None

        self.particles.clear()
        self.score = 0
        self.kills = 0
        self.chain = 0
        self.chain_timer = 0.0
        self.shake = 0.0
        self.hurt_flash = 0.0
        self.time = 0.0
        self.time_scale = 1.0
        self.death_timer = 0.0
        self.finished = False
        self.banner = None
        self.fx_queue = []

        self.director = Director(self)
        self.director.start()

    @property
    def chain_mult(self) -> int:
        return min(S.CHAIN_MAX, 1 + self.chain // S.CHAIN_STEP)

    # ------------------------------------------------------------ 主更新
    def update(self, dt: float, keys, mouse_pos, firing: bool = True):
        dt = min(dt, 1 / 30)
        self.time += dt
        self.background.update(dt, self.player.pos)
        self.shake *= math.exp(-6.5 * dt)
        if self.shake < 0.25:
            self.shake = 0.0
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 2.6)
        self._update_banner(dt)
        self._update_fx(dt)
        self._update_chain(dt)

        # 玩家阵亡：慢动作收尾
        if self.player.dead:
            self.death_timer -= dt
            sim_dt = dt * self.time_scale
            self.particles.update(sim_dt)
            for enemy in self.enemies:
                if enemy.alive:
                    enemy.update(sim_dt, self)
            if self.boss:
                self.boss.update(sim_dt, self)
            self._update_bullets(sim_dt, collide=False)
            for bullet in self.enemy_bullets:
                bullet.update(sim_dt)
            self.enemy_bullets = [b for b in self.enemy_bullets if b.alive and self._on_screen(b.pos)]
            for p in self.powerups:
                p.update(sim_dt, self.player)
            self.powerups = [p for p in self.powerups if p.alive]
            if self.death_timer <= 0:
                self.finished = True
            return

        move = Vector2()
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1

        want_dash = keys[pygame.K_SPACE] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        self.player.update(dt, move, Vector2(mouse_pos), want_dash, self)

        # 自动开火
        if firing and self.player.fire_cd <= 0:
            self._player_shoot()

        self._update_enemies(dt)
        self._update_bullets(dt, collide=True)

        for bullet in self.enemy_bullets:
            bullet.update(dt)
        self._enemy_bullet_collisions()

        for p in self.powerups:
            p.update(dt, self.player)
        self._collect_powerups()

        self.director.update(dt)
        self.particles.update(dt)

        # 清理
        self.enemies = [e for e in self.enemies if e.alive]
        self.powerups = [p for p in self.powerups if p.alive]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive and self._on_screen(b.pos)]

    # ------------------------------------------------------------ 波次辅助
    def show_banner(self, title, sub, duration=2.0, color=S.CYAN):
        self.banner = {
            "title": title,
            "sub": sub,
            "time": float(duration),
            "duration": float(duration),
            "color": color,
        }

    def _update_banner(self, dt):
        if self.banner is not None:
            self.banner["time"] -= dt
            if self.banner["time"] <= 0:
                self.banner = None

    def _update_chain(self, dt):
        if self.chain_timer > 0:
            self.chain_timer -= dt
            if self.chain_timer <= 0:
                self.chain = 0
                self.chain_timer = 0.0

    def _update_fx(self, dt):
        alive = []
        for fx in self.fx_queue:
            fx["t"] -= dt
            if fx["t"] <= 0:
                self.particles.burst(
                    fx["pos"], fx["color"], count=fx.get("count", 14),
                    speed=(80, 360), life=(0.2, 0.65), size=(1, 3.5),
                )
                self.shake = max(self.shake, fx.get("shake", 6.0))
            else:
                alive.append(fx)
        self.fx_queue = alive

    # ------------------------------------------------------------ 射击
    def _player_shoot(self):
        p = self.player
        interval = S.GUN_INTERVAL * (S.RAPID_MULT if p.rapid_time > 0 else 1.0)
        p.fire_cd = interval

        if p.spread_time > 0:
            angles = [p.angle + math.degrees(S.SPREAD_ANGLE * o) for o in (-1, 0, 1)]
        else:
            angles = [p.angle]

        muzzle = p.pos.copy()
        for ang in angles:
            direction = from_angle(ang)
            origin = p.pos + direction * S.MUZZLE_OFFSET
            self.bullets.append(Bullet(origin, direction * S.BULLET_SPEED, S.GUN_DAMAGE, color=S.CYAN))
            muzzle = origin

        audio.play("shoot", 0.035)
        self.particles.burst(
            muzzle,
            S.CYAN,
            count=3,
            direction=math.radians(p.angle),
            spread=0.6,
            speed=(60, 220),
            life=(0.08, 0.2),
            size=(1, 2.5),
        )

    def _update_bullets(self, dt, collide):
        for b in self.bullets:
            b.update(dt)

        if collide:
            for b in self.bullets:
                if not b.alive:
                    continue
                for enemy in self.enemies:
                    if not enemy.alive:
                        continue
                    if seg_circle_hit(b.prev, b.pos, enemy.pos, enemy.radius + b.radius):
                        b.alive = False
                        self._hit_enemy(enemy, b.damage, b.pos)
                        break
                if not b.alive:
                    continue
                if self.boss is not None and not self.boss.dead:
                    if seg_circle_hit(b.prev, b.pos, self.boss.pos, self.boss.radius + b.radius):
                        b.alive = False
                        self._hit_boss(self.boss, b.damage, b.pos)

        self.bullets = [
            b for b in self.bullets
            if b.alive and -80 < b.pos.x < S.WIDTH + 80 and -80 < b.pos.y < S.HEIGHT + 80
        ]

    def _hit_enemy(self, enemy: Enemy, damage: float, at):
        enemy.hp -= damage
        enemy.flash = 0.08
        self.particles.burst(at, enemy.color, count=5, speed=(40, 200), life=(0.08, 0.28), size=(1, 2.4))
        audio.play("hit", 0.035)
        if enemy.hp <= 0 and enemy.alive:
            enemy.alive = False
            self._kill_enemy(enemy)

    def _kill_enemy(self, enemy: Enemy):
        self.chain += 1
        self.chain_timer = S.CHAIN_WINDOW
        self.score += int(enemy.score * self.chain_mult)
        self.kills += 1

        big = 1.8 if enemy.kind == "tank" else 1.0
        self.particles.burst(
            enemy.pos, enemy.color,
            count=int(16 * big), speed=(60, 330),
            life=(0.2, 0.65), size=(1, 3.6),
        )
        self.particles.burst(
            enemy.pos, S.WHITE, count=5, speed=(30, 190),
            life=(0.1, 0.3), size=(1, 2.2),
        )
        self.shake = max(self.shake, 6.5 if enemy.kind == "tank" else 3.5)
        audio.play("kill", 0.04)
        self._maybe_drop(enemy.pos)

    def _hit_boss(self, boss: Boss, damage: float, at):
        boss.hp -= damage
        boss.flash = 0.06
        self.particles.burst(at, boss.color, count=4, speed=(40, 220), life=(0.08, 0.26), size=(1, 2.6))
        audio.play("hit", 0.04)
        if boss.hp <= 0 and not boss.dead:
            self._kill_boss(boss)

    def _kill_boss(self, boss: Boss):
        boss.dead = True
        self.score += int(boss.score * self.chain_mult)
        self.kills += 1
        self.shake = 24.0
        self.hurt_flash = max(self.hurt_flash, 0.5)
        audio.play("kill", 0.0)

        for i in range(7):
            offset = from_angle(random.uniform(0, 360), random.uniform(5, 46))
            self.fx_queue.append(
                {"t": 0.04 + i * 0.075, "pos": boss.pos + offset, "color": S.MAGENTA,
                 "count": 18, "shake": 9.0}
            )
        self.particles.burst(boss.pos, S.WHITE, count=40, speed=(100, 520), life=(0.3, 0.9), size=(1.5, 4))
        self.particles.burst(boss.pos, S.MAGENTA, count=50, speed=(80, 480), life=(0.25, 0.8), size=(1, 4))

        # 必掉三个补给
        for i, kind in enumerate(("heal", "shield", random.choice(("rapid", "spread")))):
            self.powerups.append(Powerup(boss.pos + from_angle(random.uniform(0, 360), 20 + i * 16), kind))

        self.boss = None

    def _enemy_bullet_collisions(self):
        player = self.player
        for b in self.enemy_bullets:
            if not b.alive:
                continue
            if seg_circle_hit(b.prev, b.pos, player.pos, player.radius + b.radius):
                b.alive = False
                self.particles.burst(b.pos, b.color, count=7, speed=(40, 200), life=(0.1, 0.3), size=(1, 2.4))
                self._damage_player(b.damage)

    def _update_enemies(self, dt):
        for enemy in self.enemies:
            if enemy.alive:
                enemy.update(dt, self)
        if self.boss is not None and not self.boss.dead:
            self.boss.update(dt, self)

        # 接触伤害 + 软性推开
        if not self.player.dead:
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                delta = enemy.pos - self.player.pos
                reach = enemy.radius + self.player.radius
                dist = delta.length()
                if dist < reach:
                    n = delta / dist if dist > 0.001 else Vector2(1, 0)
                    enemy.pos += n * (reach - dist) * 0.65
                    enemy.vel += n * 70
                    self._damage_player(enemy.damage)

            if self.boss is not None and not self.boss.dead:
                delta = self.boss.pos - self.player.pos
                dist = delta.length()
                reach = self.boss.radius * 0.85 + self.player.radius
                if dist < reach:
                    self._damage_player(self.boss.damage * 0.8)

    def _damage_player(self, amount: float):
        result = self.player.take_damage(amount)
        if result == "none":
            return

        if result == "shield":
            audio.play("shield", 0.05)
            self.particles.burst(self.player.pos, S.CYAN, count=8, speed=(40, 180), life=(0.12, 0.3), size=(1, 2.5))
            self.shake = max(self.shake, 3.0)
        elif result == "shield_break":
            audio.play("shield", 0.05)
            audio.play("hurt", 0.1)
            self.particles.burst(self.player.pos, S.CYAN, count=26, speed=(80, 320), life=(0.2, 0.5), size=(1, 3.2))
            self.shake = max(self.shake, 8.0)
        else:
            self.hurt_flash = 1.0
            self.shake = max(self.shake, 9.0)
            audio.play("hurt", 0.12)
            self.particles.burst(self.player.pos, S.RED, count=14, speed=(60, 260), life=(0.15, 0.4), size=(1, 3))

        if result == "dead":
            self._on_player_death()

    def _on_player_death(self):
        self.death_timer = 1.6
        self.time_scale = 0.3
        self.shake = 22.0
        self.hurt_flash = 1.0
        audio.play("gameover")
        self.particles.burst(self.player.pos, S.CYAN, count=50, speed=(80, 480), life=(0.4, 1.0), size=(1.5, 4))
        self.particles.burst(self.player.pos, S.WHITE, count=30, speed=(60, 380), life=(0.3, 0.8), size=(1, 3))
        self.fx_queue.append({"t": 0.16, "pos": self.player.pos, "color": S.CYAN, "count": 30, "shake": 12.0})
        self.fx_queue.append({"t": 0.42, "pos": self.player.pos, "color": S.RED, "count": 24, "shake": 8.0})

    # ------------------------------------------------------------ 道具
    def _maybe_drop(self, pos):
        if random.random() > S.POWERUP_DROP_CHANCE:
            return
        hp_ratio = self.player.hp / self.player.max_hp
        weights = {
            "heal": 34 if hp_ratio < 0.55 else 14,
            "rapid": 25,
            "spread": 25,
            "shield": 22,
        }
        kinds = list(weights)
        kind = random.choices(kinds, weights=[weights[k] for k in kinds], k=1)[0]
        self.powerups.append(Powerup(pos, kind))

    def _collect_powerups(self):
        p = self.player
        for powerup in self.powerups:
            if not powerup.alive:
                continue
            if (powerup.pos - p.pos).length_squared() <= 30 * 30:
                powerup.alive = False
                self._apply_powerup(powerup)
                self.particles.burst(powerup.pos, powerup.color, count=16, speed=(50, 240), life=(0.15, 0.4), size=(1, 3))
                audio.play("pickup", 0.05)

    def _apply_powerup(self, powerup: Powerup):
        p = self.player
        kind = powerup.kind
        if kind == "heal":
            if p.hp < p.max_hp:
                p.hp = min(p.max_hp, p.hp + S.HEAL_AMOUNT)
            else:
                self.score += 100
        elif kind == "rapid":
            p.rapid_time = S.POWERUP_TIME
        elif kind == "spread":
            p.spread_time = S.POWERUP_TIME
        elif kind == "shield":
            p.shield = S.SHIELD_HP
            p.shield_time = S.SHIELD_TIME
        self.score += 25

    # ------------------------------------------------------------ 生成
    def _edge_spawn_pos(self) -> Vector2:
        side = random.randrange(4)
        margin = 48
        if side == 0:
            return Vector2(random.uniform(0, S.WIDTH), -margin)
        if side == 1:
            return Vector2(random.uniform(0, S.WIDTH), S.HEIGHT + margin)
        if side == 2:
            return Vector2(-margin, random.uniform(0, S.HEIGHT))
        return Vector2(S.WIDTH + margin, random.uniform(0, S.HEIGHT))

    def spawn_enemy(self, kind: str):
        self.spawn_enemy_at(kind, self._edge_spawn_pos())

    def spawn_enemy_at(self, kind: str, pos):
        if len(self.enemies) >= S.MAX_ENEMIES + 4:
            return
        self.enemies.append(Enemy(kind, pos, self.director.wave))
        self.particles.burst(pos, S.ENEMY_TYPES[kind]["color"], count=8, speed=(20, 120), life=(0.15, 0.4), size=(1, 2.5))

    def spawn_boss(self, wave: int):
        self.boss = Boss(wave)
        self.show_banner("WARNING", f"SENTINEL MK-{self.boss.index}", 2.4, S.RED)
        audio.play("boss")
        self.shake = max(self.shake, 9.0)

    def spawn_enemy_bullet(self, pos, vel, damage, color, radius=6):
        self.enemy_bullets.append(EnemyBullet(pos, vel, damage, color, radius=radius))

    @staticmethod
    def _on_screen(pos) -> bool:
        return -120 < pos.x < S.WIDTH + 120 and -120 < pos.y < S.HEIGHT + 120

    # ------------------------------------------------------------ 绘制
    def draw(self, surf: pygame.Surface):
        self.background.draw(surf, self.player.pos)
        for powerup in self.powerups:
            powerup.draw(surf)
        for bullet in self.enemy_bullets:
            bullet.draw(surf)
        for bullet in self.bullets:
            bullet.draw(surf)
        if self.boss is not None and not self.boss.dead:
            self.boss.draw(surf, self.time)
        for enemy in self.enemies:
            if enemy.alive:
                enemy.draw(surf, self.time)
        self.player.draw(surf, self.time)
        self.particles.draw(surf)


# ================================================================ 波次导演
class Director:
    def __init__(self, world: World):
        self.world = world
        self.wave = 0
        self.state = "idle"
        self.timer = 0.0
        self.spawn_timer = 0.0
        self.interval = 0.5
        self.queue: list[str] = []

    def start(self):
        self.begin_wave(1)

    def update(self, dt):
        if self.world.player.dead:
            return

        if self.state == "spawn":
            self.spawn_timer -= dt
            guard = 0
            while self.spawn_timer <= 0 and self.queue and guard < 8:
                guard += 1
                if len(self.world.enemies) >= S.MAX_ENEMIES:
                    self.spawn_timer = 0.2
                    break
                kind = self.queue.pop(0)
                if kind == "boss":
                    self.world.spawn_boss(self.wave)
                else:
                    self.world.spawn_enemy(kind)
                self.spawn_timer += self.interval
            if not self.queue:
                self.state = "clear_wait"
        elif self.state == "clear_wait":
            if not self.world.enemies and self.world.boss is None:
                self._on_cleared()
        elif self.state == "interlude":
            self.timer -= dt
            if self.timer <= 0:
                self.begin_wave(self.wave + 1)

    def begin_wave(self, wave: int):
        self.wave = wave
        self.queue = self._build_queue(wave)
        self.state = "spawn"
        self.spawn_timer = S.WAVE_FIRST_DELAY
        self.interval = max(S.WAVE_SPAWN_MIN, S.WAVE_SPAWN_BASE - 0.022 * wave)
        if wave % S.BOSS_EVERY != 0:
            self.world.show_banner(f"WAVE {wave:02d}", "HOSTILES INBOUND", 1.8, S.CYAN)

    def _build_queue(self, wave: int) -> list[str]:
        if wave % S.BOSS_EVERY == 0:
            minions = 4 + (wave // S.BOSS_EVERY) * 2
            return ["boss"] + [random.choice(("drone", "sprinter")) for _ in range(minions)]

        count = min(34, 6 + int(wave * 2.2))
        kinds = [("drone", 10.0)]
        if wave >= 2:
            kinds.append(("sprinter", 3.0 + wave * 0.3))
        if wave >= 3:
            kinds.append(("tank", 1.0 + wave * 0.12))
        if wave >= 4:
            kinds.append(("gunner", 1.0 + wave * 0.15))
        names = [k for k, _ in kinds]
        weights = [w for _, w in kinds]
        return random.choices(names, weights=weights, k=count)

    def _on_cleared(self):
        bonus = S.WAVE_CLEAR_BASE + self.wave * 25
        self.world.score += bonus
        p = self.world.player
        p.hp = min(p.max_hp, p.hp + 8)
        self.world.show_banner("WAVE CLEAR", f"+{bonus}  //  SECTOR SECURED", 2.0, S.GREEN)
        audio.play("wave")
        self.state = "interlude"
        self.timer = S.WAVE_INTERLUDE

    def remaining(self) -> int:
        count = len(self.queue) + len(self.world.enemies)
        if self.world.boss is not None:
            count += 1
        return count
