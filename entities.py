"""游戏实体：玩家、敌机、Boss、子弹、道具。"""
from __future__ import annotations

import math
import random

import pygame
from pygame.math import Vector2

import audio
import settings as S
from utils import (
    TAU,
    angle_of,
    clamp,
    draw_glow,
    from_angle,
    rotate_points,
    safe_norm,
    scale_color,
    translate_points,
)


def _poly(surf, pos, local, angle, fill, outline, width=2):
    pts = translate_points(rotate_points(local, angle), pos)
    if fill is not None:
        pygame.draw.polygon(surf, fill, pts)
    if outline is not None:
        pygame.draw.polygon(surf, outline, pts, width)


# ================================================================ 玩家
class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.vel = Vector2()
        self.angle = -90.0
        self.max_hp = S.PLAYER_MAX_HP
        self.hp = S.PLAYER_MAX_HP
        self.radius = S.PLAYER_RADIUS
        self.dead = False

        self.iframes = 0.0
        self.hit_flash = 0.0

        self.dash_time = 0.0
        self.dash_cd = 0.0
        self.dash_dir = Vector2(1, 0)

        self.fire_cd = 0.0
        self.rapid_time = 0.0
        self.spread_time = 0.0

        self.shield = 0.0
        self.shield_time = 0.0

        self._thruster_cd = 0.0

    @property
    def invulnerable(self) -> bool:
        return self.iframes > 0 or self.dash_time > 0

    # ------------------------------------------------------------ 更新
    def update(self, dt, move, aim_pos, want_dash, world):
        self.fire_cd = max(0.0, self.fire_cd - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.rapid_time = max(0.0, self.rapid_time - dt)
        self.spread_time = max(0.0, self.spread_time - dt)

        if self.shield_time > 0:
            self.shield_time -= dt
            if self.shield_time <= 0:
                self.shield_time = 0.0
                self.shield = 0.0

        if move.length_squared() > 1.0:
            move = move.normalize()

        # 冲刺
        if want_dash and self.dash_cd <= 0 and self.dash_time <= 0:
            direction = move if move.length_squared() > 0 else from_angle(self.angle)
            self.dash_dir = direction.normalize()
            self.dash_time = S.DASH_TIME
            self.dash_cd = S.DASH_COOLDOWN
            self.iframes = max(self.iframes, S.DASH_IFRAMES)
            audio.play("dash", 0.05)
            world.shake = max(world.shake, 3.0)
            world.particles.burst(
                self.pos - self.dash_dir * 8,
                S.CYAN,
                count=14,
                direction=math.atan2(-self.dash_dir.y, -self.dash_dir.x),
                spread=1.2,
                speed=(80, 260),
                life=(0.12, 0.38),
                size=(1, 3),
            )

        if self.dash_time > 0:
            self.dash_time -= dt
            self.pos += self.dash_dir * S.DASH_SPEED * dt
            world.particles.emit(
                self.pos + Vector2(random.uniform(-6, 6), random.uniform(-6, 6)),
                -self.dash_dir * random.uniform(60, 180),
                random.uniform(0.12, 0.3),
                random.uniform(1.2, 2.8),
                S.CYAN,
                4.0,
            )
        else:
            target = move * S.PLAYER_SPEED
            k = 1.0 - math.exp(-S.PLAYER_ACCEL * dt)
            self.vel += (target - self.vel) * k
            self.pos += self.vel * dt

            # 推进器粒子
            if self.vel.length_squared() > 60 * 60:
                self._thruster_cd -= dt
                if self._thruster_cd <= 0:
                    self._thruster_cd = 0.022
                    back = -safe_norm(self.vel)
                    side = Vector2(-back.y, back.x) * random.uniform(-28, 28)
                    world.particles.emit(
                        self.pos + back * random.uniform(8, 15),
                        back * random.uniform(40, 110) + side,
                        random.uniform(0.12, 0.28),
                        random.uniform(1, 2.2),
                        S.CYAN_DIM,
                        5.0,
                    )

        # 边界
        m = S.PLAY_MARGIN
        if self.pos.x < m:
            self.pos.x = m
            self.vel.x = max(0.0, self.vel.x)
        elif self.pos.x > S.WIDTH - m:
            self.pos.x = S.WIDTH - m
            self.vel.x = min(0.0, self.vel.x)
        if self.pos.y < m:
            self.pos.y = m
            self.vel.y = max(0.0, self.vel.y)
        elif self.pos.y > S.HEIGHT - m:
            self.pos.y = S.HEIGHT - m
            self.vel.y = min(0.0, self.vel.y)

        to_aim = aim_pos - self.pos
        if to_aim.length_squared() > 16:
            self.angle = angle_of(to_aim)

    # ------------------------------------------------------------ 受伤
    def take_damage(self, amount: float) -> str:
        """返回 none / shield / shield_break / hit / dead。"""
        if self.dead or self.invulnerable:
            return "none"

        if self.shield > 0:
            self.shield -= amount
            self.iframes = 0.2
            if self.shield <= 0:
                self.shield = 0.0
                self.shield_time = 0.0
                return "shield_break"
            return "shield"

        self.hp -= amount
        self.iframes = S.PLAYER_IFRAMES
        self.hit_flash = 0.18
        if self.hp <= 0:
            self.hp = 0.0
            self.dead = True
            return "dead"
        return "hit"

    # ------------------------------------------------------------ 绘制
    def draw(self, surf, t):
        if self.dead:
            return

        blink = self.iframes > 0 and int(t * 22) % 2 == 0
        core = S.CYAN_DIM if blink else S.CYAN

        draw_glow(surf, self.pos, 32, S.CYAN if not blink else (8, 34, 44))
        back = from_angle(self.angle + 180)
        draw_glow(surf, self.pos + back * 9, 12, (30, 90, 150))

        local = [(20, 0), (-11, -11), (-5, 0), (-11, 11)]
        fill = (10, 34, 44)
        if self.hit_flash > 0:
            fill = (120, 240, 255)
        _poly(surf, self.pos, local, self.angle, fill, core, 2)

        # 机头亮线
        p1 = self.pos + from_angle(self.angle, 13)
        p2 = self.pos + from_angle(self.angle, 1)
        pygame.draw.line(surf, S.WHITE, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 2)
        pygame.draw.circle(surf, S.WHITE, (int(self.pos.x), int(self.pos.y)), 2)

        # 护盾
        if self.shield > 0:
            ratio = clamp(self.shield / S.SHIELD_HP, 0.0, 1.0)
            r = 27 + math.sin(t * 7) * 1.5
            ring = S.CYAN if ratio > 0.35 else S.ORANGE
            draw_glow(surf, self.pos, 36, (10, 70, 90))
            pygame.draw.circle(surf, ring, (int(self.pos.x), int(self.pos.y)), int(r), 2)
            rect = pygame.Rect(int(self.pos.x - r), int(self.pos.y - r), int(r * 2), int(r * 2))
            pygame.draw.arc(
                surf,
                S.WHITE,
                rect,
                -math.pi / 2,
                -math.pi / 2 + TAU * max(0.01, ratio - 0.01),
                2,
            )


# ================================================================ 子弹
class Bullet:
    def __init__(self, pos, vel, damage, radius=None, life=None, color=None):
        self.pos = Vector2(pos)
        self.prev = Vector2(pos)
        self.vel = Vector2(vel)
        self.damage = damage
        self.radius = radius or S.BULLET_RADIUS
        self.life = life if life is not None else S.BULLET_LIFE
        self.color = color or S.CYAN
        self.alive = True

    def update(self, dt):
        self.prev = self.pos.copy()
        self.pos += self.vel * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, surf):
        tail = self.pos - safe_norm(self.vel) * 15
        draw_glow(surf, self.pos, 10, self.color)
        pygame.draw.line(
            surf,
            scale_color(self.color, 0.7),
            (int(tail.x), int(tail.y)),
            (int(self.pos.x), int(self.pos.y)),
            2,
        )
        pygame.draw.circle(surf, S.WHITE, (int(self.pos.x), int(self.pos.y)), 2)


