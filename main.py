# Code was based on: https://github.com/kitao/pyxel/blob/main/python/pyxel/examples/10_platformer.py


import pyxel
import math
import logging
from enum import Enum, auto
import random
from collections import deque

SCREEN_W, SCREEN_H = (128, 128)
MAP_SIZE_BLOCKS_X, MAP_SIZE_BLOCKS_Y = 90, 150

TRANSPARENT_COLOR = 2
SCROLL_BORDER_X = 80
SCROLL_BORDER_Y = 80
TILE_FLOOR = (1, 0)
TILE_SPAWN1 = (0, 1)
TILE_SPAWN2 = (1, 1)
TILE_SPAWN3 = (2, 1)
WALL_TILE_X = 4
VOID_TILE = (0,0)

DARKNESS_SPRITES = [(0,104+y*8,8,8) for y in range(9)]

class BlockID(Enum):
    AIR = auto()
    GRASS = auto()
    DIRT = auto()
    STONE = auto()
    HARD_STONE = auto()
    MAGMA_ROCK = auto()

class OreID(Enum):
    NONE = auto()
    GOLD = auto()
    DIAMONDS = auto()
    MITHRIL = auto()
    ALIENIUM = auto()

scroll_x, scroll_y = 0, 0
player = None
input = None
mining_helper = None
blocks_handler = None
ore_handler = None
inventory_handler = None
trigger_zones_handler = None
darkness_system = None
danger_handler = None
enemies = []

