"""
PathForge -- Algorithm Visualization Studio (UI layer)

This file owns rendering and input only. All pathfinding and maze-
generation logic lives in pathforge_core/ and is independently unit-
tested (tests/) and benchmarked (pathforge_core/benchmark.py) without
importing pygame at all. That split is deliberate: the algorithms are
the part worth proving correct; the UI is a viewer on top of them.
"""

import random

import pygame as pg

from pathforge_core.algorithms import Algorithm, solve
from pathforge_core.grid import Grid
from pathforge_core.maze_generation import MazeAlgorithm, generate as generate_maze

pg.init()
pg.display.set_caption("PathForge -- Algorithm Visualization Studio")

# ----------------------------- Config ------------------------

SCREEN_W, SCREEN_H = 1440, 960
FPS = 60

SIDEBAR_W = 370
TOPBAR_H = 76
PADDING = 20

GRID_COLS = 34
GRID_ROWS = 25
CELL = 24

GRID_W = GRID_COLS * CELL
GRID_H = GRID_ROWS * CELL

BOARD_X = SIDEBAR_W + 28
BOARD_Y = TOPBAR_H + 20

FONT = "segoeui"
MONO = "consolas"

BG = (10, 13, 19)
SURFACE = (18, 23, 32)
SURFACE_2 = (23, 29, 40)
SURFACE_3 = (29, 36, 49)
TEXT = (235, 240, 248)
MUTED = (143, 154, 173)
GRID_COLOR = (34, 42, 55)
ACCENT = (91, 145, 255)
ACCENT_2 = (200, 130, 255)
GREEN = (61, 220, 145)
RED = (255, 94, 120)
YELLOW = (255, 196, 82)
TERRAIN_COLOR = (168, 111, 58)
WHITE = (255, 255, 255)

TERRAIN_COST = 4.0

FONT_SM = pg.font.SysFont(FONT, 13)
FONT_MD = pg.font.SysFont(FONT, 16)
FONT_LG = pg.font.SysFont(FONT, 20, bold=True)
FONT_XL = pg.font.SysFont(FONT, 28, bold=True)
MONO_SM = pg.font.SysFont(MONO, 12)
MONO_MD = pg.font.SysFont(MONO, 15, bold=True)

screen = pg.display.set_mode((SCREEN_W, SCREEN_H))
clock = pg.time.Clock()


# ============================================================
# UI Helpers
# ============================================================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def rounded_rect(surface, color, rect, radius=8, border=0, border_color=None):
    pg.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pg.draw.rect(surface, border_color, rect, width=border, border_radius=radius)


def text(surface, value, pos, font=FONT_MD, color=TEXT):
    surface.blit(font.render(str(value), True, color), pos)


def centered_text(surface, value, rect, font=FONT_MD, color=TEXT):
    img = font.render(str(value), True, color)
    surface.blit(img, img.get_rect(center=rect.center))


class Button:
    def __init__(self, rect, label, callback=None):
        self.rect = pg.Rect(rect)
        self.label = label
        self.callback = callback
        self.enabled = True

    def draw(self, surface, mouse_pos, active=False):
        hovered = self.rect.collidepoint(mouse_pos) and self.enabled
        fill = ACCENT if active else (SURFACE_3 if hovered else SURFACE_2)
        border = ACCENT if hovered or active else GRID_COLOR
        rounded_rect(surface, fill, self.rect, 8, 1, border)
        centered_text(surface, self.label, self.rect, FONT_SM, TEXT)

    def handle(self, event):
        if (event.type == pg.MOUSEBUTTONDOWN and event.button == 1
                and self.enabled and self.rect.collidepoint(event.pos)):
            if self.callback:
                self.callback()
            return True
        return False


