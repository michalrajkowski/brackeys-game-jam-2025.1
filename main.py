# Code was based on: https://github.com/kitao/pyxel/blob/main/python/pyxel/examples/10_platformer.py


import pyxel
import math
import logging
from enum import Enum, auto
import random

SCREEN_W, SCREEN_H = (128, 128)
MAP_SIZE_BLOCKS_X, MAP_SIZE_BLOCKS_Y = 256, 256

TRANSPARENT_COLOR = 2
SCROLL_BORDER_X = 80
SCROLL_BORDER_Y = 80
TILE_FLOOR = (1, 0)
TILE_SPAWN1 = (0, 1)
TILE_SPAWN2 = (1, 1)
TILE_SPAWN3 = (2, 1)
WALL_TILE_X = 4
VOID_TILE = (0,0)

class BlockID(Enum):
    AIR = auto()
    GRASS = auto()
    DIRT = auto()
    STONE = auto()

scroll_x, scroll_y = 0, 0
player = None
input = None
mining_helper = None
blocks_handler = None
enemies = []

logging.basicConfig(
    level=logging.DEBUG,  # Set the log level to DEBUG (or another level like INFO, WARNING)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Include timestamp, log level, and message
    datefmt='%Y-%m-%d %H:%M:%S',  # Format for the timestamp
)

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

def get_tile(tile_x, tile_y):
    return pyxel.tilemaps[1].pget(tile_x, tile_y)

def destroy_block(tile_x,tile_y):
    blocks_handler.destroy_block(tile_x, tile_y)

def is_colliding(x, y, is_falling):
    # Get player new bounding box:
    x1 = pyxel.floor(x) // 8 
    y1 = (pyxel.floor(y)) // 8
    x2 = (pyxel.ceil(x) + 7) // 8
    y2 = (pyxel.ceil(y) + 7) // 8

    print(x1, y1, x2, y2)

    # Check if player is completly in empty space!
    for yi in range(y1, y2 + 1):
        for xi in range(x1, x2 + 1):
            if blocks_handler.is_solid(xi, yi):
                return True
    
    # Legacy code!
    # if is_falling and y % 8 == 1:
    #     for xi in range(x1, x2 + 1):
    #         if get_tile(xi, y1 + 1) == TILE_FLOOR:
    #             return True
    return False

def is_close_enough(entity_x, entity_y, block_x, block_y, proximity=4):
    # Define the entity's bounding box corners
    entity_corners = [
        (entity_x, entity_y),  # top-left
        (entity_x + 7, entity_y),  # top-right
        (entity_x, entity_y + 7),  # bottom-left
        (entity_x + 7, entity_y + 7),  # bottom-right
    ]
    
    # Define the block's bounding box corners
    block_corners = [
        (block_x, block_y),  # top-left
        (block_x + 7, block_y),  # top-right
        (block_x, block_y + 7),  # bottom-left
        (block_x + 7, block_y + 7),  # bottom-right
    ]
    
    # Check if any corner of the entity is within the proximity of the block
    for ex, ey in entity_corners:
        for bx, by in block_corners:
            # Check if the distance between entity corner and block corner is within proximity
            if abs(ex - bx) <= proximity and abs(ey - by) <= proximity:
                return True  # Entity is close enough to the block
                
    return False  # No proximity found

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


def is_wall(block_x, block_y):
    return blocks_handler.is_solid(block_x, block_y)

def cleanup_entities(entities):
    for i in range(len(entities) - 1, -1, -1):
        if not entities[i].is_alive:
            del entities[i]

class MiningHelper:
    def __init__(self, required_hits=45):
        self.current_block = None  # Track only one mined block
        self.mining_hits = 0
        self.required_hits = required_hits

    def mine(self, x, y):
        block_pos = (x, y)
        
        if self.current_block != block_pos:
            self.current_block = block_pos
            self.mining_hits = 0  # Reset progress when switching blocks
        
        self.mining_hits += 1
        
        if self.mining_hits >= self.required_hits:
            destroy_block(block_pos[0], block_pos[1])
            self.current_block = None
            self.mining_hits = 0
    
    def draw(self):
        if not self.current_block:
            return
        x, y = self.current_block[0] * 8, self.current_block[1] * 8
        progress = self.mining_hits / self.required_hits

        # Define the number of dots for the rectangle's perimeter
        total_dots = 32  # 8 dots per side for an 8x8 block

        # Calculate the number of filled dots based on progress
        filled_dots = int(total_dots * progress)

        # Draw top side
        for i in range(8):
            if i < filled_dots:
                pyxel.pset(x + i, y - 1, 7)  # Filled dot
            else:
                pyxel.pset(x + i, y - 1, 13)  # Unfilled dot

        # Draw right side
        for i in range(8):
            if 8 + i < filled_dots:
                pyxel.pset(x + 8, y + i, 7)  # Filled dot
            else:
                pyxel.pset(x + 8, y + i, 13)  # Unfilled dot

        # Draw bottom side
        for i in range(8):
            if 16 + i < filled_dots:
                pyxel.pset(x + 7 - i, y + 8, 7)  # Filled dot
            else:
                pyxel.pset(x + 7 - i, y + 8, 13)  # Unfilled dot

        # Draw left side
        for i in range(8):
            if 24 + i < filled_dots:
                pyxel.pset(x - 1, y + 7 - i, 7)  # Filled dot
            else:
                pyxel.pset(x - 1, y + 7 - i, 13)  # Unfilled dot
    
    def reset(self):
        self.current_block = None
        self.mining_hits = 0