logging.basicConfig(
    level=logging.DEBUG,  # Set the log level to DEBUG (or another level like INFO, WARNING)
    format="%(asctime)s - %(levelname)s - %(message)s",  # Include timestamp, log level, and message
    datefmt="%Y-%m-%d %H:%M:%S",  # Format for the timestamp
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

    # print(x1, y1, x2, y2)

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

class DangerHandler:
    def __init__(self):
        self.danger_level=0

    def update(self):
        self.danger_level+=1/30/3

    def draw(self):
        danger_color = 7 if self.danger_level < 50 else (10 if self.danger_level < 75 else 8)
        pyxel.text(scroll_x+1,scroll_y+1,"Danger",danger_color)
        pyxel.text(scroll_x+1,scroll_y+9,f"{int(self.danger_level)}%".center(6),danger_color)

class DarknessSystem:
    def __init__(self, map_width = 16, map_height = 16):
        self.map_width = map_width
        self.map_height = map_height
        self.light_map = [[0 for _ in range(map_width)] for _ in range(map_height)]
    
    def update_lighting(self, world_player_x, world_player_y, base_light=9):
        self.light_map = [[0 for _ in range(self.map_width)] for _ in range(self.map_height)]
        block_player_x, block_player_y = world_player_x//8, world_player_y//8
        screen_player_x, screen_player_y = world_player_x - scroll_x, world_player_y - scroll_y
        block_screen_x, block_screen_y = screen_player_x//8, screen_player_y//8
        self.light_map[block_screen_y][block_screen_x] = base_light

        # Simple render around player:
        visited = set()
        queue = deque([(0, 0, base_light)])
        while queue:
            dx, dy, intensity = queue.popleft()
            if (dx, dy) in visited:
                continue

            if intensity <= 0:
                intensity = 0

            visited.add((dx, dy))
            if 0 <= block_screen_x+dx < self.map_width and 0 <= block_screen_y+dy < self.map_height:
                self.light_map[block_screen_y+dy][block_screen_x+dx] = intensity

            next_intensity = intensity
            next_intensity -= 0.5 if blocks_handler.get_block_id(block_player_x + dx, block_player_y + dy) in [BlockID.GRASS, BlockID.AIR] else 2.0

            directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            for mod_x, mod_y in directions:
                nx, ny = dx + mod_x, dy + mod_y
                if 0 <= block_screen_x+nx < self.map_width and 0 <= block_screen_y+dy < self.map_height and (nx, ny) not in visited:
                    queue.append((nx, ny, next_intensity))

    def render_darkness(self):
        for y in range(len(self.light_map)):
            for x in range(len(self.light_map[y])):
                light_level = self.light_map[y][x]
                light_level-=1
                if light_level < 0:
                    light_level = 0
                pyxel.blt(scroll_x+ x*8,scroll_y + y*8,0, DARKNESS_SPRITES[int(light_level)][0],DARKNESS_SPRITES[int(light_level)][1],DARKNESS_SPRITES[int(light_level)][2],DARKNESS_SPRITES[int(light_level)][3], TRANSPARENT_COLOR)

class InventoryHandler:
    def __init__(self):
        self.ores = {}  # Dictionary to store mined ores and their count
        self.player_money = 0

    def collect_ore(self, ore_id):
        if ore_id != OreID.NONE:
            if ore_id in self.ores:
                self.ores[ore_id] += 1
            else:
                self.ores[ore_id] = 1  # First time collecting this ore

    def add_money(self, amount):
        self.player_money+=amount
    def clear(self):
        self.ores = {}
    def get_inventory(self):
        return self.ores  # Returns only mined ores
    
    def draw_ui(self):
        y_offset = 1
        x_offset = 30
        for ore, count in self.get_inventory().items():
            ore_name = ore.name.capitalize()
            ore_ui_sprite = Ores.get_ui_sprite(ore)
            pyxel.blt(scroll_x+ x_offset,scroll_y + y_offset,0, *ore_ui_sprite, TRANSPARENT_COLOR)
            pyxel.text(scroll_x+x_offset+9, scroll_y+y_offset, f"x{count}", 7)
            x_offset += 22  # Move down for next item
        pyxel.text(scroll_x+SCREEN_W-40, scroll_y+1, f"{self.player_money}$".rjust(10),7)

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

        self.mining_hits += 100

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

class Ores:
    TEXTURES = {
        OreID.NONE: (0, 0, 0, 0),
        OreID.GOLD: (32, 80, 8, 8),
        OreID.DIAMONDS: (32, 96, 8, 8),
        OreID.MITHRIL: (32, 96+16, 8, 8),
        OreID.ALIENIUM: (32, 96+32, 8, 8)
    }

    UI_SPRITES = {
        OreID.NONE: (0, 0, 0, 0),
        OreID.GOLD: (0, 80, 8, 8),
        OreID.DIAMONDS: (8, 80, 8, 8),
        OreID.MITHRIL: (16, 80, 8, 8),
        OreID.ALIENIUM: (24, 80, 8, 8)
    }

    BASE_VALUE = {
        OreID.NONE: 0,
        OreID.GOLD: 100,
        OreID.DIAMONDS: 1000,
        OreID.MITHRIL: 10000,
        OreID.ALIENIUM: 999999
    }

    @staticmethod
    def get_texture(ore_id):
        return Ores.TEXTURES.get(ore_id, (0, 0, 0, 0))
    
    @staticmethod
    def get_ui_sprite(ore_id):
        return Ores.UI_SPRITES.get(ore_id, (0, 0, 0, 0))
    
    @staticmethod
    def get_base_value(ore_id):
        return Ores.BASE_VALUE.get(ore_id, 0)

class OresHandler:
    def __init__(self):
        self.ores_map: dict[tuple[int, int], OreID] = {(x,y): OreID.NONE for x in range(MAP_SIZE_BLOCKS_X) for y in range(MAP_SIZE_BLOCKS_Y)}
        self.generate_ores()
    def generate_ores(self):
        for x in range(MAP_SIZE_BLOCKS_X):
            for y in range(MAP_SIZE_BLOCKS_Y):
                block = blocks_handler.get_block_id(x, y)
                
                if block not in {BlockID.STONE, BlockID.HARD_STONE, BlockID.MAGMA_ROCK, BlockID.DIRT}:
                    continue  

                depth_factor = y / MAP_SIZE_BLOCKS_Y

                if y >= 13 and block == BlockID.DIRT and random.random() < 0.05 + depth_factor * 0.1:
                    self.ores_map[(x, y)] = OreID.GOLD
                
                if y >= 20 and block in {BlockID.STONE, BlockID.HARD_STONE} and random.random() < 0.02 + depth_factor * 0.15:
                    self.ores_map[(x, y)] = OreID.DIAMONDS

                if y >= 40 and block in {BlockID.HARD_STONE, BlockID.MAGMA_ROCK} and random.random() < 0.01 + depth_factor * 0.1:
                    self.ores_map[(x, y)] = OreID.MITHRIL

                if y >= 60 and block == BlockID.MAGMA_ROCK and random.random() < 0.005 + depth_factor * 0.05:
                    self.ores_map[(x, y)] = OreID.ALIENIUM

    def get_ore_id(self, x, y):
        return self.ores_map.get((x, y), OreID.NONE)

    def destroy_ore(self, x, y):
        if not self.ores_map[(x,y)] == OreID.NONE:
            inventory_handler.collect_ore(self.ores_map[(x,y)])
        self.ores_map[(x,y)] = OreID.NONE

# === Static Block Data ===
class Blocks:
    # Block properties stored in a dictionary (no instance data)
    TEXTURES = {
        BlockID.AIR: (48, 112, 8, 8),
        BlockID.GRASS: (48, 96, 8, 8),
        BlockID.DIRT: (48, 80, 8, 8),
        BlockID.STONE: (48, 64, 8, 8),
        BlockID.HARD_STONE: (48, 128, 8, 8),
        BlockID.MAGMA_ROCK: (48, 144, 8, 8),
    }

    SOLIDITY = {
        BlockID.AIR: False,
        BlockID.GRASS: True,
        BlockID.DIRT: True,
        BlockID.STONE: True,
        BlockID.HARD_STONE: True,
        BlockID.MAGMA_ROCK: True,
    }

    MINING_HITS = {
        BlockID.AIR: 0,
        BlockID.GRASS: 5,
        BlockID.DIRT: 10,
        BlockID.STONE: 20,
        BlockID.HARD_STONE: 50,
        BlockID.MAGMA_ROCK: 200,
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
        self.variants_map: dict[tuple[int, int], int] = {}
        # Initialze variants:
        self.variants_map = {(x,y) : random.randint(0,3) for x in range(MAP_SIZE_BLOCKS_X) for y in range(MAP_SIZE_BLOCKS_Y)}
        self.generate_map()
        self.generate_caves()
        self.rocks_gradient_changer()

    def destroy_block(self, block_x, block_y):
        if not self.is_in_range(block_x, block_y):
            return
        self.blocks_map[(block_x, block_y)] = BlockID.AIR
        ore_handler.destroy_ore(block_x, block_y)

    def is_solid(self, block_x, block_y) -> bool:
        if not self.is_in_range(block_x, block_y):
            return False
        return Blocks.is_solid(self.get_block_id(block_x, block_y))

    def generate_map(self):
        for i in range(MAP_SIZE_BLOCKS_X):
            for j in range(MAP_SIZE_BLOCKS_Y):
                if j > 6:
                    self.blocks_map[(i, j)] = BlockID.AIR
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

        # Include block variant:
        variant_int = self.variants_map[(block_x,block_y)]
        variant_x, variant_y = variant_int%2, variant_int//2
        (img_u, img_v, img_w, img_h) = block_image
        variant_block_image = (img_u + variant_x*8, img_v + variant_y*8, img_w, img_h)
        pyxel.blt(screen_x, screen_y, 0, *variant_block_image, TRANSPARENT_COLOR)

        # Draw ore on block

        ore_id = ore_handler.get_ore_id(block_x, block_y)
        ore_image = Ores.get_texture(ore_id)
        pyxel.blt(screen_x, screen_y, 0, *ore_image, TRANSPARENT_COLOR)

    def generate_caves(self, fill_probability=72, iterations=5):
        for y in range(MAP_SIZE_BLOCKS_Y):
            for x in range(MAP_SIZE_BLOCKS_X):
                if random.randint(0, 100) < fill_probability:
                    self.set_block(x,y, BlockID.STONE)
                else:
                    self.set_block(x,y, BlockID.AIR)

        for _ in range(iterations):
            new_blocks_map : dict[tuple[int, int], BlockID] = {} 
            for y in range(1, MAP_SIZE_BLOCKS_Y-1):
                for x in range(1, MAP_SIZE_BLOCKS_X-1):
                    # Count walls around
                    walls = sum(1 for dy in range(-1, 2) for dx in range(-1, 2)
                                if self.get_block_id(x+dx,y+dy) == BlockID.STONE and (dx != 0 or dy != 0))
                    
                    if walls >= 5:
                        new_blocks_map[(x,y)] = BlockID.STONE
                    else:
                        new_blocks_map[(x,y)] = BlockID.AIR
            self.blocks_map = new_blocks_map
        # Fix missing borders
        for y in range(MAP_SIZE_BLOCKS_Y):
            self.set_block(0, y, BlockID.STONE)
            self.set_block(MAP_SIZE_BLOCKS_X-1, y, BlockID.STONE)

    def rocks_gradient_changer(self, layer_height=10, buffer=10):
        layers = [BlockID.DIRT, BlockID.STONE, BlockID.HARD_STONE, BlockID.MAGMA_ROCK]
        
        for y in range(MAP_SIZE_BLOCKS_Y):
            for x in range(MAP_SIZE_BLOCKS_X):
                if y < 10:
                    self.set_block(x, y, BlockID.AIR)
                elif y == 10:
                    self.set_block(x, y, BlockID.GRASS)
                elif y < 13:
                    self.set_block(x, y, BlockID.DIRT)
                else:
                    layer_index = (y - 13) // (layer_height + buffer)
                    layer_index = min(layer_index, len(layers) - 1)
                    
                    primary_block = layers[layer_index]
                    layer_start = 13 + layer_index * (layer_height + buffer)
                    layer_end = layer_start + layer_height
                    transition_top = layer_start - buffer
                    transition_bottom = layer_end

                    if transition_top <= y < layer_start and layer_index > 0:
                        above_block = layers[layer_index - 1]
                        mix_prob = (y - transition_top) / buffer
                        if self.get_block_id(x, y) == BlockID.STONE:
                            self.set_block(x, y, above_block if random.random() > mix_prob else primary_block)

                    elif transition_bottom <= y < transition_bottom + buffer and layer_index < len(layers) - 1:
                        below_block = layers[layer_index + 1]
                        mix_prob = (transition_bottom + buffer - y) / buffer
                        if self.get_block_id(x, y) == BlockID.STONE:
                            self.set_block(x, y, below_block if random.random() > mix_prob else primary_block)

                    else:
                        if self.get_block_id(x, y) == BlockID.STONE:
                            self.set_block(x, y, primary_block)


def area_to_xywh(area):
    (x1,y1,x2,y2) = area
    return (x1, y1, x2-x1, y2-y1)

class TriggerZone:
    def __init__(self, x1, y1, x2, y2, color=1, is_invisible=False):
        self.area = (x1, y1, x2, y2)
        self.color = color
        self.is_invisible = is_invisible


    def draw(self):
        if self.is_invisible:
            return
        xywh_area = area_to_xywh(self.area)
        pyxel.rect(*xywh_area, self.color)

    def is_in_area(self, object_coords):
        (o_x, o_y) = object_coords
        (x1, y1, x2, y2) = self.area
        return x1 <= o_x <= x2 and y1 <= o_y <= y2

    def trigger(self):
        logging.info(f"TriggerZone: {self} triggered!")

class ShopZone(TriggerZone):
    def __init__(self, x1, y1, x2, y2, color=1, is_invisible=False):
        super().__init__(x1, y1, x2, y2, color, is_invisible)

    def trigger(self):
        super().trigger()
        for ore, number in inventory_handler.get_inventory().items():
            # Sell each ore
            added_money = Ores.get_base_value(ore) * number
            inventory_handler.add_money(added_money)

        # Clear ores:
        inventory_handler.clear()

class TriggerZonesHandler:
    def __init__(self):
        self.trigger_zones : list[TriggerZone] = []
        shop_zone : TriggerZone = ShopZone(0,0,40,16,2)
        self.add_zone(shop_zone)
    
    def add_zone(self, zone : TriggerZone):
        self.trigger_zones.append(zone)

    def check_zones_player(self):
        for zone in self.trigger_zones:
            zone : TriggerZone = zone
            if zone.is_in_area((player.x,player.y)):
                zone.trigger()

    def draw_zones(self):
        for zone in self.trigger_zones:
            zone.draw()
            

class InputHandler:
    def __init__(self, double_click_time=10, hold_time=5):
        self.keys = {
            "left": [pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT],
            "right": [pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT],
            "down": [pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN],
            "jump": [
                pyxel.KEY_SPACE,
                pyxel.KEY_W,
                pyxel.GAMEPAD1_BUTTON_DPAD_UP,
                pyxel.GAMEPAD1_BUTTON_A,
            ],
        }
        self.states = {
            key: {
                "pressed": False,
                "long_pressed": False,
                "held": False,
                "double_click": False,
                "last_press_time": -double_click_time,
            }
            for key in self.keys
        }
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
                if (
                    pyxel.frame_count - self.states[action]["last_press_time"]
                    <= self.double_click_time
                ):
                    self.states[action]["double_click"] = True
                self.states[action]["last_press_time"] = pyxel.frame_count

            # Holding Detection
            if held_now:
                self.hold_counters[action] += 1
                self.states[action]["held"] = (
                    self.hold_counters[action] >= self.hold_time
                )
            else:
                self.hold_counters[action] = 0
                self.states[action]["held"] = False

            self.states[action]["pressed"] = pressed_now
            self.states[action]["long_pressed"] = held_now
        for key, state in self.states.items():
            if state["double_click"]:
                # print(key)
                pass

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

        self.x = clamp(self.x, 0, MAP_SIZE_BLOCKS_X * 8)
        self.y = clamp(self.y, 0, MAP_SIZE_BLOCKS_Y * 8)

        if self.x > scroll_x + SCROLL_BORDER_X:
            last_scroll_x = scroll_x
            scroll_x = min(self.x - SCROLL_BORDER_X, (MAP_SIZE_BLOCKS_X-8) * 8)
            # spawn_enemy(last_scroll_x + 128, scroll_x + 127)
        if self.x < scroll_x + (SCREEN_W - SCROLL_BORDER_X):
            last_scroll_x = scroll_x
            scroll_x = max(self.x - (SCREEN_W - SCROLL_BORDER_X), 0)
            # spawn_enemy(last_scroll_x + 128, scroll_x + 127)
        if self.y > scroll_y + SCROLL_BORDER_Y:
            last_scroll_y = scroll_y
            scroll_y = min(self.y - SCROLL_BORDER_Y, (MAP_SIZE_BLOCKS_Y-8) * 8)
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
        for key, state in input.states.items():
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

        # Check for zones triggers
        trigger_zones_handler.check_zones_player()

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
        if mining_helper.current_block and ((mining_helper.mining_hits) % 30 < 7):
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

        global player, input, mining_helper, blocks_handler, ore_handler, inventory_handler, trigger_zones_handler, darkness_system, danger_handler
        player = Player(0, 0)
        input = InputHandler()
        mining_helper = MiningHelper()
        blocks_handler = BlocksHandler()
        ore_handler = OresHandler()
        inventory_handler = InventoryHandler()
        trigger_zones_handler = TriggerZonesHandler()
        darkness_system = DarknessSystem()
        danger_handler = DangerHandler()
        pyxel.playm(0, loop=True)
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btn(pyxel.KEY_Q):
            pyxel.quit()

        input.update()
        player.update()
        danger_handler.update()

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

        # Trigger zones
        trigger_zones_handler.draw_zones()

        # Lightning
        darkness_system.update_lighting(player.x, player.y)
        darkness_system.render_darkness()


        # Draw nagerometer
        danger_handler.draw()

        # Draw gizmos
        mining_helper.draw()

        # UI
        inventory_handler.draw_ui()


def game_over():
    global scroll_x, scroll_y, enemies
    scroll_x = 0
    scroll_y = 0
    player.x = 0
    player.y = 0
    player.dx = 0
    player.dy = 0
    enemies = []
    pyxel.play(3, 9)


App()
