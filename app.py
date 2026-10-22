"""游戏外壳：状态机、输入、渲染合成、最高分存档。"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pygame
from pygame.math import Vector2

import audio
import settings as S
from ui import UI
from world import World

BASE_DIR = Path(__file__).resolve().parent
STATE_TITLE = "title"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_GAMEOVER = "gameover"


def load_best() -> int:
    try:
        with open(BASE_DIR / S.HIGHSCORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return max(0, int(data.get("best", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_best(value: int):
    try:
        with open(BASE_DIR / S.HIGHSCORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"best": int(value)}, f)
    except OSError:
        pass


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((S.WIDTH, S.HEIGHT))
        pygame.display.set_caption(S.CAPTION)
        pygame.display.set_icon(self._make_icon())

        self.world_surface = pygame.Surface((S.WIDTH, S.HEIGHT))
        self.world = World()
        self.ui = UI()

        self.state = STATE_TITLE
        self.best = load_best()
        self.new_record = False
        self.ui_time = 0.0
        self.mouse_pos = pygame.mouse.get_pos()
        self.running = True
        self.clock = pygame.time.Clock()
        self._cursor_hidden = False

    @staticmethod
    def _make_icon() -> pygame.Surface:
        icon = pygame.Surface((32, 32))
        icon.fill((5, 7, 16))
        pygame.draw.polygon(icon, S.CYAN, [(26, 16), (7, 7), (12, 16), (7, 25)], 2)
        return icon

    # ------------------------------------------------------------ 事件
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == STATE_TITLE:
                self.start_game()
            return

        if event.type != pygame.KEYDOWN:
            return

        key = event.key
        if key == pygame.K_m:
            audio.toggle_mute()
            return

        if self.state == STATE_TITLE:
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_game()
            elif key == pygame.K_ESCAPE:
                self.running = False
        elif self.state == STATE_PLAYING:
            if key in (pygame.K_ESCAPE, pygame.K_p):
                self.state = STATE_PAUSED
                audio.play("click")
        elif self.state == STATE_PAUSED:
            if key in (pygame.K_ESCAPE, pygame.K_p):
                self.state = STATE_PLAYING
                audio.play("click")
            elif key == pygame.K_r:
                self.start_game()
        elif self.state == STATE_GAMEOVER:
            if key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                self.start_game()
            elif key == pygame.K_ESCAPE:
                self.state = STATE_TITLE
                audio.play("click")

    def start_game(self):
        audio.play("click")
        self.world.reset()
        self.state = STATE_PLAYING
        self.new_record = False
        self.mouse_pos = pygame.mouse.get_pos()

    # ------------------------------------------------------------ 更新
    def update(self, dt: float):
        self.ui_time += dt
        self.mouse_pos = pygame.mouse.get_pos()

        if self.state == STATE_PLAYING:
            keys = pygame.key.get_pressed()
            self.world.update(dt, keys, self.mouse_pos, firing=True)
            if self.world.finished:
                self._on_game_over()
        elif self.state == STATE_TITLE:
            focus = Vector2(
                S.WIDTH / 2 + math.sin(self.ui_time * 0.20) * 150,
                S.HEIGHT / 2 + math.cos(self.ui_time * 0.17) * 80,
            )
            self.world.background.update(dt, focus)
        elif self.state == STATE_GAMEOVER:
            self.world.background.update(dt, self.world.player.pos)
            self.world.particles.update(dt * 0.5)

        want_hidden = self.state == STATE_PLAYING
        if want_hidden != self._cursor_hidden:
            pygame.mouse.set_visible(not want_hidden)
            self._cursor_hidden = want_hidden

    def _on_game_over(self):
        self.state = STATE_GAMEOVER
        self.new_record = self.world.score > self.best
        if self.new_record:
            self.best = self.world.score
            save_best(self.best)

    # ------------------------------------------------------------ 绘制
    def draw(self):
        if self.state == STATE_TITLE:
            focus = Vector2(
                S.WIDTH / 2 + math.sin(self.ui_time * 0.20) * 150,
                S.HEIGHT / 2 + math.cos(self.ui_time * 0.17) * 80,
            )
            self.world.background.draw(self.screen, focus)
            self.ui.draw_title(self.screen, self.best, self.ui_time, audio.is_muted())
        else:
            self.world.draw(self.world_surface)
            ox = oy = 0
            if self.state == STATE_PLAYING and self.world.shake > 0.4:
                mag = self.world.shake
                ox = random.uniform(-mag, mag)
                oy = random.uniform(-mag, mag)
            self.screen.fill(S.BG_BOTTOM)
            self.screen.blit(self.world_surface, (int(ox), int(oy)))
            self.ui.draw_world_overlay(self.screen)
            self.ui.draw_hud(
                self.screen, self.world, self.mouse_pos, self.best,
                self.ui_time, audio.is_muted(),
                show_crosshair=self.state == STATE_PLAYING,
            )
            if self.state == STATE_PAUSED:
                self.ui.draw_pause(self.screen, self.world, self.ui_time)
            elif self.state == STATE_GAMEOVER:
                self.ui.draw_gameover(
                    self.screen, self.world, self.best, self.new_record, self.ui_time
                )

        self.ui.draw_scanlines(self.screen)
        pygame.display.flip()

    # ------------------------------------------------------------ 主循环
    def run(self):
        while self.running:
            dt = self.clock.tick(S.FPS) / 1000.0
            dt = min(dt, 0.05)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
        pygame.quit()