# === Static Block Data ===
class Blocks:
    # Block properties stored in a dictionary (no instance data)
    TEXTURES = {
        BlockID.AIR: (48, 112, 8, 8),
        BlockID.GRASS: (48, 104, 8, 8),
        BlockID.DIRT: (48, 80, 8, 8),
        BlockID.STONE: (48, 64, 8, 8),
    }

    SOLIDITY = {
        BlockID.AIR: False,
        BlockID.GRASS: True,
        BlockID.DIRT: True,
        BlockID.STONE: True,
    }

    MINING_HITS = {
        BlockID.AIR: 0,
        BlockID.GRASS: 5,
        BlockID.DIRT: 10,
        BlockID.STONE: 20,
    }

    @staticmethod
    def get_texture(block_id):
        return Blocks.TEXTURES.get(block_id, (0, 0, 0, 0))

    @staticmethod
    def is_solid(block_id):
        return Blocks.SOLIDITY.get(block_id, True)

    @staticmethod
    def get_mining_hits(block_id):
        return Blocks.MINING_HITS.get(block_id, 0)

# === Block Map Handler ===
class BlocksHandler:
    def __init__(self):
        self.blocks_map: dict[tuple[int, int], BlockID] = {}
        self.generate_map()

    def destroy_block(self, block_x, block_y):
        if not self.is_in_range(block_x, block_y):
            return
        self.blocks_map[(block_x, block_y)] = BlockID.AIR

    def is_solid(self, block_x, block_y) -> bool:
        if not self.is_in_range(block_x, block_y):
            return False
        return Blocks.is_solid(self.get_block_id(block_x, block_y))

    def generate_map(self):
        for i in range(MAP_SIZE_BLOCKS_X):
            for j in range(MAP_SIZE_BLOCKS_Y):
                if j > 6:
                    self.blocks_map[(i, j)] = BlockID.DIRT
                    # self.blocks_map[(i, j)] = random.choice(list(BlockID))
                else:
                    self.blocks_map[(i, j)] = BlockID.AIR
    def is_in_range(self, block_x, block_y):
        return 0 <= block_x < MAP_SIZE_BLOCKS_X and 0 <= block_y < MAP_SIZE_BLOCKS_Y

    def set_block(self, block_x, block_y, block_id):
        if self.is_in_range(block_x, block_y):
            self.blocks_map[(block_x, block_y)] = block_id

    def get_block_id(self, block_x, block_y):
        return self.blocks_map.get((block_x, block_y), BlockID.AIR)

    def get_block_image(self, block_x, block_y):
        block_id = self.get_block_id(block_x, block_y)
        return Blocks.get_texture(block_id)

    def draw(self):
        start_x = scroll_x // 8 - 1
        start_y = scroll_y // 8 - 1
        end_x = (scroll_x + 128) // 8 + 1
        end_y = (scroll_y + 128) // 8 + 1

        for block_x in range(start_x, end_x + 1):
            for block_y in range(start_y, end_y + 1):
                self.draw_block(block_x, block_y, scroll_x, scroll_y)

    def draw_block(self, block_x, block_y, scroll_x, scroll_y):
        if not self.is_in_range(block_x, block_y):
            return

        block_image = self.get_block_image(block_x, block_y)
        
        # Convert block grid position to screen position
        screen_x = block_x * 8 - scroll_x
        screen_y = block_y * 8 - scroll_y

        pyxel.blt(screen_x, screen_y, 0, *block_image, TRANSPARENT_COLOR)


