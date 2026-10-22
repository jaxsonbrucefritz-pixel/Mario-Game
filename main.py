import asyncio
import math
import random
import pygame

# Game Boy color palette
GB_GREEN_DARK = (15, 56, 15)
GB_GREEN_MED = (48, 98, 48)
GB_GREEN_LIGHT = (139, 172, 15)
GB_GREEN_LIGHTEST = (155, 188, 15)
GB_RED_MED = (191, 0, 15)
GB_BROWN_DARK = (224, 192, 128)
GB_BROWN_LIGHT = (240, 224, 192)
GB_TAN = (255, 198, 140)
GB_BLUE = (0, 0, 200)
GB_WHITE = (255, 255, 255)

WIDTH, HEIGHT = 640, 576
GROUND_Y = 560
LAST_LEVEL = 3
GRAVITY = 0.5
MAX_FALL = 12
WALK_SPEED = 3
RUN_SPEED = 5       # top speed while holding Z / Shift
ACCEL = 0.25        # how fast you speed up
FRICTION = 0.2      # how fast you slow down when you let go
SKID = 0.45         # how hard you brake when turning around
LEVEL_TIME = 400    # the clock at the start of each level
TIME_TICK = 24      # frames per tick of the clock
LEDGE_Y = 270       # height of the upper exit's ledge
BONUS_X = [170, 270, 370, 470]  # the four ladders in the bonus game
ENEMY_W, ENEMY_H = 28, 24
GOOMBA_SPEED = 2
SHELL_SPEED = 6
MUSHROOM_SPEED = 2

# --- HERO SPRITES ---
# Pixel art, facing right. Each character is one 2x2 screen pixel.
# R = cap/shirt (red for Mario, green for Luigi), S = skin, H = hair/mustache,
# E = eye, W = cap emblem, B = overalls, Y = buttons, K = shoes
HERO_PIXELS = [
    "....RRRRRR.....",
    "...RRRRWWRRR...",
    "..RRRRWWRRRRR..",
    "..RRRRRRRRRRRRR",
    "..HHHSSSSSS....",
    "..HHSSSSESSS...",
    "..HSSSSSESSSSS.",
    "..HSSSHHHHHSSS.",
    "...SSSSHHHHH...",
    "....SSSSSSS....",
    "...RRBRRRRBR...",
    "..RRRBRRRRBRR..",
    ".SRRRBBBBBBRRS.",
    ".SSRBBYBBYBBRSS",
    ".SS.BBBBBBBB.SS",
    "....BBBBBBBB...",
    "....BBB..BBB...",
    "....BBB..BBB...",
    "...KKKK..KKKK..",
    "..KKKKK..KKKKK.",
]
# Swapped in for the last four rows on the walking frame
HERO_WALK_LEGS = [
    "...BBB...BBBB..",
    "..BBB.....BBB..",
    ".KKKK.....KKKK.",
    "KKKK.......KKKK",
]
HERO_COLORS = {
    "S": GB_TAN,
    "H": (101, 56, 24),
    "E": (20, 20, 20),
    "W": GB_WHITE,
    "B": GB_BLUE,
    "Y": (255, 220, 0),
    "K": (120, 70, 20),
}
_sprite_cache = {}

def make_sprite(rows, colors, flip=False):
    # Turn a pixel-art grid into a surface (2x2 screen pixels per letter).
    # "." is see-through; every other letter is looked up in colors.
    key = (tuple(rows), tuple(colors.items()), flip)
    if key not in _sprite_cache:
        surf = pygame.Surface((len(rows[0]) * 2, len(rows) * 2), pygame.SRCALPHA)
        for py, row in enumerate(rows):
            for px, ch in enumerate(row):
                if ch != ".":
                    surf.fill(colors[ch], (px * 2, py * 2, 2, 2))
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        _sprite_cache[key] = surf
    return _sprite_cache[key]

def grow_pixels(rows):
    # Stretch the small sprite into the big one by repeating body rows and columns
    tall = []
    for i, row in enumerate(rows):
        tall.append(row)
        if i in (5, 9, 10, 11, 12, 13, 14, 15, 16, 17):
            tall.append(row)
    return ["".join(ch * (2 if j in (5, 8, 10) else 1) for j, ch in enumerate(row)) for row in tall]

def hero_sprite(main_color, big, frame, facing):
    rows = HERO_PIXELS[:16] + (HERO_WALK_LEGS if frame else HERO_PIXELS[16:])
    if big:
        rows = grow_pixels(rows)
    return make_sprite(rows, dict(HERO_COLORS, R=main_color), facing < 0)

def draw_mario(screen, x, y, font, facing=1, frame=0):
    screen.blit(hero_sprite(GB_RED_MED, False, frame, facing), (x, y))

def draw_luigi(screen, x, y, font, facing=1, frame=0):
    screen.blit(hero_sprite(GB_GREEN_LIGHT, False, frame, facing), (x, y))

def draw_big_mario(screen, x, y, font, facing=1, frame=0):
    screen.blit(hero_sprite(GB_RED_MED, True, frame, facing), (x, y))

def draw_big_luigi(screen, x, y, font, facing=1, frame=0):
    screen.blit(hero_sprite(GB_GREEN_LIGHT, True, frame, facing), (x, y))

def draw_goal(screen, x):
    # Exit tower: a normal door at ground level, and a bonus door up on the ledge
    wall = (40, 88, 40)
    pygame.draw.rect(screen, wall, (x, 150, 160, GROUND_Y - 150))
    for i in range(5):
        pygame.draw.rect(screen, wall, (x + i * 35, 128, 20, 22))
    for row_y in range(150, GROUND_Y, 20):
        pygame.draw.line(screen, GB_GREEN_DARK, (x, row_y), (x + 159, row_y), 1)
    draw_brick(screen, x - 70, LEDGE_Y, 200, 16)
    for door_bottom in (LEDGE_Y, GROUND_Y):
        pygame.draw.rect(screen, GB_GREEN_DARK, (x + 60, door_bottom - 52, 40, 52))
        pygame.draw.ellipse(screen, GB_GREEN_DARK, (x + 60, door_bottom - 64, 40, 26))
    # A star over the upper door marks the bonus game
    points = []
    for k in range(10):
        r = 13 if k % 2 == 0 else 5
        a = -math.pi / 2 + k * math.pi / 5
        points.append((x + 80 + r * math.cos(a), LEDGE_Y - 86 + r * math.sin(a)))
    pygame.draw.polygon(screen, (240, 180, 40), points)

