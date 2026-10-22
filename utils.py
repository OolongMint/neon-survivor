"""通用工具：数学、发光缓存、粒子、星空/网格背景。"""
from __future__ import annotations

import math
import random

import pygame
from pygame.math import Vector2

import settings as S

# ---------------------------------------------------------------- 数学
TAU = math.tau


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def scale_color(c, f):
    """按亮度缩放颜色，结果始终合法。"""
    return (
        int(clamp(c[0] * f, 0, 255)),
        int(clamp(c[1] * f, 0, 255)),
        int(clamp(c[2] * f, 0, 255)),
    )


def angle_of(vec: Vector2) -> float:
    return math.degrees(math.atan2(vec.y, vec.x))


def from_angle(deg: float, length: float = 1.0) -> Vector2:
    r = math.radians(deg)
    return Vector2(math.cos(r) * length, math.sin(r) * length)


def safe_norm(vec: Vector2) -> Vector2:
    if vec.length_squared() < 1e-6:
        return Vector2()
    return vec.normalize()


def seg_circle_hit(p1: Vector2, p2: Vector2, center: Vector2, radius: float) -> bool:
    """线段与圆是否相交（用于高速子弹，避免穿透）。"""
    seg = p2 - p1
    l2 = seg.length_squared()
    if l2 <= 1e-9:
        return (center - p1).length_squared() <= radius * radius
    t = clamp((center - p1).dot(seg) / l2, 0.0, 1.0)
    closest = p1 + seg * t
    return (center - closest).length_squared() <= radius * radius


def rotate_points(points, angle_deg):
    """把局部坐标点旋转后返回整数像素坐标。"""
    r = math.radians(angle_deg)
    cos_a, sin_a = math.cos(r), math.sin(r)
    out = []
    for x, y in points:
        out.append((int(x * cos_a - y * sin_a), int(x * sin_a + y * cos_a)))
    return out


def translate_points(points, pos):
    return [(int(pos[0] + x), int(pos[1] + y)) for x, y in points]


# ---------------------------------------------------------------- 发光
_GLOW_CACHE: dict = {}