class EnemyBullet:
    def __init__(self, pos, vel, damage=8, color=None, radius=6, life=6.0):
        self.pos = Vector2(pos)
        self.prev = Vector2(pos)
        self.vel = Vector2(vel)
        self.damage = damage
        self.color = color or S.ORANGE
        self.radius = radius
        self.life = life
        self.alive = True

    def update(self, dt):
        self.prev = self.pos.copy()
        self.pos += self.vel * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, surf):
        draw_glow(surf, self.pos, 15, self.color)
        pygame.draw.circle(surf, scale_color(self.color, 0.5), (int(self.pos.x), int(self.pos.y)), self.radius)
        pygame.draw.circle(surf, S.WHITE, (int(self.pos.x), int(self.pos.y)), max(1, self.radius - 4))


# ================================================================ 普通敌人
_SHAPES = {
    "tri": [(1.15, 0), (-0.8, -0.85), (-0.45, 0), (-0.8, 0.85)],
    "diamond": [(1.1, 0), (0, -0.72), (-0.9, 0), (0, 0.72)],
    "hex": [(1.0, 0), (0.5, -0.87), (-0.5, -0.87), (-1.0, 0), (-0.5, 0.87), (0.5, 0.87)],
}


class Enemy:
    def __init__(self, kind: str, pos, wave: int):
        cfg = S.ENEMY_TYPES[kind]
        self.kind = kind
        self.pos = Vector2(pos)
        self.vel = Vector2()
        self.radius = float(cfg["radius"])
        self.color = cfg["color"]
        self.shape = _SHAPES[cfg["shape"]]
        self.damage = cfg["damage"] * min(1.5, 1.0 + 0.02 * (wave - 1))
        self.score = int(cfg["score"])
        self.mass = cfg["mass"]

        hp_scale = 1.0 + S.ENEMY_HP_GROWTH * (wave - 1) + S.ENEMY_HP_QUAD * (wave - 1) ** 2
        self.max_hp = cfg["hp"] * hp_scale
        self.hp = self.max_hp
        self.speed = cfg["speed"] * min(S.ENEMY_SPEED_CAP, 1.0 + S.ENEMY_SPEED_GROWTH * (wave - 1))

        self.angle = 0.0
        self.spin = 0.0
        self.flash = 0.0
        self.alive = True
        self.wobble = random.uniform(0, TAU)
        self.fire_interval = cfg.get("fire_interval", 2.0) / min(1.8, 1.0 + 0.035 * wave)
        self.fire_cd = random.uniform(0.8, self.fire_interval + 0.6)
        self.bullet_speed = cfg.get("bullet_speed", 300)

    def update(self, dt, world):
        self.flash = max(0.0, self.flash - dt)
        player = world.player
        if player.dead:
            self.vel *= math.exp(-1.0 * dt)
            self.pos += self.vel * dt
            return

        to_player = player.pos - self.pos
        dist = to_player.length()
        direction = to_player / dist if dist > 0.001 else Vector2(1, 0)
        perpendicular = Vector2(-direction.y, direction.x)

        if self.kind == "gunner":
            desired_dist = 270.0
            if dist > desired_dist + 40:
                desired = direction
            elif dist < desired_dist - 50:
                desired = -direction
            else:
                desired = perpendicular * math.sin(world.time * 2.2 + self.wobble)
            desired = desired + direction * 0.12
        elif self.kind == "sprinter":
            desired = direction + perpendicular * math.sin(world.time * 7.0 + self.wobble) * 0.5
        else:
            desired = direction + perpendicular * math.sin(world.time * 1.7 + self.wobble) * 0.2

        # 简单分离，避免叠成一坨
        separation = Vector2()
        for other in world.enemies:
            if other is self or not other.alive:
                continue
            delta = self.pos - other.pos
            dist2 = delta.length_squared()
            reach = self.radius + other.radius + 8
            if 1e-6 < dist2 < reach * reach:
                d = math.sqrt(dist2)
                separation += delta / d * (1.0 - d / reach)
        desired += separation * 1.7

        desired = safe_norm(desired)
        target_vel = desired * self.speed
        k = 1.0 - math.exp(-6.0 * dt)
        self.vel += (target_vel - self.vel) * k
        self.pos += self.vel * dt

        self.angle = angle_of(to_player)
        if self.kind == "tank":
            self.spin += 36.0 * dt

        # 远程敌人开火
        if self.kind == "gunner" and dist < 760:
            self.fire_cd -= dt
            if self.fire_cd <= 0:
                self.fire_cd = self.fire_interval * random.uniform(0.85, 1.2)
                aim = angle_of(to_player) + random.uniform(-5.0, 5.0)
                world.spawn_enemy_bullet(
                    self.pos,
                    from_angle(aim, self.bullet_speed),
                    max(6.0, self.damage * 0.8),
                    S.GREEN,
                    radius=5,
                )
                world.particles.burst(
                    self.pos + from_angle(aim, self.radius),
                    S.GREEN,
                    count=5,
                    direction=math.radians(aim),
                    spread=0.8,
                    speed=(40, 140),
                    life=(0.1, 0.25),
                    size=(1, 2),
                )

    def draw(self, surf, t):
        pulse = 1.0 + 0.04 * math.sin(t * 4.0 + self.wobble)
        color = S.WHITE if self.flash > 0 else self.color

        draw_glow(surf, self.pos, int(self.radius * 2.3), self.color)

        r = self.radius * pulse
        local = [(x * r, y * r) for x, y in self.shape]
        angle = self.spin if self.kind == "tank" else self.angle
        fill = S.WHITE if self.flash > 0 else scale_color(self.color, 0.18)
        _poly(surf, self.pos, local, angle, fill, color, 2)

        # 内芯
        if self.kind == "tank":
            pygame.draw.circle(
                surf, scale_color(color, 0.9), (int(self.pos.x), int(self.pos.y)), int(self.radius * 0.34), 2
            )
        elif self.kind == "gunner":
            tip = self.pos + from_angle(self.angle, self.radius * 0.5)
            pygame.draw.circle(surf, S.WHITE, (int(tip.x), int(tip.y)), 3)
        else:
            pygame.draw.circle(
                surf, scale_color(color, 0.8), (int(self.pos.x), int(self.pos.y)), max(2, int(self.radius * 0.18))
            )

        # 受伤血条
        if self.hp < self.max_hp:
            ratio = clamp(self.hp / self.max_hp, 0.0, 1.0)
            w = int(self.radius * 1.9)
            h = 3
            x = int(self.pos.x - w / 2)
            y = int(self.pos.y - self.radius - 10)
            pygame.draw.rect(surf, (24, 30, 46), (x, y, w, h))
            pygame.draw.rect(surf, color, (x, y, int(w * ratio), h))