class InputHandler:
    def __init__(self, double_click_time=10, hold_time=5):
        self.keys = {
            "left": [pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT],
            "right": [pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT],
            "down": [pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN],
            "jump": [pyxel.KEY_SPACE, pyxel.KEY_W, pyxel.GAMEPAD1_BUTTON_DPAD_UP, pyxel.GAMEPAD1_BUTTON_A],
        }
        self.states = {key: {"pressed": False,"long_pressed":False, "held": False, "double_click": False, "last_press_time": -double_click_time} for key in self.keys}
        self.double_click_time = double_click_time
        self.hold_time = hold_time
        self.hold_counters = {key: 0 for key in self.keys}

    def update(self):
        for action, keys in self.keys.items():
            pressed_now = any(pyxel.btnp(k) for k in keys)
            held_now = any(pyxel.btn(k) for k in keys)

            # Double Click Detection
            self.states[action]["double_click"] = False
            if pressed_now:
                if pyxel.frame_count - self.states[action]["last_press_time"] <= self.double_click_time:
                    self.states[action]["double_click"] = True
                self.states[action]["last_press_time"] = pyxel.frame_count

            # Holding Detection
            if held_now:
                self.hold_counters[action] += 1
                self.states[action]["held"] = self.hold_counters[action] >= self.hold_time
            else:
                self.hold_counters[action] = 0
                self.states[action]["held"] = False

            self.states[action]["pressed"] = pressed_now
            self.states[action]["long_pressed"] = held_now
        for key, state in self.states.items():
            if state["double_click"]:
                print(key)

    def is_pressed(self, action):
        return self.states[action]["pressed"]

    def is_long_pressed(self, action):
        return self.states[action]["long_pressed"]

    def is_held(self, action):
        return self.states[action]["held"]

    def is_double_click(self, action):
        return self.states[action]["double_click"]

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
        if input.is_long_pressed("left"):
            self.dx = -2
            self.direction = -1
        if input.is_long_pressed("right"):
            self.dx = 2
            self.direction = 1
        self.dy = min(self.dy + 1, 3)
        if input.is_pressed("jump"):
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

        # Handle mining:
        # If button is held + player is in proximity he starts mining (only true holding counts (this with delay))
        # 1. Look at held direction
        # 2. Look at marked block (proximity + blocktype)
        # 3. Start mining it if it is valid!
        marked_blocks = self.get_marker_blocks()
        pre_mining_progress = mining_helper.mining_hits
        for key,state in input.states.items():
            if input.is_held(key):
                # get marked blocks assiciated with key
                mined_blocks_coords = None
                for blocks in marked_blocks:
                    if blocks[2] == key:
                        mined_blocks_coords = (blocks[0], blocks[1])
                        print("FOUND!")
                        break
                if mined_blocks_coords == None:
                    continue
                if not is_wall(*mined_blocks_coords):
                    continue
                # Proximity check:
                logging.debug("Possible to mine!")
                # Mine, mine, mine!
                mining_helper.mine(*mined_blocks_coords)                
                break
        if not (mining_helper.mining_hits > pre_mining_progress):
            # Reset mining
            mining_helper.reset()

        # Handle doubleclicks:

    # left, right, down

    # Marker blocks = blocks that are in player proximity if solid?
    def get_marker_blocks(self):
        player_middle_x,player_middle_y = pyxel.floor(self.x + 4), pyxel.floor(self.y + 4)

        directions = [(0, 1),(0, -1),(1, 0),(-1, 0)]
        directions_names = ["down","jump","right","left"]
        neighbour_points = [(player_middle_x + dx * 8, player_middle_y + dy * 8, directions_names[directions.index((dx,dy))]) for dx, dy in directions]

        marker_blocks = []
        for nei_point in neighbour_points:
            (px, py, dir_name) = nei_point
            bx, by = px//8, py//8
            if not blocks_handler.is_solid(bx, by):
                continue
            if not is_close_enough(self.x, self.y, bx*8, by*8):
                continue
            marker_blocks.append((bx, by, dir_name))
        return marker_blocks

    def draw(self):
        u = (2 if self.is_falling else pyxel.frame_count // 3 % 2) * 8
        w = 8 if self.direction > 0 else -8
        pyxel.blt(self.x, self.y, 0, u, 16, w, 8, TRANSPARENT_COLOR)
    
    def draw_block_markers(self):
        # Define the marker graphics
        marker_graphic = (0, 64, 8, 8)
        marker_graphic_hit = (8, 64, 8, 8)
        
        marker_blocks = self.get_marker_blocks()
        
        # Determine the correct marker based on mining hits
        if mining_helper.current_block and ((mining_helper.mining_hits)% 30 < 7):
            marker = marker_graphic_hit
        else:
            marker = marker_graphic
        
        for block in marker_blocks:
            (bx, by, block_name) = block
            pyxel.blt(bx*8, by*8, 0, *marker, TRANSPARENT_COLOR)

class App:
    def __init__(self):
        pyxel.init(128, 128, title="2D Miner")
        pyxel.load("assets/miner.pyxres")

        # Change enemy spawn tiles invisible
        pyxel.images[0].rect(0, 8, 24, 8, TRANSPARENT_COLOR)

        global player, input, mining_helper, blocks_handler
        player = Player(0, 0)
        input = InputHandler()
        mining_helper = MiningHelper()
        blocks_handler = BlocksHandler()
        pyxel.playm(0, loop=True)
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btn(pyxel.KEY_Q):
            pyxel.quit()

        input.update() 
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

        # pyxel.bltm(0, 0, 2, (scroll_x // 4) % 128, (scroll_y // 4) % 128, 128, 128) # Background
        # pyxel.bltm(0, 0, 1, scroll_x, scroll_y, 128, 128, TRANSPARENT_COLOR) # Foreground
        
        # Render map with block handler:
        blocks_handler.draw()
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

        # Draw gizmos
        mining_helper.draw()


def game_over():
    global scroll_x,scroll_y, enemies
    scroll_x = 0
    scroll_y = 0
    player.x = 0
    player.y = 0
    player.dx = 0
    player.dy = 0
    enemies = []
    pyxel.play(3, 9)


App()