def glow_surface(radius: int, color) -> pygame.Surface:
    """生成径向渐变光晕（黑底，配合 BLEND_ADD 使用）。"""
    radius = max(2, int(radius))
    color = (int(color[0]), int(color[1]), int(color[2]))
    key = (radius, color)
    cached = _GLOW_CACHE.get(key)
    if cached is not None:
        return cached

    size = radius * 2 + 2
    surf = pygame.Surface((size, size))
    surf.fill((0, 0, 0))
    steps = int(clamp(radius // 2, 8, 64))
    for i in range(steps, 0, -1):
        t = i / steps                      # 1 = 最外圈
        f = (1.0 - t) ** 2.0               # 中心亮、边缘暗
        c = (int(color[0] * f), int(color[1] * f), int(color[2] * f))
        pygame.draw.circle(surf, c, (size // 2, size // 2), max(1, int(radius * t)))
    _GLOW_CACHE[key] = surf
    return surf


def draw_glow(surf: pygame.Surface, pos, radius: int, color):
    g = glow_surface(radius, color)
    surf.blit(
        g,
        (int(pos[0] - g.get_width() / 2), int(pos[1] - g.get_height() / 2)),
        special_flags=pygame.BLEND_ADD,
    )


# ---------------------------------------------------------------- 粒子
class _Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "size", "color", "drag")

    def __init__(self, pos, vel, life, size, color, drag):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.size = float(size)
        self.color = color
        self.drag = drag


class Particles:
    """轻量粒子池，普通绘制即可获得火花效果。"""

    def __init__(self, limit: int = 1100):
        self.items: list[_Particle] = []
        self.limit = limit

    def clear(self):
        self.items.clear()

    def emit(self, pos, vel, life, size, color, drag=3.0):
        if len(self.items) >= self.limit:
            return
        self.items.append(_Particle(pos, vel, life, size, color, drag))

    def burst(
        self,
        pos,
        color,
        count=12,
        speed=(60, 260),
        life=(0.18, 0.55),
        size=(1, 3),
        drag=3.5,
        direction=None,
        spread=math.tau,
    ):
        for _ in range(count):
            if direction is None:
                ang = random.uniform(0, TAU)
            else:
                ang = direction + random.uniform(-spread / 2, spread / 2)
            spd = random.uniform(*speed)
            vel = from_angle(math.degrees(ang), spd)
            self.emit(
                pos,
                vel,
                random.uniform(*life),
                random.uniform(*size),
                color,
                drag,
            )

    def trail(self, pos, color, count=1, spread=0.4, speed=(20, 80), life=(0.15, 0.4), size=(1, 2.4)):
        for _ in range(count):
            ang = random.uniform(0, TAU)
            spd = random.uniform(*speed)
            self.emit(pos, from_angle(math.degrees(ang), spd),
                      random.uniform(*life), random.uniform(*size), color, 4.0)

    def update(self, dt):
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.pos += p.vel * dt
            if p.drag:
                p.vel *= math.exp(-p.drag * dt)
            alive.append(p)
        self.items = alive

    def draw(self, surf):
        for p in self.items:
            t = clamp(p.life / p.max_life, 0.0, 1.0)
            color = scale_color(p.color, 0.35 + 0.65 * t)
            r = max(1, int(round(p.size * (0.3 + 0.7 * t))))
            pygame.draw.circle(surf, color, (int(p.pos.x), int(p.pos.y)), r)


# ---------------------------------------------------------------- 背景
class Background:
    """深空渐变 + 星点 + 霓虹网格。只在 init 时烘焙昂贵的光晕。"""

    def __init__(self):
        self.time = 0.0
        self.stars = []
        for _ in range(110):
            self.stars.append(
                {
                    "x": random.uniform(0, S.WIDTH),
                    "y": random.uniform(0, S.HEIGHT),
                    "speed": random.uniform(4, 22),
                    "size": random.choice((1, 1, 1, 2)),
                    "phase": random.uniform(0, TAU),
                    "freq": random.uniform(0.4, 1.6),
                    "base": random.uniform(0.18, 0.7),
                }
            )
        self.gradient = self._build_gradient()

    def _build_gradient(self) -> pygame.Surface:
        surf = pygame.Surface((S.WIDTH, S.HEIGHT))
        for y in range(S.HEIGHT):
            t = y / max(1, S.HEIGHT - 1)
            col = lerp_color(S.BG_TOP, S.BG_BOTTOM, t)
            pygame.draw.line(surf, col, (0, y), (S.WIDTH, y))
        # 两团极暗的星云，直接烘焙进背景，零逐帧成本
        for pos, radius, color in (
            ((S.WIDTH * 0.22, S.HEIGHT * 0.30), 330, S.NEBULA_A),
            ((S.WIDTH * 0.80, S.HEIGHT * 0.72), 300, S.NEBULA_B),
        ):
            g = glow_surface(radius, color)
            surf.blit(
                g,
                (int(pos[0] - g.get_width() / 2), int(pos[1] - g.get_height() / 2)),
                special_flags=pygame.BLEND_ADD,
            )
        return surf

    def update(self, dt, focus=None):
        self.time += dt
        for st in self.stars:
            st["y"] += st["speed"] * dt
            if st["y"] > S.HEIGHT + 2:
                st["y"] = -2
                st["x"] = random.uniform(0, S.WIDTH)

    def draw(self, surf: pygame.Surface, focus=None):
        if focus is None:
            focus = S.CENTER
        surf.blit(self.gradient, (0, 0))

        # 星点（带闪烁）
        for st in self.stars:
            glow = 0.6 + 0.4 * math.sin(self.time * st["freq"] + st["phase"])
            b = st["base"] * glow
            col = (int(120 * b), int(160 * b), int(210 * b))
            if col[0] or col[1] or col[2]:
                surf.fill(col, (int(st["x"]), int(st["y"]), st["size"], st["size"]))

        # 网格：随玩家位置产生轻微视差
        off_x = -(focus.x - S.CENTER.x) * 0.06
        off_y = -(focus.y - S.CENTER.y) * 0.06
        step = 80
        start_x = int(off_x) % step - step
        start_y = int(off_y) % step - step

        x = start_x
        while x < S.WIDTH + step:
            # 用“世界坐标”判定主次线，避免玩家移动时闪烁
            major = int(round((x - off_x) / step)) % 4 == 0
            col = S.GRID_MAJOR if major else S.GRID_MINOR
            pygame.draw.line(surf, col, (x, 0), (x, S.HEIGHT), 1)
            x += step

        y = start_y
        while y < S.HEIGHT + step:
            major = int(round((y - off_y) / step)) % 4 == 0
            col = S.GRID_MAJOR if major else S.GRID_MINOR
            pygame.draw.line(surf, col, (0, y), (S.WIDTH, y), 1)
            y += step
