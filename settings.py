"""NEON SURVIVOR // 霓虹射手 —— 全局配置与数值平衡。

所有可调参数集中在这里，方便微调手感。
"""
from pygame.math import Vector2

# ---------- 窗口 ----------
WIDTH = 1280
HEIGHT = 720
FPS = 60
CENTER = Vector2(WIDTH / 2, HEIGHT / 2)
CAPTION = "NEON SURVIVOR // 霓虹射手"

# ---------- 配色 ----------
BG_TOP = (8, 11, 28)
BG_BOTTOM = (2, 3, 9)
GRID_MINOR = (13, 23, 45)
GRID_MAJOR = (20, 36, 70)
NEBULA_A = (15, 6, 36)
NEBULA_B = (3, 13, 34)

CYAN = (46, 235, 255)
CYAN_DIM = (20, 105, 128)
MAGENTA = (255, 66, 170)
PINK = (255, 122, 200)
ORANGE = (255, 176, 54)
GREEN = (64, 255, 158)
PURPLE = (172, 112, 255)
RED = (255, 62, 86)
YELLOW = (255, 228, 92)
WHITE = (234, 248, 255)
DIM = (108, 136, 166)
SCORE_GOLD = (255, 214, 102)
PANEL = (8, 14, 28)

# ---------- 玩家 ----------
PLAYER_MAX_HP = 100
PLAYER_SPEED = 360.0
PLAYER_ACCEL = 12.0          # 速度趋近系数，越大越跟手
PLAYER_RADIUS = 13
PLAYER_IFRAMES = 0.75        # 受击无敌时间（秒）
PLAY_MARGIN = 26             # 活动边界留白

# 冲刺
DASH_SPEED = 1260.0
DASH_TIME = 0.15
DASH_COOLDOWN = 1.7
DASH_IFRAMES = 0.32

# 主武器
GUN_INTERVAL = 0.135
GUN_DAMAGE = 11.0
BULLET_SPEED = 1080.0
BULLET_LIFE = 1.0
BULLET_RADIUS = 5
MUZZLE_OFFSET = 22

# 增益道具
POWERUP_TIME = 11.0
RAPID_MULT = 0.55
SPREAD_COUNT = 3
SPREAD_ANGLE = 0.15
SHIELD_HP = 55.0
SHIELD_TIME = 10.0
HEAL_AMOUNT = 30
POWERUP_DROP_CHANCE = 0.15
POWERUP_LIFETIME = 12.0

POWERUPS = {
    "heal": {"color": GREEN, "label": "REPAIR"},
    "rapid": {"color": YELLOW, "label": "RAPID"},
    "spread": {"color": MAGENTA, "label": "SPREAD"},
    "shield": {"color": CYAN, "label": "SHIELD"},
}

# ---------- 敌人 ----------
ENEMY_TYPES = {
    "drone": {
        "hp": 26, "speed": 118, "radius": 13, "damage": 10,
        "score": 10, "color": MAGENTA, "shape": "tri", "mass": 1.0,
    },
    "sprinter": {
        "hp": 16, "speed": 228, "radius": 10, "damage": 8,
        "score": 14, "color": ORANGE, "shape": "diamond", "mass": 0.6,
    },
    "tank": {
        "hp": 120, "speed": 72, "radius": 25, "damage": 20,
        "score": 32, "color": PURPLE, "shape": "hex", "mass": 2.6,
    },
    "gunner": {
        "hp": 38, "speed": 96, "radius": 15, "damage": 10,
        "score": 22, "color": GREEN, "shape": "diamond", "mass": 1.2,
        "fire_interval": 2.0, "bullet_speed": 310,
    },
}

MAX_ENEMIES = 48             # 同屏敌人上限，保护帧率
ENEMY_HP_GROWTH = 0.10       # 每波线性血量成长
ENEMY_HP_QUAD = 0.004        # 每波二次血量成长
ENEMY_SPEED_GROWTH = 0.025
ENEMY_SPEED_CAP = 1.6

# ---------- Boss ----------
BOSS_EVERY = 5               # 每 5 波一个 Boss
BOSS_HP_BASE = 950
BOSS_HP_STEP = 520
BOSS_RADIUS = 52
BOSS_SCORE = 800

# ---------- 波次 ----------
WAVE_INTERLUDE = 2.8         # 清波后的休整时间
WAVE_FIRST_DELAY = 0.6
WAVE_SPAWN_BASE = 0.62
WAVE_SPAWN_MIN = 0.16
WAVE_CLEAR_BASE = 60

# ---------- 连杀 ----------
CHAIN_WINDOW = 2.6           # 多少秒内继续击杀算连锁
CHAIN_STEP = 4               # 每 4 连杀提升一级倍率
CHAIN_MAX = 5

# ---------- 存档 ----------
HIGHSCORE_FILE = "highscore.json"
