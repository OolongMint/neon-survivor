"""程序化合成音效（不依赖任何音频素材）。

启动时用正弦/方波/噪声生成一组 16-bit 立体声采样，
再交给 pygame.mixer 播放。没有音频设备时自动静音，游戏照常运行。
"""
from __future__ import annotations

import array
import math
import random

import pygame

SR = 44100
TAU = math.tau

_ready = False
_muted = False
_sounds: dict[str, pygame.mixer.Sound] = {}
_last_played: dict[str, float] = {}


# ---------------------------------------------------------------- 合成
def _snd(duration: float, gen, volume: float = 1.0) -> pygame.mixer.Sound:
    n = int(SR * duration)
    buf = array.array("h", [0]) * (n * 2)
    for i in range(n):
        t = i / SR
        v = gen(t)
        v = -1.0 if v < -1.0 else 1.0 if v > 1.0 else v
        s = int(v * 32767)
        buf[2 * i] = s
        buf[2 * i + 1] = s
    sound = pygame.mixer.Sound(buffer=buf.tobytes())
    sound.set_volume(volume)
    return sound


def _env(t, attack=0.003, decay=0.0, fade_out=0.0, dur=1.0):
    a = 1.0 if attack <= 0 else min(1.0, t / attack)
    d = math.exp(-decay * t) if decay > 0 else 1.0
    o = 1.0
    if fade_out > 0 and t > dur - fade_out:
        o = max(0.0, (dur - t) / fade_out)
    return a * d * o


def _sweep(f0, f1, dur):
    """返回频率扫动的相位函数。"""
    def phase(t):
        return TAU * (f0 * t + 0.5 * (f1 - f0) * t * t / max(1e-6, dur))

    return phase


def _arp(dur: float, notes, note_dur: float, wave="sine"):
    def gen(t):
        idx = min(len(notes) - 1, int(t / note_dur))
        lt = t - idx * note_dur
        f = notes[idx]
        if wave == "saw":
            s = 2.0 * ((f * lt) % 1.0) - 1.0
        else:
            s = math.sin(TAU * f * lt)
        return s * _env(lt, 0.004, 9.0)

    total = dur
    return total, gen


# ---------------------------------------------------------------- 音色
def _build():
    global _sounds

    # 射击：高频扫向低频的短促激光
    dur = 0.08
    ph = _sweep(1400, 380, dur)

    def shoot_gen(t):
        s = 0.55 * (1.0 if math.sin(ph(t)) >= 0 else -1.0)
        s += 0.35 * math.sin(ph(t))
        s += 0.12 * random.uniform(-1, 1)
        return s * _env(t, 0.002, 42.0)

    _sounds["shoot"] = _snd(dur, shoot_gen, 0.22)

    # 命中：噪声 + 高频短音
    _sounds["hit"] = _snd(
        0.05,
        lambda t: (random.uniform(-1, 1) * 0.75 + math.sin(TAU * 2400 * t) * 0.5)
        * math.exp(-90 * t),
        0.22,
    )

    # 击毁：低频轰鸣 + 噪声爆裂
    def kill_gen(t):
        rumble = math.sin(TAU * (180 * t - 260 * t * t)) * 0.55
        noise = random.uniform(-1, 1) * 0.8
        return (rumble * math.exp(-9 * t) + noise * math.exp(-16 * t))

    _sounds["kill"] = _snd(0.32, kill_gen, 0.4)

    # 受伤：下滑锯齿
    hurt_ph = _sweep(300, 65, 0.34)
    _sounds["hurt"] = _snd(
        0.34,
        lambda t: (2.0 * ((hurt_ph(t) / TAU) % 1.0) - 1.0) * _env(t, 0.004, 8.0)
        + random.uniform(-1, 1) * 0.25 * math.exp(-20 * t),
        0.5,
    )

    # 冲刺：风声
    dash_ph = _sweep(220, 900, 0.2)
    _sounds["dash"] = _snd(
        0.2,
        lambda t: (math.sin(dash_ph(t)) * 0.45 + random.uniform(-1, 1) * 0.35)
        * _env(t, 0.01, 10.0),
        0.3,
    )

    # 拾取：两声上扬
    def pickup_gen(t):
        if t < 0.09:
            return math.sin(TAU * 880 * t) * _env(t, 0.003, 8.0)
        lt = t - 0.09
        return (math.sin(TAU * 1320 * lt) + 0.35 * math.sin(TAU * 2640 * lt)) * _env(lt, 0.003, 9.0)

    _sounds["pickup"] = _snd(0.3, pickup_gen, 0.42)

    # 护盾：金属高音
    _sounds["shield"] = _snd(
        0.26,
        lambda t: (math.sin(TAU * 1600 * t) + 0.5 * math.sin(TAU * 2450 * t))
        * math.exp(-13 * t),
        0.35,
    )

    # 清波：上行分解和弦
    dur, gen = _arp(0.55, [523.25, 659.25, 783.99, 1046.5], 0.11)
    _sounds["wave"] = _snd(dur, gen, 0.4)

    # Boss 警报：低频脉动
    def boss_gen(t):
        trem = 0.55 + 0.45 * math.sin(TAU * 5.2 * t)
        s = math.sin(TAU * 55 * t) * 0.6 + math.sin(TAU * 82.5 * t) * 0.35
        s += random.uniform(-1, 1) * 0.12
        return s * trem * _env(t, 0.12, 0.4, 0.25, 1.25)

    _sounds["boss"] = _snd(1.25, boss_gen, 0.5)

    # 失败：下行和弦
    dur, gen = _arp(1.05, [392.0, 311.13, 246.94, 164.81], 0.22, wave="saw")
    _sounds["gameover"] = _snd(dur, gen, 0.45)

    # UI 点击
    _sounds["click"] = _snd(
        0.045,
        lambda t: math.sin(TAU * 1200 * t) * math.exp(-70 * t),
        0.2,
    )


# ---------------------------------------------------------------- 对外接口
def init() -> bool:
    """初始化混音器并生成音效。失败时返回 False，游戏静音运行。"""
    global _ready
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(32)
        _build()
        _ready = True
    except (pygame.error, ValueError, OSError):
        _ready = False
    return _ready


def play(name: str, min_interval: float = 0.0):
    if not _ready or _muted:
        return
    sound = _sounds.get(name)
    if sound is None:
        return
    now = pygame.time.get_ticks() / 1000.0
    if min_interval > 0:
        last = _last_played.get(name, -999.0)
        if now - last < min_interval:
            return
        _last_played[name] = now
    sound.play()


def toggle_mute() -> bool:
    global _muted
    _muted = not _muted
    if _muted and _ready:
        pygame.mixer.stop()
    return _muted


def is_muted() -> bool:
    return _muted


def available() -> bool:
    return _ready
