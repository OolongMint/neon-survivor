"""界面绘制：字体、HUD、标题、暂停、结算、横幅与扫描线。"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pygame

import settings as S
from utils import TAU, clamp, scale_color


def _font_path(names):
    """优先直接找 Windows 字体文件；match_font 在部分系统上会崩溃，故兜底 try。"""
    base = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in names:
        path = base / name
        if path.is_file():
            return str(path)
    for name in names:
        try:
            found = pygame.font.match_font(Path(name).stem)
        except Exception:
            found = None
        if found:
            return found
    return None


class UI:
    def __init__(self):
        self.mono_path = _font_path(["consolab.ttf", "consola.ttf", "arialbd.ttf"])
        self.display_path = _font_path(["bahnschrift.ttf", "arialbd.ttf", "segoeuib.ttf"])
        self.cjk_path = _font_path(["msyhbd.ttc", "msyh.ttc", "simhei.ttf", "simsun.ttc"])
        self.has_cjk = self.cjk_path is not None

        self._fonts = {}
        self._text_cache = {}
        self._panel_cache = {}

        self.scanlines = self._make_scanlines()
        self.vignette = self._make_vignette()
        self.red_overlay = pygame.Surface((S.WIDTH, S.HEIGHT))
        self.red_overlay.fill(S.RED)
        self.black_overlay = pygame.Surface((S.WIDTH, S.HEIGHT))
        self.black_overlay.fill((0, 0, 0))

        # 标题装饰用暗色
        self._title_hex = (10, 34, 52)

    # ------------------------------------------------------------ 资源
    def _make_scanlines(self):
        surf = pygame.Surface((S.WIDTH, S.HEIGHT), pygame.SRCALPHA)
        for y in range(0, S.HEIGHT, 3):
            pygame.draw.line(surf, (0, 0, 0, 24), (0, y), (S.WIDTH, y))
        return surf

    def _make_vignette(self):
        small = pygame.Surface((64, 36), pygame.SRCALPHA)
        for y in range(36):
            for x in range(64):
                dx = (x + 0.5) / 64 * 2 - 1
                dy = (y + 0.5) / 36 * 2 - 1
                d = math.hypot(dx, dy)
                a = int(clamp((d - 0.55) / 0.62, 0, 1) ** 1.4 * 165)
                small.set_at((x, y), (0, 0, 0, a))
        return pygame.transform.smoothscale(small, (S.WIDTH, S.HEIGHT))

    def font(self, kind, size):
        key = (kind, size)
        cached = self._fonts.get(key)
        if cached is not None:
            return cached
        path = {"mono": self.mono_path, "display": self.display_path, "cjk": self.cjk_path}.get(kind)
        if path is None:
            path = self.mono_path
        try:
            f = pygame.font.Font(path, size) if path else pygame.font.Font(None, size)
        except Exception:
            f = pygame.font.Font(None, size)
        self._fonts[key] = f
        return f

    def text(self, text, kind, size, color):
        key = (text, kind, size, color)
        cached = self._text_cache.get(key)
        if cached is not None:
            return cached
        img = self.font(kind, size).render(text, True, color)
        if len(self._text_cache) > 700:
            self._text_cache.clear()
        self._text_cache[key] = img
        return img

    def blit_text(self, surf, text, kind, size, color, pos, anchor="center", alpha=255):
        img = self.text(text, kind, size, color)
        if alpha < 255:
            img = img.copy()
            img.set_alpha(alpha)
        rect = img.get_rect()
        setattr(rect, anchor, (int(pos[0]), int(pos[1])))
        surf.blit(img, rect)

    def L(self, zh, en):
        return zh if self.has_cjk else en

    def panel(self, w, h, alpha=180, border=S.CYAN_DIM):
        key = (w, h, alpha, border)
        cached = self._panel_cache.get(key)
        if cached is not None:
            return cached
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((7, 11, 24, alpha))
        pygame.draw.rect(surf, (*border, 165), surf.get_rect(), 1)
        length = 16
        for x, y, dx, dy in ((0, 0, 1, 1), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)):
            pygame.draw.line(surf, (*S.CYAN, 190), (x, y), (x + dx * length, y), 2)
            pygame.draw.line(surf, (*S.CYAN, 190), (x, y), (x, y + dy * length), 2)
        self._panel_cache[key] = surf
        return surf

    # ------------------------------------------------------------ HUD
    def draw_hud(self, screen, world, mouse_pos, best, t, muted, show_crosshair=True):
        p = world.player

        # 受伤 / 低血量红色边缘（画在 HUD 下方，避免染色面板）
        red_alpha = 0
        if world.hurt_flash > 0:
            red_alpha = int(72 * world.hurt_flash)
        if not p.dead and p.hp / p.max_hp < 0.28:
            red_alpha = max(red_alpha, int(24 + 16 * math.sin(t * 6)))
        if red_alpha > 0:
            self.red_overlay.set_alpha(red_alpha)
            screen.blit(self.red_overlay, (0, 0))

        self._draw_hp(screen, p, t)
        self._draw_score(screen, world, best, t)
        self._draw_wave(screen, world)
        if world.boss is not None and not world.boss.dead and not p.dead:
            self._draw_boss_bar(screen, world.boss, t)
        self._draw_powerups(screen, p, t)
        self._draw_dash(screen, p, t)

        if world.banner is not None:
            self._draw_banner(screen, world.banner)

        if muted:
            self.blit_text(screen, "MUTED", "mono", 12, S.DIM, (S.WIDTH - 36, 178), anchor="midright")

        if show_crosshair:
            self._draw_crosshair(screen, mouse_pos, t)

    def _draw_hp(self, screen, p, t):
        panel = self.panel(360, 104, 150)
        screen.blit(panel, (20, 18))
        self.blit_text(screen, "HULL INTEGRITY", "mono", 12, S.DIM, (36, 34), anchor="midleft")

        ratio = clamp(p.hp / p.max_hp, 0.0, 1.0)
        if ratio > 0.55:
            color = S.GREEN
        elif ratio > 0.28:
            color = S.YELLOW
        else:
            color = S.RED

        rect = pygame.Rect(36, 48, 328, 16)
        self._bar(screen, rect, ratio, color, ticks=16)
        self.blit_text(
            screen, f"{int(p.hp):03d}", "mono", 13,
            S.WHITE, (356, 57), anchor="midright",
        )

        shield_rect = pygame.Rect(36, 74, 328, 6)
        if p.shield > 0:
            self._bar(screen, shield_rect, clamp(p.shield / S.SHIELD_HP, 0, 1), S.CYAN, ticks=0)
            self.blit_text(
                screen, "SHIELD", "mono", 10, S.CYAN,
                (36, 94), anchor="midleft",
            )
            self.blit_text(
                screen, f"{int(p.shield):02d}", "mono", 10, S.CYAN,
                (364, 94), anchor="midright",
            )
        else:
            self.blit_text(screen, "SHIELD OFFLINE", "mono", 10, S.GRID_MAJOR, (36, 94), anchor="midleft")

    def _draw_score(self, screen, world, best, t):
        panel = self.panel(300, 104, 150)
        screen.blit(panel, (S.WIDTH - 320, 18))
        self.blit_text(screen, "SCORE", "mono", 12, S.DIM, (S.WIDTH - 36, 34), anchor="midright")
        self.blit_text(
            screen, f"{world.score:07d}", "mono", 30,
            S.WHITE, (S.WIDTH - 36, 58), anchor="midright",
        )
        self.blit_text(
            screen, f"BEST {best:07d}", "mono", 12,
            S.SCORE_GOLD, (S.WIDTH - 36, 88), anchor="midright",
        )

        if world.chain >= S.CHAIN_STEP and world.chain_timer > 0:
            pulse = 1 + 0.06 * math.sin(t * 10)
            mult = world.chain_mult
            color = S.SCORE_GOLD if mult >= 3 else S.YELLOW
            self.blit_text(
                screen, f"CHAIN {world.chain:02d}   x{mult}", "mono",
                int(15 * pulse) + 3, color,
                (S.WIDTH - 36, 142), anchor="midright",
            )

    def _draw_wave(self, screen, world):
        panel = self.panel(240, 92, 150)
        screen.blit(panel, (S.WIDTH // 2 - 120, 18))
        self.blit_text(
            screen, f"WAVE {world.director.wave:02d}", "mono", 24,
            S.WHITE, (S.WIDTH // 2, 46),
        )
        remaining = world.director.remaining()
        color = S.RED if world.boss is not None else S.DIM
        self.blit_text(
            screen, f"THREAT {remaining:03d}", "mono", 11,
            color, (S.WIDTH // 2, 74),
        )

    def _draw_boss_bar(self, screen, boss, t):
        # 底部居中的 Boss 血条，避开顶部 HUD 与 Boss 本体
        x = S.WIDTH // 2 - 350
        w = 700
        y = S.HEIGHT - 120
        color = boss.color
        name = f"SENTINEL MK-{boss.index}"
        self.blit_text(screen, name, "mono", 13, color, (x, y), anchor="midleft")
        if boss.enraged:
            self.blit_text(screen, "// ENRAGED", "mono", 11, S.RED, (x + 190, y), anchor="midleft")
        self.blit_text(
            screen, f"{int(boss.hp)} / {int(boss.max_hp)}", "mono", 11,
            S.DIM, (x + w, y), anchor="midright",
        )
        rect = pygame.Rect(x, y + 14, w, 10)
        self._bar(screen, rect, clamp(boss.hp / boss.max_hp, 0, 1), color, ticks=28)
        pygame.draw.rect(screen, scale_color(color, 0.35), rect.inflate(6, 6), 1)

    def _draw_powerups(self, screen, p, t):
        active = []
        if p.rapid_time > 0:
            active.append(("rapid", p.rapid_time / S.POWERUP_TIME))
        if p.spread_time > 0:
            active.append(("spread", p.spread_time / S.POWERUP_TIME))
        if p.shield > 0:
            active.append(("shield", clamp(p.shield / S.SHIELD_HP, 0, 1)))

        for i, (kind, ratio) in enumerate(active[:3]):
            x = 20 + i * 132
            y = S.HEIGHT - 76
            panel = self.panel(124, 54, 150)
            screen.blit(panel, (x, y))
            color = S.POWERUPS[kind]["color"]
            pygame.draw.circle(screen, color, (x + 20, y + 21), 6, 2)
            pygame.draw.circle(screen, color, (x + 20, y + 21), 2)
            self.blit_text(
                screen, S.POWERUPS[kind]["label"], "mono", 12,
                color, (x + 34, y + 15), anchor="midleft",
            )
            pygame.draw.rect(screen, (14, 20, 36), (x + 12, y + 36, 100, 5))
            pygame.draw.rect(screen, color, (x + 12, y + 36, int(100 * clamp(ratio, 0, 1)), 5))

    def _draw_dash(self, screen, p, t):
        cx, cy = S.WIDTH - 62, S.HEIGHT - 62
        ready = p.dash_cd <= 0
        rect = pygame.Rect(cx - 25, cy - 25, 50, 50)
        pygame.draw.circle(screen, (10, 16, 30), (cx, cy), 25)
        pygame.draw.circle(screen, S.CYAN_DIM, (cx, cy), 25, 1)
        if ready:
            pulse = 1 + 0.08 * math.sin(t * 6)
            pygame.draw.circle(screen, S.CYAN, (cx, cy), int(24 * pulse), 2)
            pygame.draw.circle(screen, S.CYAN, (cx, cy), 4)
            label_color = S.CYAN
        else:
            progress = 1 - p.dash_cd / S.DASH_COOLDOWN
            if progress > 0.01:
                pygame.draw.arc(
                    screen, S.CYAN, rect,
                    -math.pi / 2,
                    -math.pi / 2 + TAU * min(0.999, max(0.005, progress)),
                    3,
                )
            label_color = S.DIM
        self.blit_text(screen, "DASH", "mono", 9, label_color, (cx, cy + 36))

    def _bar(self, surf, rect, ratio, color, ticks=16):
        rect = pygame.Rect(rect)
        pygame.draw.rect(surf, (12, 18, 34), rect)
        ratio = clamp(ratio, 0.0, 1.0)
        if ratio > 0:
            fill = pygame.Rect(rect.x, rect.y, max(1, int(rect.w * ratio)), rect.h)
            pygame.draw.rect(surf, color, fill)
            pygame.draw.line(
                surf, scale_color(color, 1.25),
                (fill.x, fill.y), (fill.right - 1, fill.y), 1,
            )
        if ticks:
            for i in range(1, ticks):
                x = rect.x + rect.w * i // ticks
                pygame.draw.line(surf, (8, 12, 24), (x, rect.y), (x, rect.bottom - 1), 1)
        pygame.draw.rect(surf, color, rect, 1)

    def _draw_crosshair(self, screen, mouse_pos, t):
        mx, my = int(mouse_pos[0]), int(mouse_pos[1])
        color = S.CYAN
        pygame.draw.circle(screen, color, (mx, my), 10, 1)
        for i in range(4):
            ang = math.radians(t * 35 + i * 90 + 45)
            c, s = math.cos(ang), math.sin(ang)
            p1 = (mx + c * 14, my + s * 14)
            p2 = (mx + c * 20, my + s * 20)
            pygame.draw.line(screen, color, p1, p2, 2)
        pygame.draw.circle(screen, S.WHITE, (mx, my), 2)

    def _draw_banner(self, screen, banner):
        elapsed = banner["duration"] - banner["time"]
        fade = min(1.0, elapsed / 0.18, banner["time"] / 0.35)
        alpha = int(240 * clamp(fade, 0, 1))
        yoff = int((1 - min(1.0, elapsed / 0.25)) * 16)

        title = banner["title"]
        sub = banner["sub"]
        color = banner["color"]

        title_font = "display" if len(title) <= 14 else "mono"
        self.blit_text(
            screen, title, title_font, 54, color,
            (S.WIDTH // 2, 258 + yoff), alpha=alpha,
        )
        self.blit_text(
            screen, sub, "mono", 15, S.DIM,
            (S.WIDTH // 2, 306 + yoff), alpha=alpha,
        )
        line_w = 190
        line_alpha = int(alpha * 0.6)
        line_surf = pygame.Surface((line_w, 1), pygame.SRCALPHA)
        line_surf.fill((*color, line_alpha))
        screen.blit(line_surf, (S.WIDTH // 2 - 150 - line_w, 258 + yoff))
        screen.blit(line_surf, (S.WIDTH // 2 + 150, 258 + yoff))

    # ------------------------------------------------------------ 标题
    def draw_title(self, screen, best, t, muted):
        # 背景装饰六边形
        for radius, speed, col in ((250, 0.18, (10, 30, 48)), (185, -0.26, (12, 38, 60))):
            pts = []
            for i in range(6):
                ang = TAU * i / 6 + t * speed
                pts.append((S.WIDTH // 2 + math.cos(ang) * radius,
                            S.HEIGHT * 0.34 + math.sin(ang) * radius * 0.62))
            pygame.draw.polygon(screen, col, pts, 1)

        self.blit_text(
            screen, "// DEEP SPACE SURVIVAL PROTOCOL", "mono", 13,
            S.CYAN_DIM, (S.WIDTH // 2, 84),
        )

        bob = math.sin(t * 1.4) * 3
        if self.has_cjk:
            title = "霓虹射手"
            main_font = self.font("cjk", 102)
        else:
            title = "NEON SURVIVOR"
            main_font = self.font("display", 78)

        main = main_font.render(title, True, S.WHITE)
        red = main_font.render(title, True, (255, 40, 105))
        cyan = main_font.render(title, True, (40, 225, 255))
        rect = main.get_rect(center=(S.WIDTH // 2, int(196 + bob)))
        screen.blit(red, rect.move(-4, 0))
        screen.blit(cyan, rect.move(4, 0))
        screen.blit(main, rect)

        self.blit_text(
            screen, "N E O N   S U R V I V O R", "mono", 21,
            S.CYAN, (S.WIDTH // 2, 276 + bob),
        )
        for sign in (-1, 1):
            x1 = S.WIDTH // 2 + sign * 230
            x2 = S.WIDTH // 2 + sign * 420
            pygame.draw.line(screen, S.CYAN_DIM, (x1, 306), (x2, 306), 1)
            pygame.draw.circle(screen, S.CYAN, (x1, 306), 2)

        self.blit_text(
            screen, f"BEST RECORD  {best:07d}", "mono", 16,
            S.SCORE_GOLD, (S.WIDTH // 2, 342),
        )

        # 操作说明面板
        panel = self.panel(620, 220, 170)
        screen.blit(panel, panel.get_rect(center=(S.WIDTH // 2, 470)))
        self.blit_text(screen, "// CONTROLS", "mono", 12, S.DIM, (S.WIDTH // 2, 382))

        rows = [
            ("WASD / \u2191\u2193\u2190\u2192", self.L("移动", "MOVE")),
            ("MOUSE", self.L("瞄准 \u00b7 自动开火", "AIM \u00b7 AUTO-FIRE")),
            ("SPACE / SHIFT", self.L("冲刺（短暂无敌）", "DASH (I-FRAMES)")),
            ("ESC / P", self.L("暂停", "PAUSE")),
            ("M", self.L("静音 / 恢复", "MUTE")),
        ]
        y = 410
        for key, desc in rows:
            self.blit_text(screen, key, "mono", 17, S.WHITE, (S.WIDTH // 2 - 262, y), anchor="midleft")
            pygame.draw.circle(screen, S.CYAN_DIM, (S.WIDTH // 2 - 40, y), 2)
            desc_kind = "cjk" if self.has_cjk else "mono"
            self.blit_text(screen, desc, desc_kind, 17, S.DIM, (S.WIDTH // 2 + 2, y), anchor="midleft")
            y += 34

        alpha = int(150 + 105 * math.sin(t * 3.0))
        self.blit_text(
            screen, self.L("按 ENTER 开始", "PRESS ENTER TO DEPLOY"),
            "cjk" if self.has_cjk else "mono", 24,
            S.CYAN, (S.WIDTH // 2, 630), alpha=alpha,
        )
        self.blit_text(
            screen, self.L("ESC 退出   \u00b7   M 静音", "ESC QUIT   \u00b7   M MUTE"),
            "cjk" if self.has_cjk else "mono", 13,
            S.DIM, (S.WIDTH // 2, 668),
        )
        if muted:
            self.blit_text(screen, "MUTED", "mono", 12, S.DIM, (S.WIDTH - 28, 40), anchor="midright")

    # ------------------------------------------------------------ 暂停 / 结算
    def draw_pause(self, screen, world, t):
        self.black_overlay.set_alpha(165)
        screen.blit(self.black_overlay, (0, 0))
        panel = self.panel(520, 300, 200)
        screen.blit(panel, panel.get_rect(center=(S.WIDTH // 2, S.HEIGHT // 2)))

        self.blit_text(screen, "PAUSED", "display", 56, S.CYAN, (S.WIDTH // 2, S.HEIGHT // 2 - 78))
        self.blit_text(
            screen, self.L("已暂停", "SYSTEM HALTED"), "cjk" if self.has_cjk else "mono", 18,
            S.DIM, (S.WIDTH // 2, S.HEIGHT // 2 - 32),
        )
        pygame.draw.line(
            screen, S.CYAN_DIM,
            (S.WIDTH // 2 - 180, S.HEIGHT // 2 - 8), (S.WIDTH // 2 + 180, S.HEIGHT // 2 - 8), 1,
        )
        self.blit_text(
            screen, self.L("ESC / P  继续", "ESC / P  RESUME"), "cjk" if self.has_cjk else "mono", 17,
            S.WHITE, (S.WIDTH // 2, S.HEIGHT // 2 + 30),
        )
        self.blit_text(
            screen, self.L("R  重新开始", "R  RESTART"), "cjk" if self.has_cjk else "mono", 17,
            S.WHITE, (S.WIDTH // 2, S.HEIGHT // 2 + 64),
        )
        self.blit_text(
            screen, self.L("M  静音切换", "M  TOGGLE MUTE"), "cjk" if self.has_cjk else "mono", 17,
            S.WHITE, (S.WIDTH // 2, S.HEIGHT // 2 + 98),
        )
        self.blit_text(
            screen, f"WAVE {world.director.wave:02d}    SCORE {world.score:07d}", "mono", 12,
            S.DIM, (S.WIDTH // 2, S.HEIGHT // 2 + 132),
        )

    def draw_gameover(self, screen, world, best, new_record, t):
        self.black_overlay.set_alpha(190)
        screen.blit(self.black_overlay, (0, 0))
        panel = self.panel(700, 440, 205, S.RED)
        screen.blit(panel, panel.get_rect(center=(S.WIDTH // 2, S.HEIGHT // 2)))

        cx = S.WIDTH // 2
        top = S.HEIGHT // 2 - 220
        self.blit_text(screen, "SIGNAL LOST", "display", 58, S.RED, (cx, top + 62))
        self.blit_text(
            screen, self.L("信号中断", "CONNECTION TERMINATED"), "cjk" if self.has_cjk else "mono", 17,
            S.DIM, (cx, top + 102),
        )
        pygame.draw.line(screen, (80, 24, 34), (cx - 220, top + 128), (cx + 220, top + 128), 1)

        rows = [
            (self.L("抵达波次", "WAVE REACHED"), f"{world.director.wave:02d}"),
            (self.L("最终得分", "FINAL SCORE"), f"{world.score:07d}"),
            (self.L("击毁目标", "KILLS"), f"{world.kills:04d}"),
            (self.L("历史最高", "BEST"), f"{best:07d}"),
        ]
        y = top + 164
        for label, value in rows:
            self.blit_text(
                screen, label, "cjk" if self.has_cjk else "mono", 16,
                S.DIM, (cx - 240, y), anchor="midleft",
            )
            self.blit_text(
                screen, value, "mono", 24, S.WHITE, (cx + 240, y), anchor="midright",
            )
            y += 44

        if new_record:
            alpha = int(170 + 85 * math.sin(t * 5))
            self.blit_text(
                screen, "NEW RECORD", "display", 24, S.SCORE_GOLD,
                (cx, top + 350), alpha=alpha,
            )

        alpha = int(160 + 90 * math.sin(t * 3))
        self.blit_text(
            screen, self.L("按 R 重新部署", "PRESS R TO REDEPLOY"),
            "cjk" if self.has_cjk else "mono", 18,
            S.CYAN, (cx, top + 388), alpha=alpha,
        )
        self.blit_text(
            screen, self.L("ESC 返回标题", "ESC  RETURN TO TITLE"),
            "cjk" if self.has_cjk else "mono", 12,
            S.DIM, (cx, top + 414),
        )

    # ------------------------------------------------------------ 全屏叠加
    def draw_world_overlay(self, screen):
        screen.blit(self.vignette, (0, 0))

    def draw_scanlines(self, screen):
        screen.blit(self.scanlines, (0, 0))
