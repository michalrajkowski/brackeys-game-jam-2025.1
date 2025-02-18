# Code was based on: https://github.com/kitao/pyxel/blob/main/python/pyxel/examples/10_platformer.py

import pyxel
import math

SCREEN_W, SCREEN_H = (128, 128)

TRANSPARENT_COLOR = 2
SCROLL_BORDER_X = 80
SCROLL_BORDER_Y = 80
TILE_FLOOR = (1, 0)
TILE_SPAWN1 = (0, 1)
TILE_SPAWN2 = (1, 1)
TILE_SPAWN3 = (2, 1)
WALL_TILE_X = 4

scroll_x, scroll_y = 0, 0
player = None
enemies = []

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

def get_tile(tile_x, tile_y):
    return pyxel.tilemaps[1].pget(tile_x, tile_y)


def is_colliding(x, y, is_falling):
    x1 = pyxel.floor(x) // 8
    y1 = pyxel.floor(y) // 8
    x2 = (pyxel.ceil(x) + 7) // 8
    y2 = (pyxel.ceil(y) + 7) // 8
    for yi in range(y1, y2 + 1):
        for xi in range(x1, x2 + 1):
            if get_tile(xi, yi)[0] >= WALL_TILE_X:
                return True
    if is_falling and y % 8 == 1:
        for xi in range(x1, x2 + 1):
            if get_tile(xi, y1 + 1) == TILE_FLOOR:
                return True
    return False


def push_back(x, y, dx, dy):
    for _ in range(pyxel.ceil(abs(dy))):
        step = max(-1, min(1, dy))
        if is_colliding(x, y + step, dy > 0):
            break
        y += step
        dy -= step
    for _ in range(pyxel.ceil(abs(dx))):
        step = max(-1, min(1, dx))
        if is_colliding(x + step, y, dy > 0):
            break
        x += step
        dx -= step
    return x, y