# ================================================================ Boss
class Boss:
    def __init__(self, wave: int):
        self.wave = wave
        index = max(1, wave // S.BOSS_EVERY)
        self.max_hp = S.BOSS_HP_BASE + S.BOSS_HP_STEP * (index - 1)
        self.hp = self.max_hp
        self.pos = Vector2(S.CENTER.x, -100)
        self.vel = Vector2()
        self.radius = S.BOSS_RADIUS
        self.angle = 90.0
        self.spin = 0.0
        self.time = 0.0
        self.entering = True
        self.enraged = False
        self.flash = 0.0
        self.dead = False
        self.damage = 26.0
        self.score = S.BOSS_SCORE + wave * 60
        self.index = index

        self.ring_cd = 2.4
        self.aim_cd = 1.4
        self.summon_cd = 7.0

    @property
    def color(self):
        return S.RED if self.enraged else S.MAGENTA

    def update(self, dt, world):
        self.time += dt
        self.flash = max(0.0, self.flash - dt)

        if self.entering:
            target = Vector2(S.CENTER.x, 155)
            delta = target - self.pos
            step = min(230.0 * dt, delta.length())
            if delta.length_squared() > 1e-6:
                self.pos += delta.normalize() * step
            self.angle = angle_of(world.player.pos - self.pos)
            if delta.length() < 6:
                self.entering = False
            return

        self.spin += dt * (115.0 if self.enraged else 55.0)
        tx = S.CENTER.x + math.sin(self.time * 0.7) * 320
        ty = 165 + math.sin(self.time * 1.25) * 32
        target = Vector2(tx, ty)
        k = 1.0 - math.exp(-1.7 * dt)
        self.pos += (target - self.pos) * k
        self.angle = angle_of(world.player.pos - self.pos)

        if world.player.dead:
            return

        # 狂暴
        if not self.enraged and self.hp <= self.max_hp * 0.4:
            self.enraged = True
            world.show_banner("ENRAGED", "SENTINEL OVERDRIVE", 1.8, S.RED)
            world.shake = max(world.shake, 14)
            audio.play("boss")

        self.ring_cd -= dt
        if self.ring_cd <= 0:
            self.ring_cd = 1.85 if self.enraged else 2.65
            self._fire_ring(world)

        self.aim_cd -= dt
        if self.aim_cd <= 0:
            self.aim_cd = 1.0 if self.enraged else 1.5
            self._fire_aimed(world)

        self.summon_cd -= dt
        if self.summon_cd <= 0:
            self.summon_cd = 5.5 if self.enraged else 7.5
            for i in range(3):
                ang = self.spin + TAU * i / 3
                offset = from_angle(ang, self.radius + 58)
                world.spawn_enemy_at("drone", self.pos + offset)

    def _fire_ring(self, world):
        count = 22 if self.enraged else 16
        speed = 238 if self.enraged else 205
        for i in range(count):
            ang = self.spin * 0.8 + TAU * i / count
            origin = self.pos + from_angle(ang, self.radius + 6)
            world.spawn_enemy_bullet(origin, from_angle(ang, speed), 9.0, S.ORANGE, radius=6)
        world.particles.burst(
            self.pos, S.ORANGE, count=12, speed=(60, 220), life=(0.15, 0.4), size=(1, 2.6)
        )

    def _fire_aimed(self, world):
        base = angle_of(world.player.pos - self.pos)
        spread = (-0.18, 0.0, 0.18)
        for off in spread:
            ang = base + math.degrees(off)
            world.spawn_enemy_bullet(self.pos, from_angle(ang, 355), 11.0, S.RED, radius=6)
        audio.play("hit", 0.08)

    def draw(self, surf, t):
        color = S.WHITE if self.flash > 0 else self.color
        draw_glow(surf, self.pos, 104, self.color)

        # 外层六边形
        local_outer = [(math.cos(TAU * i / 6) * self.radius * 1.25,
                        math.sin(TAU * i / 6) * self.radius * 1.25) for i in range(6)]
        _poly(surf, self.pos, local_outer, self.spin, scale_color(self.color, 0.06), color, 3)

        # 内层六边形（反向旋转）
        local_inner = [(math.cos(TAU * i / 6) * self.radius * 0.85,
                        math.sin(TAU * i / 6) * self.radius * 0.85) for i in range(6)]
        _poly(surf, self.pos, local_inner, -self.spin * 1.6, scale_color(self.color, 0.12), color, 2)

        # 核心
        core_r = self.radius * 0.46 + math.sin(t * 4) * 3
        draw_glow(surf, self.pos, int(core_r * 1.7), S.WHITE)
        pts = translate_points(
            rotate_points([(core_r, 0), (-core_r * 0.6, -core_r * 0.8), (-core_r * 0.6, core_r * 0.8)],
                          -self.spin * 2.2),
            self.pos,
        )
        pygame.draw.polygon(surf, scale_color(self.color, 0.75), pts)
        pygame.draw.polygon(surf, S.WHITE, pts, 2)

        # 两侧弧线
        r = self.radius * 1.55
        rect = pygame.Rect(int(self.pos.x - r), int(self.pos.y - r), int(r * 2), int(r * 2))
        start = self.spin * 0.03
        pygame.draw.arc(surf, scale_color(color, 0.6), rect, start, start + 1.1, 3)
        pygame.draw.arc(surf, scale_color(color, 0.6), rect, start + math.pi, start + math.pi + 1.1, 3)


# ================================================================ 道具
class Powerup:
    def __init__(self, pos, kind: str):
        cfg = S.POWERUPS[kind]
        self.kind = kind
        self.color = cfg["color"]
        self.label = cfg["label"]
        self.pos = Vector2(pos)
        self.vel = from_angle(random.uniform(0, 360), random.uniform(30, 90))
        self.t = random.uniform(0, TAU)
        self.life = S.POWERUP_LIFETIME
        self.radius = 13
        self.alive = True

    def update(self, dt, player):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return

        if not player.dead:
            to_player = player.pos - self.pos
            d = to_player.length()
            if 0 < d < 150:
                self.vel += safe_norm(to_player) * 900.0 * dt
        self.vel *= math.exp(-2.2 * dt)
        self.pos += self.vel * dt

        m = 24
        self.pos.x = clamp(self.pos.x, m, S.WIDTH - m)
        self.pos.y = clamp(self.pos.y, m, S.HEIGHT - m)

    def draw(self, surf):
        if self.life < 3.0 and int(self.life * 9) % 2 == 0:
            return
        yoff = math.sin(self.t * 3.0) * 3
        pos = Vector2(self.pos.x, self.pos.y + yoff)
        pulse = 1.0 + 0.05 * math.sin(self.t * 5.0)
        r = self.radius * pulse

        draw_glow(surf, pos, 28, self.color)
        center = (int(pos.x), int(pos.y))
        pygame.draw.circle(surf, scale_color(self.color, 0.14), center, int(r))
        pygame.draw.circle(surf, self.color, center, int(r), 2)
        # 旋转的短刻度，和敌人多边形成像区分开
        for i in range(3):
            ang = math.degrees(self.t * 2.4 + TAU * i / 3)
            p1 = pos + from_angle(ang, r + 3)
            p2 = pos + from_angle(ang, r + 8)
            pygame.draw.line(
                surf, self.color, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 2
            )

        c = self.color
        x, y = int(pos.x), int(pos.y)
        if self.kind == "heal":
            pygame.draw.rect(surf, c, (x - 2, y - 7, 4, 14))
            pygame.draw.rect(surf, c, (x - 7, y - 2, 14, 4))
        elif self.kind == "rapid":
            bolt = [(x + 2, y - 8), (x - 5, y + 1), (x - 1, y + 1), (x - 2, y + 8), (x + 5, y - 1), (x + 1, y - 1)]
            pygame.draw.polygon(surf, c, bolt)
        elif self.kind == "spread":
            for dx, dy in ((-7, -6), (0, 0), (-7, 6)):
                pygame.draw.line(surf, c, (x - 2, y), (x + 6 + dx // 2, y + dy), 2)
        elif self.kind == "shield":
            pygame.draw.circle(surf, c, (x, y), 6, 2)
            pygame.draw.circle(surf, c, (x, y), 2)