class Toggle:
    def __init__(self, rect, label, value=False):
        self.rect = pg.Rect(rect)
        self.label = label
        self.value = value

    def draw(self, surface, mouse_pos):
        text(surface, self.label, (self.rect.x, self.rect.y + 3), FONT_SM, MUTED)
        track = pg.Rect(self.rect.right - 42, self.rect.y, 34, 18)
        rounded_rect(surface, ACCENT if self.value else SURFACE_3, track, 9)
        cx = track.right - 9 if self.value else track.x + 9
        pg.draw.circle(surface, WHITE, (cx, track.centery), 6)

    def handle(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.value = not self.value
            return True
        return False


# ============================================================
# Application
# ============================================================

class PathForgeApp:
    def __init__(self):
        self.start = (1, 1)
        self.goal = (GRID_COLS - 2, GRID_ROWS - 2)
        self.walls = set()
        self.terrain = {}

        self.algorithm = Algorithm.ASTAR
        self.algorithms = list(Algorithm)
        self.maze_algorithms = list(MazeAlgorithm)

        self.diagonal = False
        self.paint_mode = "wall"  # "wall" | "terrain"

        self.running = False
        self.paused = False
        self.show_frontier = True
        self.show_grid = True

        self.result = None
        self.event_index = 0
        self.visited = set()
        self.frontier = set()
        self.path_draw_index = 0

        self.status = "READY"
        self.message = "Design a map, choose an algorithm, then run."
        self.speed = 1.0
        self.dragging = False
        self.erase_mode = False
        self.undo_stack = []
        self.redo_stack = []

        self.create_ui()
        self.new_map("random")

    # ---------------- UI construction ----------------

    def create_ui(self):
        x = PADDING
        y = TOPBAR_H + 18
        half = (SIDEBAR_W - 44 - 8) // 2

        self.algo_buttons = []
        for i, algo in enumerate(self.algorithms):
            col = i % 2
            row = i // 2
            w = half if len(self.algorithms) > 4 else SIDEBAR_W - 44
            bx = x + col * (half + 8) if len(self.algorithms) > 4 else x
            by = y + row * 34
            self.algo_buttons.append(Button((bx, by, w, 30), algo.value, lambda a=algo: self.select_algorithm(a)))
        y += ((len(self.algorithms) + 1) // 2) * 34 + 10

        self.run_btn = Button((x, y, half, 40), "RUN", self.start_search)
        self.pause_btn = Button((x + half + 8, y, half, 40), "PAUSE", self.toggle_pause)
        y += 48
        self.step_btn = Button((x, y, SIDEBAR_W - 44, 30), "STEP", self.step_once)
        y += 38

        text_y_paint = y
        self.wall_mode_btn = Button((x, y, half, 30), "PAINT: WALL", lambda: self.set_paint_mode("wall"))
        self.terrain_mode_btn = Button((x + half + 8, y, half, 30), "PAINT: MUD", lambda: self.set_paint_mode("terrain"))
        y += 38
        self.start_mode_btn = Button((x, y, half, 30), "SET START", lambda: self.set_paint_mode("start"))
        self.goal_mode_btn = Button((x + half + 8, y, half, 30), "SET GOAL", lambda: self.set_paint_mode("goal"))
        y += 38

        self.random_btn = Button((x, y, half, 30), "RANDOM", lambda: self.new_map("random"))
        self.clear_btn = Button((x + half + 8, y, half, 30), "CLEAR", self.clear_map)
        y += 38

        self._maze_label_y = y
        y += 18
        self.maze_buttons = []
        maze_labels = {
            MazeAlgorithm.RECURSIVE_BACKTRACKER: "BACKTRACK",
            MazeAlgorithm.PRIMS: "PRIM'S",
            MazeAlgorithm.KRUSKAL: "KRUSKAL'S",
            MazeAlgorithm.RECURSIVE_DIVISION: "DIVISION",
        }
        for i, algo in enumerate(self.maze_algorithms):
            col = i % 2
            row = i // 2
            bx = x + col * (half + 8)
            by = y + row * 34
            self.maze_buttons.append(
                Button((bx, by, half, 30), maze_labels[algo], lambda a=algo: self.generate_maze(a))
            )
        y += 2 * 34 + 8

        self.reset_btn = Button((x, y, half, 30), "RESET", self.reset_run)
        self.undo_btn = Button((x + half + 8, y, half, 30), "UNDO", self.undo)
        y += 38
        self.redo_btn = Button((x, y, half, 30), "REDO", self.redo)
        y += 40

        self.diagonal_toggle = Toggle((x, y, SIDEBAR_W - 44, 22), "Diagonal movement (needed for JPS)", False)
        y += 30
        self.grid_toggle = Toggle((x, y, SIDEBAR_W - 44, 22), "Show grid", True)
        y += 28
        self.frontier_toggle = Toggle((x, y, SIDEBAR_W - 44, 22), "Show frontier", True)

        self._all_buttons = [
            *self.algo_buttons, self.run_btn, self.pause_btn, self.step_btn,
            self.wall_mode_btn, self.terrain_mode_btn, self.start_mode_btn, self.goal_mode_btn,
            self.random_btn, self.clear_btn,
            *self.maze_buttons,
            self.reset_btn, self.undo_btn, self.redo_btn,
        ]
        self._all_toggles = [self.diagonal_toggle, self.grid_toggle, self.frontier_toggle]

    def set_paint_mode(self, mode):
        self.paint_mode = mode
        labels = {
            "wall": "walls",
            "terrain": f"mud (cost {TERRAIN_COST:.0f}x)",
            "start": "start point -- click a cell to move it",
            "goal": "goal point -- click a cell to move it",
        }
        self.message = f"Paint mode: {labels[mode]}."

    # ---------------- Map management ----------------

    def snapshot(self):
        return set(self.walls), dict(self.terrain)

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        self.undo_stack = self.undo_stack[-30:]
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self.snapshot())
        self.walls, self.terrain = self.undo_stack.pop()
        self.reset_run()
        self.message = "Undo applied."

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self.snapshot())
        self.walls, self.terrain = self.redo_stack.pop()
        self.reset_run()
        self.message = "Redo applied."

    def clear_map(self):
        self.push_undo()
        self.walls.clear()
        self.terrain.clear()
        self.reset_run()
        self.message = "Canvas cleared."

    def new_map(self, mode="random"):
        self.push_undo()
        self.walls.clear()
        self.terrain.clear()
        if mode == "random":
            for y in range(GRID_ROWS):
                for x in range(GRID_COLS):
                    p = (x, y)
                    if p in (self.start, self.goal):
                        continue
                    if random.random() < 0.25:
                        self.walls.add(p)
        self.walls.discard(self.start)
        self.walls.discard(self.goal)
        self.reset_run()
        self.message = "Random map generated."

    def generate_maze(self, algo: MazeAlgorithm):
        if self.running:
            return
        self.push_undo()
        seed = random.randrange(1_000_000)
        self.walls = set(generate_maze(algo, GRID_COLS, GRID_ROWS, seed=seed))
        self.terrain.clear()
        self.walls.discard(self.start)
        self.walls.discard(self.goal)
        self.reset_run()
        self.message = f"{algo.value} maze generated (seed {seed})."

    def reset_run(self):
        self.running = False
        self.paused = False
        self.result = None
        self.event_index = 0
        self.visited.clear()
        self.frontier.clear()
        self.path_draw_index = 0
        self.status = "READY"

    # ---------------- Algorithm ----------------

    def select_algorithm(self, algo: Algorithm):
        if self.running:
            return
        self.algorithm = algo
        if algo == Algorithm.JPS and not self.diagonal:
            self.message = "JPS selected -- enable diagonal movement below to run it."
        else:
            self.message = f"{algo.value} selected."

    def start_search(self):
        if self.running:
            return

        self.diagonal = self.diagonal_toggle.value
        grid = Grid(GRID_COLS, GRID_ROWS, frozenset(self.walls), diagonal=self.diagonal, terrain=dict(self.terrain))

        if self.algorithm == Algorithm.JPS:
            if not self.diagonal:
                self.message = "JPS requires diagonal movement -- toggle it on first."
                return
            if self.terrain:
                self.message = "JPS requires uniform-cost terrain -- clear mud tiles first (or use A*)."
                return

        self.status = "SEARCHING"
        self.message = f"{self.algorithm.value} is exploring the graph..."
        self.running = True
        self.paused = False
        self.event_index = 0
        self.visited.clear()
        self.frontier.clear()
        self.path_draw_index = 0

        self.result = solve(self.algorithm, grid, self.start, self.goal)

    def toggle_pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        self.message = "Paused." if self.paused else "Resumed."

    def step_once(self):
        if not self.running:
            self.start_search()
        if self.running:
            self.process_events(1)

    def finish_search(self):
        self.running = False
        r = self.result
        self.status = "COMPLETE" if r.found else "NO PATH"
        if r.found:
            self.message = (f"{r.algorithm.value} finished -- "
                             f"{r.nodes_expanded:,} nodes expanded, "
                             f"cost {r.cost:.1f}, "
                             f"{r.elapsed_seconds * 1000:.2f} ms.")
        else:
            self.message = f"{r.algorithm.value} explored the reachable area -- no path exists."

    def process_events(self, amount):
        if not self.running or self.paused or self.result is None:
            return
        amount = max(1, int(amount))
        events = self.result.events
        for _ in range(amount):
            if self.event_index >= len(events):
                self.finish_search()
                return
            typ, node = events[self.event_index]
            self.event_index += 1
            if typ == "visit":
                self.visited.add(node)
                self.frontier.discard(node)
            else:
                self.frontier.add(node)
        if self.event_index >= len(events):
            self.finish_search()

    # ---------------- Board interaction ----------------

    def cell_from_mouse(self, pos):
        mx, my = pos
        gx = (mx - BOARD_X) // CELL
        gy = (my - BOARD_Y) // CELL
        if 0 <= gx < GRID_COLS and 0 <= gy < GRID_ROWS:
            return gx, gy
        return None

    def paint_cell(self, pos, erase=False):
        if self.running:
            return
        cell = self.cell_from_mouse(pos)
        if not cell:
            return

        if self.paint_mode in ("start", "goal"):
            other = self.goal if self.paint_mode == "start" else self.start
            if cell == other:
                return
            if not self.dragging:
                self.push_undo()
                self.dragging = True
            self.walls.discard(cell)
            self.terrain.pop(cell, None)
            if self.paint_mode == "start":
                self.start = cell
            else:
                self.goal = cell
            self.reset_run()
            return

        if cell in (self.start, self.goal):
            return
        if not self.dragging:
            self.push_undo()
            self.dragging = True

        if self.paint_mode == "wall":
            if erase:
                self.walls.discard(cell)
            else:
                self.terrain.pop(cell, None)
                self.walls.add(cell)
        else:  # terrain
            if erase:
                self.terrain.pop(cell, None)
            elif cell not in self.walls:
                self.terrain[cell] = TERRAIN_COST

        self.reset_run()

    # ---------------- Rendering ----------------

    def draw_background(self):
        screen.fill(BG)
        for x in range(0, SCREEN_W, 35):
            pg.draw.line(screen, (18, 22, 30), (x, 0), (x, SCREEN_H))
        for y in range(0, SCREEN_H, 35):
            pg.draw.line(screen, (18, 22, 30), (0, y), (SCREEN_W, y))

    def draw_topbar(self):
        rounded_rect(screen, SURFACE, (0, 0, SCREEN_W, TOPBAR_H), 0)
        text(screen, "PATHFORGE", (22, 14), FONT_XL)
        text(screen, "Algorithm Visualization Studio", (24, 47), FONT_SM, MUTED)

        status_colors = {"READY": MUTED, "SEARCHING": ACCENT, "COMPLETE": GREEN, "NO PATH": RED}
        s_color = status_colors.get(self.status, MUTED)
        chip = pg.Rect(SCREEN_W - 350, 20, 130, 34)
        rounded_rect(screen, SURFACE_2, chip, 17)
        pg.draw.circle(screen, s_color, (chip.x + 16, chip.centery), 5)
        text(screen, self.status, (chip.x + 28, chip.y + 8), FONT_SM, TEXT)

        algo_chip = pg.Rect(SCREEN_W - 205, 20, 185, 34)
        rounded_rect(screen, ACCENT, algo_chip, 17)
        centered_text(screen, self.algorithm.value, algo_chip, FONT_SM)

    def draw_sidebar(self):
        rounded_rect(screen, SURFACE, (0, TOPBAR_H, SIDEBAR_W, SCREEN_H - TOPBAR_H), 0)
        x = PADDING
        text(screen, "ALGORITHM", (x, TOPBAR_H + 4), FONT_SM, MUTED)
        mouse = pg.mouse.get_pos()
        for btn in self.algo_buttons:
            btn.draw(screen, mouse, active=(btn.label == self.algorithm.value))
        self.run_btn.draw(screen, mouse)
        self.pause_btn.draw(screen, mouse)
        self.step_btn.draw(screen, mouse)

        self.wall_mode_btn.draw(screen, mouse, active=(self.paint_mode == "wall"))
        self.terrain_mode_btn.draw(screen, mouse, active=(self.paint_mode == "terrain"))
        self.start_mode_btn.draw(screen, mouse, active=(self.paint_mode == "start"))
        self.goal_mode_btn.draw(screen, mouse, active=(self.paint_mode == "goal"))
        self.random_btn.draw(screen, mouse)
        self.clear_btn.draw(screen, mouse)

        text(screen, "MAZE GENERATOR", (x, self._maze_label_y), FONT_SM, MUTED)
        for btn in self.maze_buttons:
            btn.draw(screen, mouse)

        self.reset_btn.draw(screen, mouse)
        self.undo_btn.draw(screen, mouse)
        self.redo_btn.draw(screen, mouse)

        for t in self._all_toggles:
            t.draw(screen, mouse)

        controls_y = SCREEN_H - 110
        text(screen, "CONTROLS", (x, controls_y - 20), FONT_SM, MUTED)
        for line in ["LMB paint · RMB erase", "SPACE run/pause · R reset", "Mouse wheel: playback speed"]:
            text(screen, line, (x, controls_y), MONO_SM, MUTED)
            controls_y += 17

    def draw_stats_card(self, rect):
        rounded_rect(screen, SURFACE, rect, 14, 1, GRID_COLOR)
        text(screen, "LIVE TELEMETRY", (rect.x + 18, rect.y + 12), FONT_SM, MUTED)
        r = self.result
        rows = [
            ("Nodes expanded", f"{r.nodes_expanded:,}" if r else "\u2014"),
            ("Path cost", f"{r.cost:.1f}" if r and r.found else "\u2014"),
            ("Search time", f"{r.elapsed_seconds * 1000:.2f} ms" if r else "\u2014"),
            ("Mud tiles", f"{len(self.terrain):,}"),
        ]
        y = rect.y + 42
        for label, value in rows:
            text(screen, label, (rect.x + 18, y), FONT_SM, MUTED)
            v = MONO_MD.render(value, True, TEXT)
            screen.blit(v, (rect.right - 18 - v.get_width(), y))
            y += 24

    def draw_board(self):
        board = pg.Rect(BOARD_X - 10, BOARD_Y - 10, GRID_W + 20, GRID_H + 20)
        rounded_rect(screen, SURFACE, board, 16, 1, GRID_COLOR)
        path = self.result.path if self.result else []

        for y in range(GRID_ROWS):
            for x in range(GRID_COLS):
                r = pg.Rect(BOARD_X + x * CELL + 1, BOARD_Y + y * CELL + 1, CELL - 2, CELL - 2)
                p = (x, y)
                color = SURFACE_2
                if p in self.terrain:
                    color = TERRAIN_COLOR
                if self.show_frontier and p in self.frontier:
                    color = (42, 77, 112)
                if p in self.visited:
                    color = (35, 62, 91)
                if p in self.walls:
                    color = (54, 62, 78)
                if self.path_draw_index and p in path[:self.path_draw_index]:
                    color = (90, 72, 28)
                if p == self.start:
                    color = GREEN
                if p == self.goal:
                    color = RED
                rounded_rect(screen, color, r, 4)
                if self.show_grid:
                    pg.draw.rect(screen, GRID_COLOR, r, width=1, border_radius=4)

        sx, sy = BOARD_X + self.start[0] * CELL + CELL // 2, BOARD_Y + self.start[1] * CELL + CELL // 2
        gx, gy = BOARD_X + self.goal[0] * CELL + CELL // 2, BOARD_Y + self.goal[1] * CELL + CELL // 2
        pg.draw.circle(screen, WHITE, (sx, sy), 5)
        pg.draw.circle(screen, WHITE, (gx, gy), 5)

        if self.path_draw_index >= 2:
            pts = [(BOARD_X + x * CELL + CELL // 2, BOARD_Y + y * CELL + CELL // 2)
                   for x, y in path[:self.path_draw_index]]
            if len(pts) >= 2:
                pg.draw.lines(screen, YELLOW, False, pts, 4)

    def draw_right_info(self):
        x = BOARD_X
        y = BOARD_Y + GRID_H + 24
        left = pg.Rect(x, y, 520, 78)
        self.draw_stats_card(left)
        right = pg.Rect(x + 538, y, 420, 78)
        rounded_rect(screen, SURFACE, right, 14, 1, GRID_COLOR)
        text(screen, "ACTIVITY", (right.x + 18, right.y + 12), FONT_SM, MUTED)
        msg = self.message if len(self.message) <= 58 else self.message[:55] + "..."
        text(screen, msg, (right.x + 18, right.y + 38), FONT_MD, TEXT)

    def draw_legend(self):
        x, y = BOARD_X, BOARD_Y - 30
        entries = [("Start", GREEN), ("Goal", RED), ("Visited", (35, 62, 91)),
                   ("Frontier", (42, 77, 112)), ("Path", YELLOW), ("Wall", (54, 62, 78)),
                   ("Mud", TERRAIN_COLOR)]
        xx = x
        for label, color in entries:
            pg.draw.circle(screen, color, (xx, y + 7), 5)
            text(screen, label, (xx + 10, y), FONT_SM, MUTED)
            xx += 68

    def draw(self):
        self.draw_background()
        self.draw_topbar()
        self.draw_sidebar()
        self.draw_board()
        self.draw_legend()
        self.draw_right_info()
        small = f"{len(self.walls):,} walls  \u2022  {len(self.visited):,} visited"
        img = FONT_SM.render(small, True, MUTED)
        screen.blit(img, (SCREEN_W - img.get_width() - 24, SCREEN_H - 24))

    # ---------------- Input ----------------

    def handle_event(self, event):
        if event.type == pg.QUIT:
            return False
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                return False
            if event.key == pg.K_SPACE:
                self.toggle_pause() if self.running else self.start_search()
            elif event.key == pg.K_r:
                self.reset_run()

        if event.type == pg.MOUSEWHEEL:
            self.speed = clamp(self.speed + event.y * 0.25, 0.25, 4.0)

        if event.type == pg.MOUSEBUTTONDOWN:
            if event.button == 1:
                clicked = any(btn.handle(event) for btn in self._all_buttons)
                if not clicked:
                    for t in self._all_toggles:
                        if t.handle(event):
                            clicked = True
                            if t is self.diagonal_toggle:
                                self.diagonal = t.value
                            break
                if not clicked:
                    cell = self.cell_from_mouse(event.pos)
                    if cell:
                        already = cell in self.walls if self.paint_mode == "wall" else cell in self.terrain
                        self.paint_cell(event.pos, erase=already)
                        self.erase_mode = already
            elif event.button == 3 and self.cell_from_mouse(event.pos):
                self.paint_cell(event.pos, erase=True)
                self.erase_mode = True
        elif event.type == pg.MOUSEBUTTONUP and event.button in (1, 3):
            self.dragging = False
        elif event.type == pg.MOUSEMOTION and self.dragging:
            buttons = pg.mouse.get_pressed()
            if buttons[0] or buttons[2]:
                self.paint_cell(event.pos, erase=self.erase_mode)

        return True

    def update(self, dt):
        if self.running and not self.paused:
            rate = max(1, int(35 * self.speed * dt))
            self.process_events(rate)
        if not self.running and self.result and self.result.found:
            target = len(self.result.path)
            self.path_draw_index = min(target, self.path_draw_index + max(1, int(18 * self.speed * dt)))

    def run(self):
        running = True
        while running:
            dt = clock.tick(FPS) / 1000.0
            for event in pg.event.get():
                running = self.handle_event(event)
                if not running:
                    break
            if not running:
                break
            self.update(dt)
            self.draw()
            pg.display.flip()
        pg.quit()


if __name__ == "__main__":
    PathForgeApp().run()