def is_wall(x, y):
    tile = get_tile(x // 8, y // 8)
    return tile == TILE_FLOOR or tile[0] >= WALL_TILE_X


def spawn_enemy(left_x, right_x):
    left_x = pyxel.ceil(left_x / 8)
    right_x = pyxel.floor(right_x / 8)
    for x in range(left_x, right_x + 1):
        for y in range(16):
            tile = get_tile(x, y)
            if tile == TILE_SPAWN1:
                enemies.append(Enemy1(x * 8, y * 8))
            elif tile == TILE_SPAWN2:
                enemies.append(Enemy2(x * 8, y * 8))
            elif tile == TILE_SPAWN3:
                enemies.append(Enemy3(x * 8, y * 8))


def cleanup_entities(entities):
    for i in range(len(entities) - 1, -1, -1):
        if not entities[i].is_alive:
            del entities[i]


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.dx = 0
        self.dy = 0
        self.direction = 1
        self.is_falling = False

    def update(self):
        global scroll_x
        global scroll_y
        last_y = self.y
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            self.dx = -2
            self.direction = -1
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            self.dx = 2
            self.direction = 1
        self.dy = min(self.dy + 1, 3)
        if pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_W) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_DPAD_UP) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A):
            self.dy = -6
            pyxel.play(3, 8)
        self.x, self.y = push_back(self.x, self.y, self.dx, self.dy)
        self.dx = int(self.dx * 0.8)
        self.is_falling = self.y > last_y

        self.x = clamp(self.x, 0, 248*8)
        self.y = clamp(self.y, 0, 248*8)

        if self.x > scroll_x + SCROLL_BORDER_X:
            last_scroll_x = scroll_x
            scroll_x = min(self.x - SCROLL_BORDER_X, 240 * 8)
            # spawn_enemy(last_scroll_x + 128, scroll_x + 127)
        if self.x < scroll_x + (SCREEN_W - SCROLL_BORDER_X):
            last_scroll_x = scroll_x
            scroll_x = max(self.x - (SCREEN_W - SCROLL_BORDER_X), 0)
            # spawn_enemy(last_scroll_x + 128, scroll_x + 127)
        if self.y > scroll_y + SCROLL_BORDER_Y:
            last_scroll_y = scroll_y
            scroll_y = min(self.y - SCROLL_BORDER_Y, 240 * 8)
            # spawn_enemy(last_scroll_x + 128, scroll_x + 127)
        if self.y < scroll_y + (SCREEN_H - SCROLL_BORDER_Y):
            last_scroll_y = scroll_y
            scroll_y = max(self.y - (SCREEN_H - SCROLL_BORDER_Y), 0)
            # spawn_enemy(last_scroll_x + 128, scroll_x + 127)
        

    def draw(self):
        u = (2 if self.is_falling else pyxel.frame_count // 3 % 2) * 8
        w = 8 if self.direction > 0 else -8
        pyxel.blt(self.x, self.y, 0, u, 16, w, 8, TRANSPARENT_COLOR)
    
    def draw_block_markers(self):
        # Define the marker graphic
        marker_graphic = (0, 64, 8, 8)
        
        # Calculate bottom marker position
        y_bottom = ((pyxel.ceil(self.y) + 7) // 8 + 1) * 8
        x_bottom = ((pyxel.floor(self.x + 4)) // 8) * 8  # Centered below player
        
        # Determine closest horizontal tile (left or right)
        x_left = ((pyxel.floor(self.x) - 1) // 8) * 8
        x_right = ((pyxel.ceil(self.x) + 7) // 8) * 8
        y_same = (pyxel.floor(self.y) // 8) * 8
        
        x_direction = x_left - 8 if self.direction < 0 else x_right+8
        
        # Draw the markers
        # TODO mark blocks that are not empty space!
        pyxel.blt(x_direction, y_same, 0, *marker_graphic, TRANSPARENT_COLOR)
        pyxel.blt(x_bottom, y_bottom, 0, *marker_graphic, TRANSPARENT_COLOR)


class Enemy1:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.dx = 0
        self.dy = 0
        self.direction = -1
        self.is_alive = True

    def update(self):
        self.dx = self.direction
        self.dy = min(self.dy + 1, 3)
        if self.direction < 0 and is_wall(self.x - 1, self.y + 4):
            self.direction = 1
        elif self.direction > 0 and is_wall(self.x + 8, self.y + 4):
            self.direction = -1
        self.x, self.y = push_back(self.x, self.y, self.dx, self.dy)

    def draw(self):
        u = pyxel.frame_count // 4 % 2 * 8
        w = 8 if self.direction > 0 else -8
        pyxel.blt(self.x, self.y, 0, u, 24, w, 8, TRANSPARENT_COLOR)


class Enemy2:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.dx = 0
        self.dy = 0
        self.direction = 1
        self.is_alive = True

    def update(self):
        self.dx = self.direction
        self.dy = min(self.dy + 1, 3)
        if is_wall(self.x, self.y + 8) or is_wall(self.x + 7, self.y + 8):
            if self.direction < 0 and (
                is_wall(self.x - 1, self.y + 4) or not is_wall(self.x - 1, self.y + 8)
            ):
                self.direction = 1
            elif self.direction > 0 and (
                is_wall(self.x + 8, self.y + 4) or not is_wall(self.x + 7, self.y + 8)
            ):
                self.direction = -1
        self.x, self.y = push_back(self.x, self.y, self.dx, self.dy)

    def draw(self):
        u = pyxel.frame_count // 4 % 2 * 8 + 16
        w = 8 if self.direction > 0 else -8
        pyxel.blt(self.x, self.y, 0, u, 24, w, 8, TRANSPARENT_COLOR)


class Enemy3:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.time_to_fire = 0
        self.is_alive = True

    def update(self):
        self.time_to_fire -= 1
        if self.time_to_fire <= 0:
            dx = player.x - self.x
            dy = player.y - self.y
            sq_dist = dx * dx + dy * dy
            if sq_dist < 60**2:
                dist = pyxel.sqrt(sq_dist)
                enemies.append(Enemy3Bullet(self.x, self.y, dx / dist, dy / dist))
                self.time_to_fire = 60

    def draw(self):
        u = pyxel.frame_count // 8 % 2 * 8
        pyxel.blt(self.x, self.y, 0, u, 32, 8, 8, TRANSPARENT_COLOR)


class Enemy3Bullet:
    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.is_alive = True

    def update(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self):
        u = pyxel.frame_count // 2 % 2 * 8 + 16
        pyxel.blt(self.x, self.y, 0, u, 32, 8, 8, TRANSPARENT_COLOR)


class App:
    def __init__(self):
        pyxel.init(128, 128, title="2D Miner")
        pyxel.load("assets/miner.pyxres")

        # Change enemy spawn tiles invisible
        pyxel.images[0].rect(0, 8, 24, 8, TRANSPARENT_COLOR)

        global player
        player = Player(0, 0)
        spawn_enemy(0, 127)
        pyxel.playm(0, loop=True)
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btn(pyxel.KEY_Q):
            pyxel.quit()

        player.update()
        for enemy in enemies:
            if abs(player.x - enemy.x) < 6 and abs(player.y - enemy.y) < 6:
                game_over()
                return
            enemy.update()
            if enemy.x < scroll_x - 8 or enemy.x > scroll_x + 160 or enemy.y > 160:
                enemy.is_alive = False
        cleanup_entities(enemies)

    def draw(self):
        pyxel.cls(0)

        # Draw level
        pyxel.camera()
        pyxel.bltm(0, 0, 2, (scroll_x // 4) % 128, (scroll_y // 4) % 128, 128, 128) # Background
        pyxel.bltm(0, 0, 1, scroll_x, scroll_y, 128, 128, TRANSPARENT_COLOR) # Foreground
        # Render fog of war:

        # Draw block mining markers
        # Player left, right, down - draw a mark around the blocks
        

        # Draw characters
        pyxel.camera(scroll_x, scroll_y)
        player.draw()
        # draw block markers?
        player.draw_block_markers()
        for enemy in enemies:
            enemy.draw()


def game_over():
    global scroll_x,scroll_y, enemies
    scroll_x = 0
    scroll_y = 0
    player.x = 0
    player.y = 0
    player.dx = 0
    player.dy = 0
    enemies = []
    spawn_enemy(0, 127)
    pyxel.play(3, 9)


App()