def draw_brick(screen, x, y, width, height):
    pygame.draw.rect(screen, GB_GREEN_MED, (x, y, width, height))
    brick_h = 16
    brick_w = 20
    for i in range(height // brick_h + 1):
        ry = i * brick_h
        if ry > height:
            break
        pygame.draw.line(screen, GB_GREEN_DARK, (x, y + ry), (x + width, y + ry), 1)
        if ry < height:
            offset = (brick_w // 2) if i % 2 else 0
            for bx in range(offset, width, brick_w):
                pygame.draw.line(screen, GB_GREEN_DARK, (x + bx, y + ry), (x + bx, y + min(ry + brick_h, height)), 1)

# --- ENEMY AND ITEM SPRITES ---
# Same letter-grid pixel art as the heroes. M = body, D = dark brown,
# W = eye white, E = pupil, T = tan, G = shell, O = outline, C = shell rim,
# S = skin, K = feet, R = red, Q = box gold, U = used box
SPRITE_COLORS = {
    "M": (150, 90, 40),
    "D": (80, 45, 15),
    "W": GB_WHITE,
    "E": (20, 20, 20),
    "T": GB_BROWN_LIGHT,
    "G": GB_GREEN_LIGHT,
    "O": (30, 80, 30),
    "C": GB_BROWN_LIGHT,
    "S": GB_TAN,
    "K": (230, 150, 40),
    "R": GB_RED_MED,
    "Q": (240, 180, 40),
    "U": (150, 110, 60),
}

GOOMBA_PIXELS = [
    "....MMMMMM....",
    "...MMMMMMMM...",
    "..MMDMMMMDMM..",
    ".MMMWDMMDWMMM.",
    ".MMMWEMMEWMMM.",
    "MMMMWEMMEWMMMM",
    "MMMMMMMMMMMMMM",
    ".MMMMDDDDMMMM.",
    "...TTTTTTTT...",
    "...TTTTTTTT...",
    "DDDDD...DDD...",
    "DDDDD...DDDD..",
]
SQUISHED_GOOMBA_PIXELS = [
    "..MMMMMMMMMM..",
    ".MMWEMMMMEWMM.",
    "MMMMMMMMMMMMMM",
    "DDDDD....DDDDD",
]

def draw_goomba(screen, x, y, frame=0):
    # The feet are lopsided, so flipping the sprite makes it waddle
    screen.blit(make_sprite(GOOMBA_PIXELS, SPRITE_COLORS, frame == 1), (x, y))

def draw_squished_goomba(screen, x, y):
    # Flattened after a stomp
    screen.blit(make_sprite(SQUISHED_GOOMBA_PIXELS, SPRITE_COLORS), (x, y + 16))

def draw_coin(screen, x, y, frame_count):
    # Spin by squeezing the coin's width
    w = (20, 14, 6, 14)[(frame_count // 8) % 4]
    pygame.draw.ellipse(screen, GB_BROWN_LIGHT, (x + 10 - w // 2, y, w, 20))
    if w > 6:
        pygame.draw.ellipse(screen, GB_BROWN_DARK, (x + 10 - w // 4, y + 5, w // 2, 10), 1)

def draw_scenery(screen, camera_x):
    hill_color = (24, 66, 24)
    cloud_color = (34, 80, 34)
    # Hills scroll at half speed and clouds at a quarter, so they look far away
    offset = int(camera_x * 0.5) % 800
    for base in range(0, WIDTH + 1600, 800):
        hx = base - offset - 800
        pygame.draw.ellipse(screen, hill_color, (hx + 40, 460, 260, 200))
        pygame.draw.ellipse(screen, hill_color, (hx + 440, 500, 170, 120))
    offset = int(camera_x * 0.25) % 700
    for base in range(0, WIDTH + 1400, 700):
        cx = base - offset - 700
        for dx, dy, w in ((60, 90, 90), (300, 60, 120), (520, 140, 70)):
            pygame.draw.ellipse(screen, cloud_color, (cx + dx, dy, w, w // 2))
            pygame.draw.ellipse(screen, cloud_color, (cx + dx + w // 6, dy - w // 6, w // 2, w // 2))
            pygame.draw.ellipse(screen, cloud_color, (cx + dx + w // 2, dy - w // 10, w * 2 // 5, w * 2 // 5))

KOOPA_PIXELS = [
    ".........SSSS.",
    "........SSSSSS",
    "........SSSWES",
    "........SSSWES",
    "........SSSSSS",
    "....OOOO.SSSS.",
    "...OGGGGOSSS..",
    "..OGGOOGGOSS..",
    ".OGGOGGOGGOS..",
    ".OGOGGGGOGOS..",
    ".OGGGOOGGGOS..",
    "CCCCCCCCCCCC..",
    ".SSS....SSS...",
    ".SSS....SSS...",
    "KKKK....KKKK..",
    "KKKKK...KKKKK.",
]
# Swapped in for the last four rows on the walking frame
KOOPA_WALK_LEGS = [
    "..SSS..SSS....",
    "..SSS...SSS...",
    ".KKKK...KKKK..",
    ".KKKKK..KKKKK.",
]
SHELL_PIXELS = [
    "....OOOOOO....",
    "..OOGGGGGGOO..",
    ".OGGOGGGGOGGO.",
    ".OGOGGOOGGOGO.",
    "OGGOGGGGGGOGGO",
    "OGGGOOGGOOGGGO",
    "OGGGGGOOGGGGGO",
    "CCCCCCCCCCCCCC",
    ".CCCCCCCCCCCC.",
    "..OOOOOOOOOO..",
]

def draw_koopa(screen, x, y, facing=1, frame=0):
    # Taller than its hitbox: the head pokes up 16px above it
    rows = KOOPA_PIXELS[:12] + (KOOPA_WALK_LEGS if frame else KOOPA_PIXELS[12:])
    screen.blit(make_sprite(rows, SPRITE_COLORS, facing < 0), (x, y - 8))

def draw_shell(screen, x, y):
    # Koopa tucked into its shell
    screen.blit(make_sprite(SHELL_PIXELS, SPRITE_COLORS), (x, y + 4))

CHOMPER_CLOSED_HEAD = [
    "...RRRRRR...",
    ".RRRWRRRRRR.",
    "RRRRRRRRRRRR",
    "RRRRRRRRRRRR",
    "RWDWDWDWDWDR",
    "RRRRRRRRRRRR",
    ".RRRRRRRRRR.",
    "...RRRRRR...",
]
CHOMPER_OPEN_HEAD = [
    "..RRRRRRRR..",
    ".RRWRRRRRRR.",
    "RRRRRRRRRRRR",
    "RWDWDWDWDWDR",
    "DDDDDDDDDDDD",
    "DWDWDWDWDWDW",
    "RRRRRRRRRRRR",
    ".RRRRRRRRRR.",
]
CHOMPER_STEM = [
    ".....GG.....",
    ".....GG.....",
    ".GGG.GG.....",
    "GGGGGGG.....",
    ".GG..GG.GGG.",
    ".....GGGGGGG",
    ".....GG.....",
    ".....GG.....",
]
MUSHROOM_PIXELS = [
    "...RRRR...",
    ".RRWWRRRR.",
    "RRWWRRRWRR",
    "RRRRRRRWWR",
    "RRRRRRRRRR",
    ".SSESSESS.",
    ".SSSSSSSS.",
    "..SSSSSS..",
]
BOX_PIXELS = [
    "OOOOOOOOOO",
    "OWQQQQQQQO",
    "OQQQDDDQQO",
    "OQQQQQDQQO",
    "OQQQQDDQQO",
    "OQQQQQQQQO",
    "OQQQQDQQQO",
    "OOOOOOOOOO",
]
USED_BOX_PIXELS = [
    "OOOOOOOOOO",
    "OUUUUUUUUO",
    "OUOUUUUOUO",
    "OUUUUUUUUO",
    "OUUUUUUUUO",
    "OUOUUUUOUO",
    "OUUUUUUUUO",
    "OOOOOOOOOO",
]

def draw_chomper(screen, x, y, frame_count):
    # Pipe plant, 24 wide x 32 tall; x, y is the top-left corner
    head = CHOMPER_OPEN_HEAD if (frame_count // 10) % 2 else CHOMPER_CLOSED_HEAD
    screen.blit(make_sprite(head + CHOMPER_STEM, SPRITE_COLORS), (x, y))

def draw_mushroom(screen, x, y):
    screen.blit(make_sprite(MUSHROOM_PIXELS, SPRITE_COLORS), (x, y))

def draw_box(screen, x, y, hit, frame_count):
    if hit:
        screen.blit(make_sprite(USED_BOX_PIXELS, SPRITE_COLORS), (x, y))
    else:
        # Shimmer: the gold gets a little brighter every so often
        bright = (frame_count // 20) % 3 == 0
        colors = dict(SPRITE_COLORS, Q=(255, 210, 90)) if bright else SPRITE_COLORS
        screen.blit(make_sprite(BOX_PIXELS, colors), (x, y))

def draw_pipe(screen, x, y, w, h):
    # Body with a shine on the left and shadow on the right
    pygame.draw.rect(screen, GB_GREEN_MED, (x, y, w, h))
    pygame.draw.rect(screen, GB_GREEN_LIGHT, (x + 6, y, 4, h))
    pygame.draw.rect(screen, (30, 75, 30), (x + w - 8, y, 6, h))
    pygame.draw.rect(screen, GB_GREEN_DARK, (x, y, w, h), 2)
    # Wider lip on top
    pygame.draw.rect(screen, GB_GREEN_MED, (x - 4, y, w + 8, 14))
    pygame.draw.rect(screen, GB_GREEN_LIGHTEST, (x + 2, y + 2, 4, 10))
    pygame.draw.rect(screen, (30, 75, 30), (x + w - 6, y + 2, 6, 10))
    pygame.draw.rect(screen, GB_GREEN_DARK, (x - 4, y, w + 8, 14), 2)


# --- LEVEL DATA ---

def staircase(x, steps, up=True):
    # Each step is 20 wide and 16 taller than the last, standing on the ground
    rects = []
    for i in range(steps):
        h = 56 + 16 * (i if up else steps - 1 - i)
        rects.append(pygame.Rect(x + i * 20, GROUND_Y - h, 20, h))
    return rects

def coin(x, y):
    return {"x": x, "y": y, "collected": False}

def box(x, y, contents="coin"):
    return {"x": x, "y": y, "hit": False, "contents": contents}

def enemy(x, kind="goomba"):
    e = {"x": x, "y": GROUND_Y - ENEMY_H, "vy": 0, "dir": -1, "alive": True, "active": False, "type": kind}
    if kind == "koopa":
        e["shell"] = False
        e["grace"] = 0
    return e

def build_level(n):
    # Low brick rows sit at y=430 (reachable from the ground), high rows at
    # y=340 (reachable from a low row or a tall pipe). Boxes float 100px above
    # the row they belong to, or at y=440 over open ground.
    if n == 1:
        return {
            "goal_x": 3050,
            "platforms": [
                pygame.Rect(380, 430, 80, 16),
                pygame.Rect(550, 400, 60, 16),
                pygame.Rect(820, 430, 100, 16),
                pygame.Rect(1060, 400, 80, 16),
                pygame.Rect(1300, 430, 140, 16),
                pygame.Rect(1520, 400, 80, 16),
                pygame.Rect(1820, 430, 80, 16),
            ] + staircase(2100, 8) + staircase(2340, 8, up=False) + staircase(2720, 8),
            "pipes": [
                pygame.Rect(300, 496, 40, 64),
                pygame.Rect(700, 464, 40, 96),
                pygame.Rect(1180, 432, 40, 128),
                pygame.Rect(1960, 464, 40, 96),
                pygame.Rect(2580, 496, 40, 64),
            ],
            "pits": [(620, 680), (1460, 1530), (2260, 2340)],
            "chompers": [1, 3],  # which pipes have a plant in them
            "coins": [
                coin(420, 400), coin(590, 370), coin(860, 400), coin(900, 400),
                coin(1100, 370), coin(1340, 400), coin(1380, 400), coin(1560, 370),
                coin(1860, 400), coin(1900, 400),
            ],
            "enemies": [
                enemy(450), enemy(530), enemy(920), enemy(1260, "koopa"),
                enemy(1580), enemy(1740), enemy(2070, "koopa"), enemy(2530),
            ],
            "boxes": [
                box(220, 440), box(410, 330, "mushroom"), box(850, 330), box(890, 330),
                box(1090, 300), box(1360, 330, "mushroom"), box(1550, 300), box(1850, 330),
            ],
        }

    if n == 2:
        return {
            "goal_x": 3200,
            "platforms": [
                pygame.Rect(150, 430, 60, 16),
                pygame.Rect(360, 340, 80, 16),
                pygame.Rect(520, 430, 60, 16),
                pygame.Rect(740, 340, 100, 16),
                pygame.Rect(960, 430, 80, 16),
                pygame.Rect(1160, 340, 60, 16),
                pygame.Rect(1320, 430, 120, 16),
                pygame.Rect(1560, 340, 80, 16),
                pygame.Rect(1800, 430, 100, 16),
                pygame.Rect(2060, 340, 80, 16),
                pygame.Rect(2260, 430, 60, 16),
                pygame.Rect(2440, 340, 100, 16),
            ] + staircase(2650, 8) + staircase(2900, 8),
            "pipes": [
                pygame.Rect(260, 432, 40, 128),
                pygame.Rect(620, 464, 40, 96),
                pygame.Rect(840, 432, 40, 128),
                pygame.Rect(1240, 464, 40, 96),
                pygame.Rect(1660, 432, 40, 128),
                pygame.Rect(2160, 464, 40, 96),
                pygame.Rect(2520, 432, 40, 128),
            ],
            "pits": [(1070, 1140), (2810, 2900)],
            "chompers": [2, 4, 6],
            "coins": [
                coin(400, 310), coin(780, 310), coin(820, 310), coin(1000, 400),
                coin(1200, 310), coin(1360, 400), coin(1400, 400), coin(1600, 310),
                coin(1840, 400), coin(1880, 400), coin(2100, 310), coin(2480, 310),
            ],
            "enemies": [
                enemy(400), enemy(480, "koopa"), enemy(680), enemy(760),
                enemy(1020, "koopa"), enemy(1290), enemy(1480), enemy(1560, "koopa"),
                enemy(1860), enemy(1940), enemy(2220, "koopa"), enemy(2300),
                enemy(2480), enemy(2580, "koopa"),
            ],
            "boxes": [
                box(390, 240, "mushroom"), box(780, 240), box(1180, 240),
                box(1370, 330, "mushroom"), box(1590, 240), box(2090, 240), box(2480, 240),
            ],
        }

    # Level 3: longer, more pits, more koopas
    return {
        "goal_x": 3800,
        "platforms": [
            pygame.Rect(160, 430, 80, 16),
            pygame.Rect(680, 430, 60, 16),
            pygame.Rect(780, 340, 80, 16),
            pygame.Rect(880, 430, 60, 16),
            pygame.Rect(1200, 430, 100, 16),
            pygame.Rect(1340, 340, 80, 16),
            pygame.Rect(1520, 430, 80, 16),
            pygame.Rect(1800, 430, 60, 16),
            pygame.Rect(1900, 340, 100, 16),
            pygame.Rect(2040, 430, 40, 16),
            pygame.Rect(2400, 430, 80, 16),
            pygame.Rect(2650, 430, 120, 16),
            pygame.Rect(3200, 392, 40, 168),
        ] + staircase(2960, 8) + staircase(3240, 8, up=False) + staircase(3480, 8),
        "pipes": [
            pygame.Rect(280, 496, 40, 64),
            pygame.Rect(600, 432, 40, 128),
            pygame.Rect(1100, 464, 40, 96),
            pygame.Rect(1700, 432, 40, 128),
            pygame.Rect(2300, 496, 40, 64),
            pygame.Rect(2900, 464, 40, 96),
        ],
        "pits": [(420, 500), (860, 960), (1400, 1490), (2000, 2100), (2500, 2580), (3120, 3200)],
        "chompers": [1, 3, 5],
        "coins": [
            coin(190, 400), coin(700, 400), coin(800, 310), coin(830, 310),
            coin(1220, 400), coin(1260, 400), coin(1360, 310), coin(1390, 310),
            coin(1550, 400), coin(1920, 310), coin(1960, 310), coin(2050, 400),
            coin(2420, 400), coin(2680, 400), coin(2740, 400),
        ],
        "enemies": [
            enemy(350), enemy(540, "koopa"), enemy(750), enemy(1000),
            enemy(1150, "koopa"), enemy(1250), enemy(1600), enemy(1650, "koopa"),
            enemy(1850), enemy(2200), enemy(2250, "koopa"), enemy(2450),
            enemy(2700), enemy(2800, "koopa"), enemy(2850),
        ],
        "boxes": [
            box(180, 330), box(700, 330, "mushroom"), box(800, 240), box(1000, 440),
            box(1240, 330), box(1360, 240, "mushroom"), box(1540, 330), box(1940, 240),
            box(2200, 440), box(2420, 330), box(2690, 330), box(2730, 330, "mushroom"),
        ],
    }

def build_ground(level_end, pits):
    segments = []
    x = 0
    for start, end in sorted(pits):
        if start > x:
            segments.append(pygame.Rect(x, GROUND_Y, start - x, 16))
        x = end
    segments.append(pygame.Rect(x, GROUND_Y, level_end - x, 16))
    return segments

def move_body(body, w, h, speed, solid_list):
    # Walk in body["dir"], turn around at walls, fall with gravity
    body["x"] += body["dir"] * speed
    rect = pygame.Rect(int(body["x"]), int(body["y"]), w, h)
    for solid, _, _ in solid_list:
        if body["dir"] and rect.colliderect(solid):
            body["x"] = solid.left - w if body["dir"] > 0 else solid.right
            body["dir"] *= -1
            rect.x = int(body["x"])
            break
    body["vy"] = min(body["vy"] + GRAVITY, MAX_FALL)
    body["y"] += body["vy"]
    rect.y = int(body["y"])
    for solid, _, _ in solid_list:
        if rect.colliderect(solid):
            body["y"] = solid.top - h if body["vy"] > 0 else solid.bottom
            body["vy"] = 0
            rect.y = int(body["y"])

def run_around(x, y, vy, direction):
    # Menu characters wander back and forth and hop now and then
    on_ground = y >= 480
    x += direction * 2
    if x < 0 or x > WIDTH - 30:
        direction *= -1
        x = max(0, min(x, WIDTH - 30))
    elif on_ground and random.random() < 0.005:
        direction *= -1
    if on_ground and random.random() < 0.015:
        vy = -8
    vy += GRAVITY
    y = min(y + vy, 480)
    if y >= 480:
        vy = 0
    return x, y, vy, direction

def draw_options(screen, font, options, selected, x, y):
    for i, text in enumerate(options):
        color = GB_GREEN_LIGHTEST if i == selected else GB_GREEN_MED
        screen.blit(font.render(text, True, color), (x, y + i * 50))


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Mario Games")
    clock = pygame.time.Clock()

    state = "attract"
    selected = 0
    character = "mario"
    menu_message_timer = 0

    mario_x = -30
    luigi_x = 640
    mario_y = 480
    luigi_y = 480
    mario_vy = 0
    luigi_vy = 0
    jumping = False
    mario_dir = -1
    luigi_dir = 1
    sub_selected = 0
    sub_options = ["Start Game", "Back to Main Menu"]

    font = pygame.font.Font(None, 36)
    small_font = pygame.font.Font(None, 20)
    title_font = pygame.font.Font(None, 60)
    hud_font = pygame.font.Font(None, 28)

    # Player position is in world coordinates; subtract camera_x to draw
    player_x = 50
    player_y = GROUND_Y - 40
    player_vy = 0
    camera_x = 0
    score = 0
    big_mario = False
    mario_w = 30
    mario_h = 40
    invincible = 0
    current_level = 1
    lives = 3
    player_facing = 1
    player_anim = 0
    frame_count = 0
    player_vx = 0.0
    time_left = LEVEL_TIME
    coin_count = 0
    death_timer = 0
    intro_timer = 0

    goal_x = 3050
    level_end = goal_x + 300
    exit_kind = "lower"
    exit_timer = 0
    bonus = {}

    ground = []
    platforms = []
    pipes = []
    coins = []
    enemies = []
    mystery_boxes = []
    mushrooms = []
    popups = []
    broken_bricks = []
    chompers = []

    def load_level(n):
        nonlocal goal_x, level_end
        for items in (ground, platforms, pipes, coins, enemies, mystery_boxes, mushrooms, popups, broken_bricks, chompers):
            items.clear()
        data = build_level(n)
        goal_x = data["goal_x"]
        level_end = goal_x + 300
        platforms.extend(data["platforms"])
        pipes.extend(data["pipes"])
        coins.extend(data["coins"])
        enemies.extend(data["enemies"])
        mystery_boxes.extend(data["boxes"])
        ground.extend(build_ground(level_end, data["pits"]))
        for i, pipe_index in enumerate(data["chompers"]):
            # "height" is how far the plant sticks out of the pipe (0 = hidden)
            chompers.append({"pipe": pipes[pipe_index], "height": 0, "phase": "hidden", "timer": 60 + 40 * i})

    def start_level(keep_power=False):
        nonlocal player_x, player_y, player_vy, camera_x, big_mario, mario_w, mario_h, invincible, player_facing
        nonlocal player_vx, time_left
        player_facing = 1
        player_vx = 0.0
        time_left = LEVEL_TIME
        if not keep_power:
            big_mario = False
            mario_w = 30
            mario_h = 40
        player_x = 50
        player_y = GROUND_Y - mario_h
        player_vy = 0
        camera_x = 0
        invincible = 0
        load_level(current_level)

    def new_game():
        nonlocal score, lives, current_level, coin_count
        score = 0
        lives = 3
        coin_count = 0
        current_level = 1
        start_level()

    def add_popup(x, y, text, show_coin=False):
        popups.append({"x": x, "y": y, "timer": 40, "text": text, "coin": show_coin})

    def add_coin(x, y):
        # Every 100 coins is worth an extra life
        nonlocal score, coin_count, lives
        score += 100
        coin_count += 1
        if coin_count >= 100:
            coin_count = 0
            lives += 1
            add_popup(x, y - 20, "1UP")

    def bump_enemies(solid):
        # Hitting a block from below knocks out whatever is standing on it
        nonlocal score
        for e in enemies:
            if not e["alive"] or e.get("squished"):
                continue
            feet_y = e["y"] + ENEMY_H
            if abs(feet_y - solid.top) <= 2 and e["x"] + ENEMY_W > solid.left and e["x"] < solid.right:
                e["alive"] = False
                score += 100
                add_popup(int(e["x"]), int(e["y"]) - 20, "+100")

    def set_big(big):
        nonlocal big_mario, mario_w, mario_h, player_y
        if big == big_mario:
            return
        old_h = mario_h
        big_mario = big
        mario_w, mario_h = (36, 60) if big else (30, 40)
        player_y += old_h - mario_h  # keep feet in the same place

    def lose_life():
        nonlocal lives, state, invincible, intro_timer
        lives -= 1
        if lives <= 0:
            state = "game_over"
        else:
            start_level()
            invincible = 60
            state = "level_intro"
            intro_timer = 120

    def hurt():
        # Returns True if the hit was fatal
        nonlocal invincible
        if invincible > 0:
            return False
        if big_mario:
            set_big(False)
            invincible = 90
            return False
        return True

    def hit_box(b):
        nonlocal score
        b["hit"] = True
        if b["contents"] == "mushroom":
            mushrooms.append({"x": b["x"], "y": b["y"], "vy": 0, "dir": 1, "rise": 16})
        else:
            add_coin(b["x"], b["y"])
            add_popup(b["x"], b["y"] - 20, "+100", show_coin=True)

    def break_brick(platform, center_x):
        nonlocal score
        brick_x = platform.x + ((center_x - platform.x) // 20) * 20
        brick_x = max(platform.x, min(brick_x, platform.right - 20))
        platforms.remove(platform)
        left_w = brick_x - platform.x
        right_x = brick_x + 20
        right_w = platform.right - right_x
        if left_w > 0:
            platforms.append(pygame.Rect(platform.x, platform.y, left_w, platform.height))
        if right_w > 0:
            platforms.append(pygame.Rect(right_x, platform.y, right_w, platform.height))
        broken_bricks.append({"x": brick_x,      "y": platform.y,                  "vx": -3, "vy": -7, "timer": 45})
        broken_bricks.append({"x": brick_x + 10, "y": platform.y,                  "vx":  3, "vy": -7, "timer": 45})
        broken_bricks.append({"x": brick_x,      "y": platform.y + platform.height, "vx": -2, "vy": -4, "timer": 45})
        broken_bricks.append({"x": brick_x + 10, "y": platform.y + platform.height, "vx":  2, "vy": -4, "timer": 45})
        score += 50

    def get_solids():
        solid_list = [(g, "ground", None) for g in ground]
        solid_list += [(p, "brick", p) for p in platforms]
        solid_list += [(p, "pipe", p) for p in pipes]
        solid_list += [(pygame.Rect(b["x"], b["y"], 20, 16), "box", b) for b in mystery_boxes]
        solid_list.append((pygame.Rect(goal_x - 70, LEDGE_Y, 200, 16), "ledge", None))
        return solid_list

    def finish_level():
        nonlocal state
        state = "victory" if current_level >= LAST_LEVEL else "level_complete"

    def start_bonus():
        # Ladder lottery: one rung per row, joining two neighbouring ladders
        nonlocal state
        prizes = ["1UP", "2UP", "3UP", "POWER"]
        random.shuffle(prizes)
        rungs = []
        left = random.randrange(3)
        for k in range(7):
            # Never repeat the same gap twice in a row, so the paths cross more
            left = random.choice([i for i in range(3) if i != left])
            rungs.append((190 + k * 40, left))
        bonus.clear()
        bonus.update({
            "phase": "choose", "cursor": 0, "timer": 0, "prizes": prizes,
            "rungs": rungs, "path": [], "x": 0, "y": 0, "prize": None,
        })
        state = "bonus"

    def bonus_go():
        # Trace the ladder from the chosen top to find where it ends up
        col = bonus["cursor"]
        path = [(BONUS_X[col], 150)]
        for rung_y, left in bonus["rungs"]:
            if left == col:
                path += [(BONUS_X[col], rung_y), (BONUS_X[col + 1], rung_y)]
                col += 1
            elif left == col - 1:
                path += [(BONUS_X[col], rung_y), (BONUS_X[col - 1], rung_y)]
                col -= 1
        path.append((BONUS_X[col], 450))
        bonus["x"], bonus["y"] = path[0]
        bonus["path"] = path
        bonus["prize"] = bonus["prizes"][col]
        bonus["phase"] = "climb"

    def give_bonus_prize():
        nonlocal lives
        prize = bonus["prize"]
        if prize == "POWER":
            set_big(True)
        else:
            lives += int(prize[0])

    def start_intro():
        nonlocal mario_x, luigi_x, mario_y, luigi_y, mario_vy, luigi_vy, jumping
        mario_x = -30
        luigi_x = 640
        mario_y = 480
        luigi_y = 480
        mario_vy = 0
        luigi_vy = 0
        jumping = False

    def start_running():
        # After the intro jump, the brothers split up and run around
        nonlocal mario_x, luigi_x, mario_y, luigi_y, mario_vy, luigi_vy, mario_dir, luigi_dir
        mario_x = 270
        luigi_x = 340
        mario_y = 480
        luigi_y = 480
        mario_vy = 0
        luigi_vy = 0
        mario_dir = -1
        luigi_dir = 1

    load_level(1)

    while True:
        frame_count += 1
        walk_frame = (frame_count // 8) % 2

        # 1. INPUT
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if state == "attract":
                    state = "menu"
                elif state == "smb3_intro":
                    start_running()
                    state = "smb3_menu"
                elif state in ("smb2_menu", "smb3_menu"):
                    if event.key == pygame.K_UP:
                        sub_selected = 0
                    if event.key == pygame.K_DOWN:
                        sub_selected = 1
                    if event.key == pygame.K_ESCAPE or (event.key == pygame.K_RETURN and sub_selected == 1):
                        menu_message_timer = 0
                        state = "menu"
                    elif event.key == pygame.K_RETURN:
                        menu_message_timer = 120
                elif state == "menu":
                    if event.key == pygame.K_RETURN:
                        sub_selected = 0
                        menu_message_timer = 0
                        if selected == 0:
                            state = "char_select"
                        elif selected == 1:
                            state = "smb2_menu"
                        else:
                            start_intro()
                            state = "smb3_intro"
                    if event.key == pygame.K_UP:
                        if selected > 0:
                            selected -= 1
                    if event.key == pygame.K_DOWN:
                        if selected < 2:
                            selected += 1
                elif state == "char_select":
                    if event.key == pygame.K_LEFT:
                        character = "mario"
                    if event.key == pygame.K_RIGHT:
                        character = "luigi"
                    if event.key == pygame.K_RETURN:
                        new_game()
                        state = "level_intro"
                        intro_timer = 120
                elif state == "playing":
                    if event.key in (pygame.K_ESCAPE, pygame.K_p):
                        state = "paused"
                elif state == "paused":
                    if event.key in (pygame.K_ESCAPE, pygame.K_p):
                        state = "playing"
                    if event.key == pygame.K_m:
                        state = "menu"
                elif state == "bonus":
                    if bonus["phase"] == "choose" and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        bonus_go()
                elif state == "level_complete":
                    if event.key == pygame.K_m:
                        state = "menu"
                    if event.key == pygame.K_n:
                        current_level += 1
                        start_level(keep_power=True)
                        state = "level_intro"
                        intro_timer = 120
                elif state in ("game_over", "victory"):
                    if event.key == pygame.K_r:
                        new_game()
                        state = "level_intro"
                        intro_timer = 120
                    if event.key == pygame.K_m:
                        state = "menu"

        # 2. UPDATE
        if menu_message_timer > 0:
            menu_message_timer -= 1

        if state in ("attract", "smb3_intro"):
            if mario_x < 270:
                mario_x += 3
            if luigi_x > 340:
                luigi_x -= 3

            if mario_x >= 270 and luigi_x <= 340 and not jumping:
                mario_vy = -8
                luigi_vy = -8
                jumping = True

            if jumping:
                mario_vy += GRAVITY
                mario_y += mario_vy
                luigi_vy += GRAVITY
                luigi_y += luigi_vy

                if mario_y >= 480 and mario_vy > 0:
                    mario_y = 480
                    luigi_y = 480
                    if state == "attract":
                        state = "menu"
                    else:
                        start_running()
                        state = "smb3_menu"

        elif state == "smb3_menu":
            mario_x, mario_y, mario_vy, mario_dir = run_around(mario_x, mario_y, mario_vy, mario_dir)
            luigi_x, luigi_y, luigi_vy, luigi_dir = run_around(luigi_x, luigi_y, luigi_vy, luigi_dir)

        elif state == "playing":
            if invincible > 0:
                invincible -= 1
            solid_list = get_solids()
            keys = pygame.key.get_pressed()

            # --- HORIZONTAL MOVEMENT ---
            # Speed builds up and dies down gradually. Hold Z or Shift to run.
            running = keys[pygame.K_z] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            top_speed = RUN_SPEED if running else WALK_SPEED
            want = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
            if want and player_vx * want < 0:
                player_vx += want * SKID  # turning around: skid to a stop first
            elif want:
                if abs(player_vx) < top_speed:
                    player_vx = want * min(abs(player_vx) + ACCEL, top_speed)
                else:
                    player_vx = want * max(abs(player_vx) - FRICTION, top_speed)
            elif player_vx > 0:
                player_vx = max(0.0, player_vx - FRICTION)
            else:
                player_vx = min(0.0, player_vx + FRICTION)
            if want:
                player_facing = want

            player_x += player_vx
            if player_x < camera_x or player_x > level_end - mario_w:
                player_x = max(camera_x, min(player_x, level_end - mario_w))
                player_vx = 0.0
            player_rect = pygame.Rect(int(player_x), int(player_y), mario_w, mario_h)
            moving = player_vx
            for solid, _, _ in solid_list:
                if moving and player_rect.colliderect(solid):
                    player_x = solid.left - mario_w if moving > 0 else solid.right
                    player_vx = 0.0
                    player_rect.x = int(player_x)

            # --- VERTICAL MOVEMENT ---
            prev_bottom = player_y + mario_h
            player_vy = min(player_vy + GRAVITY, MAX_FALL)
            player_y += player_vy
            player_rect.y = int(player_y)
            hits = [s for s in solid_list if player_rect.colliderect(s[0])]
            if hits:
                if player_vy > 0:
                    player_y = min(solid.top for solid, _, _ in hits) - mario_h
                else:
                    player_y = max(solid.bottom for solid, _, _ in hits)
                    # Bonk whatever is closest to the middle of the head
                    center_x = player_x + mario_w // 2
                    solid, kind, obj = min(hits, key=lambda s: abs(s[0].centerx - center_x))
                    if kind in ("box", "brick"):
                        bump_enemies(solid)
                    if kind == "box" and not obj["hit"]:
                        hit_box(obj)
                    elif kind == "brick" and big_mario and solid.height == 16:
                        break_brick(solid, center_x)
                player_vy = 0
                player_rect.y = int(player_y)

            feet = pygame.Rect(int(player_x), int(player_y) + mario_h, mario_w, 1)
            on_ground = any(feet.colliderect(solid) for solid, _, _ in solid_list)

            jump_held = keys[pygame.K_SPACE] or keys[pygame.K_UP]
            if jump_held and on_ground:
                # A running start gives a higher jump
                base_jump = -13 if character == "luigi" else -12
                player_vy = base_jump - abs(player_vx) * 0.3
            elif not jump_held and player_vy < -4:
                player_vy = -4  # let go early for a short hop

            # Legs apart in the air, swinging while walking (faster when running)
            if not on_ground or player_vy < 0:
                player_anim = 1
            elif abs(player_vx) > 0.3:
                player_anim = (frame_count // (5 if abs(player_vx) > WALK_SPEED else 8)) % 2
            else:
                player_anim = 0

            camera_x = max(camera_x, min(player_x - 200, level_end - WIDTH))

            # --- MUSHROOMS ---
            for m in mushrooms[:]:
                if m["rise"] > 0:
                    m["y"] -= 1
                    m["rise"] -= 1
                    continue
                move_body(m, 20, 16, MUSHROOM_SPEED, solid_list)
                if m["y"] > HEIGHT:
                    mushrooms.remove(m)
                elif player_rect.colliderect(pygame.Rect(int(m["x"]), int(m["y"]), 20, 16)):
                    mushrooms.remove(m)
                    set_big(True)
                    score += 1000
                    add_popup(int(m["x"]), int(m["y"]) - 10, "+1000")

            for popup in popups[:]:
                popup["y"] -= 2
                popup["timer"] -= 1
                if popup["timer"] <= 0:
                    popups.remove(popup)

            for brick in broken_bricks[:]:
                brick["vy"] += GRAVITY
                brick["x"] += brick["vx"]
                brick["y"] += brick["vy"]
                brick["timer"] -= 1
                if brick["timer"] <= 0:
                    broken_bricks.remove(brick)

            # --- ENEMIES ---
            died = False
            for e in enemies:
                if not e["alive"]:
                    continue
                if e.get("squished"):
                    e["squished"] -= 1
                    if e["squished"] <= 0:
                        e["alive"] = False
                    continue
                if not e["active"]:
                    # Enemies wait until they scroll on screen
                    if e["x"] < camera_x + WIDTH + 20:
                        e["active"] = True
                    else:
                        continue
                shell = e["type"] == "koopa" and e["shell"]
                if shell:
                    e["grace"] = max(0, e["grace"] - 1)
                    move_body(e, ENEMY_W, ENEMY_H, SHELL_SPEED, solid_list)
                else:
                    move_body(e, ENEMY_W, ENEMY_H, GOOMBA_SPEED, solid_list)
                if e["y"] > HEIGHT or e["x"] < camera_x - 300:
                    e["alive"] = False
                    continue

                enemy_rect = pygame.Rect(int(e["x"]), int(e["y"]), ENEMY_W, ENEMY_H)

                # A kicked shell knocks out anything it runs into
                if shell and e["dir"]:
                    for other in enemies:
                        if other is e or not other["alive"] or not other["active"]:
                            continue
                        if enemy_rect.colliderect(pygame.Rect(int(other["x"]), int(other["y"]), ENEMY_W, ENEMY_H)):
                            other["alive"] = False
                            score += 200
                            add_popup(int(other["x"]), int(other["y"]) - 20, "+200")

                if not player_rect.colliderect(enemy_rect):
                    continue
                stomped = prev_bottom <= enemy_rect.top + 8 and player_y + mario_h >= enemy_rect.top - 1
                if stomped:
                    if e["type"] == "koopa":
                        if not e["shell"]:
                            e["shell"] = True
                            e["dir"] = 0
                        elif e["dir"]:
                            e["dir"] = 0
                        else:
                            e["dir"] = 1 if player_rect.centerx < enemy_rect.centerx else -1
                            e["grace"] = 12
                    else:
                        e["squished"] = 30
                    score += 100
                    add_popup(int(e["x"]), int(e["y"]) - 20, "+100")
                    player_y = enemy_rect.top - mario_h
                    player_vy = -7
                elif shell and e["dir"] == 0:
                    # Kick a resting shell away from the player
                    e["dir"] = 1 if player_rect.centerx < enemy_rect.centerx else -1
                    e["x"] = player_rect.right if e["dir"] > 0 else player_rect.left - ENEMY_W
                    e["grace"] = 12
                elif not (shell and e["grace"]):
                    if hurt():
                        died = True
                        break
                    player_rect = pygame.Rect(player_x, int(player_y), mario_w, mario_h)

            # --- PIPE CHOMPERS ---
            # Cycle: hidden -> rising -> up (snapping) -> sinking -> hidden
            for ch in chompers:
                pipe = ch["pipe"]
                if ch["phase"] == "hidden":
                    player_near = player_rect.right > pipe.left - 40 and player_rect.left < pipe.right + 40
                    if player_near:
                        ch["timer"] = max(ch["timer"], 30)  # stay down while the player is close
                    else:
                        ch["timer"] -= 1
                        if ch["timer"] <= 0:
                            ch["phase"] = "rising"
                elif ch["phase"] == "rising":
                    ch["height"] += 1
                    if ch["height"] >= 32:
                        ch["phase"] = "up"
                        ch["timer"] = 60
                elif ch["phase"] == "up":
                    ch["timer"] -= 1
                    if ch["timer"] <= 0:
                        ch["phase"] = "sinking"
                elif ch["phase"] == "sinking":
                    ch["height"] -= 1
                    if ch["height"] <= 0:
                        ch["phase"] = "hidden"
                        ch["timer"] = 90
                if ch["height"] > 4 and not died:
                    plant_rect = pygame.Rect(pipe.centerx - 10, pipe.y - ch["height"] + 2, 20, ch["height"] - 2)
                    if player_rect.colliderect(plant_rect) and hurt():
                        died = True

            # --- CLOCK ---
            if frame_count % TIME_TICK == 0:
                time_left -= 1

            if died or time_left <= 0:
                # Pop up, pause, then fall off the screen
                state = "dying"
                death_timer = 120
                player_vy = -10
                player_vx = 0.0
            elif player_y > HEIGHT:
                state = "dying"
                death_timer = 60
                player_vx = 0.0
            else:
                for c in coins:
                    if c["collected"]:
                        continue
                    if player_rect.colliderect(pygame.Rect(c["x"], c["y"], 20, 20)):
                        c["collected"] = True
                        add_coin(c["x"], c["y"])

                # --- EXITS ---
                upper_door = pygame.Rect(goal_x + 70, LEDGE_Y - 60, 20, 60)
                lower_door = pygame.Rect(goal_x + 70, GROUND_Y - 60, 20, 60)
                for door, kind in ((upper_door, "upper"), (lower_door, "lower")):
                    if player_rect.colliderect(door):
                        state = "exiting"
                        exit_kind = kind
                        exit_timer = 40
                        player_vx = 0.0
                        player_vy = 0
                        break

        elif state == "dying":
            death_timer -= 1
            if death_timer < 90:
                player_vy = min(player_vy + GRAVITY, MAX_FALL)
                player_y += player_vy
            if death_timer <= 0:
                lose_life()

        elif state == "level_intro":
            intro_timer -= 1
            if intro_timer <= 0:
                state = "playing"

        elif state == "exiting":
            # Player has gone through a door: pause, cash in the time, then move on
            for popup in popups[:]:
                popup["y"] -= 2
                popup["timer"] -= 1
                if popup["timer"] <= 0:
                    popups.remove(popup)
            if exit_timer > 0:
                exit_timer -= 1
            elif time_left > 0:
                step = min(4, time_left)
                time_left -= step
                score += step * 10
            elif exit_kind == "upper":
                start_bonus()
            else:
                finish_level()

        elif state == "bonus":
            if bonus["phase"] == "choose":
                # The pointer slides across the ladders; it picks by itself if you wait too long
                bonus["timer"] += 1
                if bonus["timer"] % 15 == 0:
                    bonus["cursor"] = (bonus["cursor"] + 1) % 4
                if bonus["timer"] >= 600:
                    bonus_go()
            elif bonus["phase"] == "climb":
                tx, ty = bonus["path"][1]
                bonus["x"] += max(-3, min(3, tx - bonus["x"]))
                bonus["y"] += max(-3, min(3, ty - bonus["y"]))
                if (bonus["x"], bonus["y"]) == (tx, ty):
                    bonus["path"].pop(0)
                    if len(bonus["path"]) == 1:
                        give_bonus_prize()
                        bonus["phase"] = "prize"
                        bonus["timer"] = 120
            else:
                bonus["timer"] -= 1
                if bonus["timer"] <= 0:
                    finish_level()

        # 3. DRAW
        screen.fill(GB_GREEN_DARK)
        if state in ("attract", "smb3_intro"):
            pygame.draw.rect(screen, GB_GREEN_MED, (0, 520, WIDTH, 16))
            draw_mario(screen, mario_x, mario_y, font, 1, 1 if jumping else walk_frame)
            draw_luigi(screen, luigi_x, luigi_y, font, -1, 1 if jumping else walk_frame)

        elif state == "menu":
            color1 = GB_GREEN_LIGHTEST if selected == 0 else GB_GREEN_MED
            color2 = GB_GREEN_LIGHTEST if selected == 1 else GB_GREEN_MED
            color3 = GB_GREEN_LIGHTEST if selected == 2 else GB_GREEN_MED
            screen.blit(font.render("Super Mario Land", True, color1), (200, 200))
            screen.blit(font.render("Super Mario Bros 2", True, color2), (200, 260))
            screen.blit(font.render("Super Mario Bros 3", True, color3), (200, 320))
            screen.blit(small_font.render("UP/DOWN to choose, ENTER to start", True, GB_GREEN_MED), (200, 520))

        elif state == "smb2_menu":
            # Brick frame around the whole screen
            draw_brick(screen, 0, 0, WIDTH, 32)
            draw_brick(screen, 0, HEIGHT - 32, WIDTH, 32)
            draw_brick(screen, 0, 32, 32, HEIGHT - 64)
            draw_brick(screen, WIDTH - 32, 32, 32, HEIGHT - 64)
            title = title_font.render("Super Mario Bros 2", True, GB_GREEN_LIGHTEST)
            screen.blit(title, ((WIDTH - title.get_width()) // 2, 110))
            draw_big_mario(screen, 120, 260, font)
            draw_big_luigi(screen, WIDTH - 156, 260, font, -1)
            draw_options(screen, font, sub_options, sub_selected, 210, 300)
            if menu_message_timer > 0:
                screen.blit(font.render("Coming soon!", True, GB_BROWN_LIGHT), (240, 440))
            screen.blit(small_font.render("ESC to go back", True, GB_GREEN_MED), (270, 510))

        elif state == "smb3_menu":
            pygame.draw.rect(screen, GB_GREEN_MED, (0, 520, WIDTH, 16))
            title = title_font.render("Super Mario Bros 3", True, GB_GREEN_LIGHTEST)
            screen.blit(title, ((WIDTH - title.get_width()) // 2, 140))
            draw_options(screen, font, sub_options, sub_selected, 210, 260)
            if menu_message_timer > 0:
                screen.blit(font.render("Coming soon!", True, GB_BROWN_LIGHT), (240, 390))
            draw_mario(screen, mario_x, mario_y, font, mario_dir, 1 if mario_y < 480 else walk_frame)
            draw_luigi(screen, luigi_x, luigi_y, font, luigi_dir, 1 if luigi_y < 480 else walk_frame)

        elif state == "char_select":
            screen.blit(font.render("Choose Your Character", True, GB_GREEN_LIGHTEST), (160, 150))
            mario_color = GB_GREEN_LIGHTEST if character == "mario" else GB_GREEN_MED
            luigi_color = GB_GREEN_LIGHTEST if character == "luigi" else GB_GREEN_MED
            screen.blit(font.render("< Mario", True, mario_color), (150, 280))
            screen.blit(font.render("Luigi >", True, luigi_color), (370, 280))
            draw_big_mario(screen, 180, 320, font)
            draw_big_luigi(screen, 400, 320, font, -1)
            screen.blit(small_font.render("Luigi jumps higher!", True, GB_GREEN_MED), (360, 395))
            screen.blit(small_font.render("ARROWS move   SPACE jump   Z run   P pause", True, GB_GREEN_MED), (170, 480))
            screen.blit(small_font.render("Press ENTER to start", True, GB_GREEN_LIGHTEST), (250, 510))

        elif state == "level_intro":
            world, stage = (current_level - 1) // 3 + 1, (current_level - 1) % 3 + 1
            title = title_font.render(f"WORLD {world}-{stage}", True, GB_GREEN_LIGHTEST)
            screen.blit(title, ((WIDTH - title.get_width()) // 2, 220))
            if character == "mario":
                draw_mario(screen, 270, 300, font)
            else:
                draw_luigi(screen, 270, 300, font)
            screen.blit(font.render(f"x  {lives}", True, GB_GREEN_LIGHTEST), (320, 310))

        elif state == "bonus":
            title = title_font.render("BONUS GAME", True, GB_GREEN_LIGHTEST)
            screen.blit(title, ((WIDTH - title.get_width()) // 2, 50))
            for bx in BONUS_X:
                pygame.draw.line(screen, GB_GREEN_LIGHT, (bx, 150), (bx, 450), 4)
            for rung_y, left in bonus["rungs"]:
                pygame.draw.line(screen, GB_GREEN_LIGHT, (BONUS_X[left], rung_y), (BONUS_X[left + 1], rung_y), 4)
            for i, bx in enumerate(BONUS_X):
                # Prizes stay hidden until the end
                revealed = bonus["phase"] == "prize"
                pygame.draw.rect(screen, GB_GREEN_MED, (bx - 44, 462, 88, 40))
                label = bonus["prizes"][i] if revealed else "?"
                text = hud_font.render(label, True, GB_GREEN_LIGHTEST)
                screen.blit(text, (bx - text.get_width() // 2, 473))
            if bonus["phase"] == "choose":
                cx = BONUS_X[bonus["cursor"]]
                hero_x, hero_y = cx - 15, 108
                pygame.draw.polygon(screen, (240, 180, 40), [(cx - 8, 98), (cx + 8, 98), (cx, 106)])
                hint = small_font.render("Press SPACE to pick a ladder", True, GB_GREEN_LIGHTEST)
                screen.blit(hint, ((WIDTH - hint.get_width()) // 2, 530))
            else:
                hero_x, hero_y = bonus["x"] - 15, bonus["y"] - 40
            climbing = bonus["phase"] == "climb"
            if character == "mario":
                draw_mario(screen, hero_x, hero_y, font, 1, walk_frame if climbing else 0)
            else:
                draw_luigi(screen, hero_x, hero_y, font, 1, walk_frame if climbing else 0)
            if bonus["phase"] == "prize":
                prize = bonus["prize"]
                message = "You got a power-up!" if prize == "POWER" else f"You got {prize}!"
                text = font.render(message, True, GB_BROWN_LIGHT)
                screen.blit(text, ((WIDTH - text.get_width()) // 2, 520))

        elif state in ("playing", "exiting", "paused", "dying"):
            draw_scenery(screen, camera_x)
            draw_goal(screen, goal_x - camera_x)
            for g in ground:
                pygame.draw.rect(screen, GB_GREEN_MED, (g.x - camera_x, g.y, g.width, g.height))
            for platform in platforms:
                draw_brick(screen, platform.x - camera_x, platform.y, platform.width, platform.height)
            for brick in broken_bricks:
                draw_brick(screen, int(brick["x"]) - camera_x, int(brick["y"]), 10, 8)
            # Plants are drawn first so the pipe hides the part still inside it
            for ch in chompers:
                if ch["height"] > 0:
                    draw_chomper(screen, ch["pipe"].centerx - 12 - camera_x, ch["pipe"].y - ch["height"], frame_count)
            for pipe in pipes:
                draw_pipe(screen, pipe.x - camera_x, pipe.y, pipe.width, pipe.height)
            for m in mushrooms:
                draw_mushroom(screen, int(m["x"]) - camera_x, int(m["y"]))
            for b in mystery_boxes:
                draw_box(screen, b["x"] - camera_x, b["y"], b["hit"], frame_count)
            enemy_frame = (frame_count // 10) % 2
            for e in enemies:
                if not e["alive"]:
                    continue
                ex, ey = int(e["x"]) - camera_x, int(e["y"])
                if e["type"] == "koopa":
                    if e["shell"]:
                        draw_shell(screen, ex, ey)
                    else:
                        draw_koopa(screen, ex, ey, 1 if e["dir"] >= 0 else -1, enemy_frame)
                elif e.get("squished"):
                    draw_squished_goomba(screen, ex, ey)
                else:
                    draw_goomba(screen, ex, ey, enemy_frame)
            for c in coins:
                if not c["collected"]:
                    draw_coin(screen, c["x"] - camera_x, c["y"], frame_count)
            for popup in popups:
                px, py = popup["x"] - camera_x, int(popup["y"])
                if popup["coin"]:
                    pygame.draw.circle(screen, GB_BROWN_LIGHT, (px + 10, py + 10), 10)
                screen.blit(small_font.render(popup["text"], True, GB_GREEN_LIGHTEST), (px, py - 10))
            # Blink while invincible; hidden once through a door
            if state != "exiting" and (invincible == 0 or (invincible // 4) % 2 == 0):
                sx, sy = player_x - camera_x, int(player_y)
                if character == "mario":
                    if big_mario:
                        draw_big_mario(screen, sx, sy, font, player_facing, player_anim)
                    else:
                        draw_mario(screen, sx, sy, font, player_facing, player_anim)
                else:
                    if big_mario:
                        draw_big_luigi(screen, sx, sy, font, player_facing, player_anim)
                    else:
                        draw_luigi(screen, sx, sy, font, player_facing, player_anim)
            # HUD: labels on top, values underneath
            world, stage = (current_level - 1) // 3 + 1, (current_level - 1) % 3 + 1
            hud = [
                (20, character.upper(), f"{score:06d}"),
                (170, "COINS", f"x{coin_count:02d}"),
                (290, "WORLD", f"{world}-{stage}"),
                (420, "TIME", f"{max(time_left, 0):03d}"),
                (540, "LIVES", f"x{lives}"),
            ]
            for hx, label, value in hud:
                screen.blit(hud_font.render(label, True, GB_GREEN_LIGHTEST), (hx, 8))
                time_low = label == "TIME" and time_left <= 100 and state == "playing"
                color = GB_RED_MED if time_low else GB_GREEN_LIGHTEST
                screen.blit(hud_font.render(value, True, color), (hx, 30))

            if state == "paused":
                screen.blit(font.render("PAUSED", True, GB_GREEN_LIGHTEST), (270, 230))
                screen.blit(small_font.render("P to resume, M for main menu", True, GB_GREEN_LIGHTEST), (215, 270))

        elif state == "level_complete":
            screen.blit(font.render("Level Complete!", True, GB_GREEN_LIGHTEST), (180, 200))
            screen.blit(font.render("Press N for next level", True, GB_GREEN_MED), (180, 280))
            screen.blit(font.render("Press M for main menu", True, GB_GREEN_MED), (180, 330))
            screen.blit(font.render(f"Score: {score}", True, GB_GREEN_LIGHTEST), (180, 380))

        elif state == "victory":
            screen.blit(font.render("YOU WIN!", True, GB_GREEN_LIGHTEST), (255, 180))
            screen.blit(font.render("All levels cleared!", True, GB_GREEN_LIGHT), (200, 230))
            screen.blit(font.render(f"Final Score: {score}", True, GB_GREEN_LIGHTEST), (210, 290))
            screen.blit(font.render("Press R to play again", True, GB_GREEN_MED), (185, 350))
            screen.blit(font.render("Press M for main menu", True, GB_GREEN_MED), (180, 400))

        elif state == "game_over":
            screen.blit(font.render("GAME OVER", True, GB_RED_MED), (220, 200))
            screen.blit(font.render(f"Score: {score}", True, GB_GREEN_LIGHTEST), (230, 270))
            screen.blit(font.render("Press R to restart", True, GB_GREEN_MED), (190, 330))
            screen.blit(font.render("Press M for main menu", True, GB_GREEN_MED), (170, 380))

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

asyncio.run(main())
