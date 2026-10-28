from pathlib import Path
from math import pi

from pico2d import (
    load_image, get_canvas_width, SDL_KEYDOWN, SDL_KEYUP,
    SDLK_a, SDLK_d, SDLK_LSHIFT, SDLK_RSHIFT, SDLK_LCTRL, SDLK_RCTRL,
    SDLK_SPACE,
)
from transitions import Machine, State


class BoyState(State):
    def update(self, boy, dt):
        boy.animate_and_move(dt)

    def draw(self, boy):
        boy.draw_sprite()


class Idle(BoyState):
    def __init__(self):
        super().__init__('idle')

    def update(self, boy, dt):
        boy.idle_elapsed += dt
        if boy.idle_elapsed >= 5.0:
            boy.sleep()
        boy.animate_and_move(dt)


class Sleep(BoyState):
    def __init__(self):
        super().__init__('Sleep')

    def enter(self, event_data):
        super().enter(event_data)
        event_data.model.keys.clear()
        event_data.model.direction = 0

    def draw(self, boy):
        boy.draw_sleep()


class SlowWalk(BoyState):
    def __init__(self):
        super().__init__('slow_walk')


class Walk(BoyState):
    def __init__(self):
        super().__init__('walk')


class Run(BoyState):
    def __init__(self):
        super().__init__('run')


class Jump(BoyState):
    def __init__(self):
        super().__init__('jump')

    def enter(self, event_data):
        super().enter(event_data)
        event_data.model.vertical_speed = event_data.model.JUMP_SPEED

    def update(self, boy, dt):
        boy.animate_and_move(dt)
        boy.update_jump(dt)


class AutoRun(BoyState):
    def __init__(self):
        super().__init__('autorun')

    def update(self, boy, dt):
        remaining = max(0.0, 5.0 - boy.auto_elapsed)
        active_dt = min(dt, remaining)
        boy.animate_and_move(active_dt, bounce=True)
        boy.auto_elapsed += active_dt
        if boy.auto_elapsed >= 5.0:
            boy.keys.clear()
            boy.direction = 0
            boy.stop()
            if dt > active_dt:
                boy.update(dt - active_dt)

    def draw(self, boy):
        if boy.auto_state == 'Sleep':
            boy.draw_sleep()
        else:
            boy.draw_sprite()


class Boy:
    # Grass is centered at y=30; its visible surface near the boy is y=55.
    GROUND_Y = 55
    SLEEP_GROUND_Y = 40
    # Transparent pixels below each frame's lowest visible pixel, by sheet row.
    FOOT_PADDING = (
        (16, 20, 14, 14, 13, 19, 14, 13),
        (16, 20, 14, 14, 13, 19, 14, 13),
        (14,) * 8,
        (14,) * 8,
    )
    # Frames, FPS, pixels/second, right-facing row, left-facing row (from bottom).
    ANIMATIONS = {
        'idle': (tuple(range(8)), 4, 0, 3, 2),
        # The sheet has no separate slow-walk strip; reuse its small upright steps.
        'slow_walk': (tuple(range(8)), 8, 60, 3, 2),
        'walk': (tuple(range(8)), 8, 160, 1, 0),
        'run': (tuple(range(8)), 16, 320, 1, 0),
        'Sleep': ((0,), 0, 0, 3, 2),
    }

    def __init__(self):
        self.x, self.y = 400, self.GROUND_Y + 50 - 14
        self.frame = 0
        self.face_dir = 1
        self.image = load_image(str(Path(__file__).with_name('animation_sheet.png')))
        self.keys = set()
        self.direction = 0
        self.idle_elapsed = 0
        self.run_previous_state = 'walk'
        self.machine = Machine(
            model=self, states=list(self.ANIMATIONS), initial='idle',
            auto_transitions=False, after_state_change='reset_animation',
            transitions=[
                ['stop', ['slow_walk', 'walk', 'run'], 'idle'],
                ['slow_walk', ['idle', 'walk', 'run', 'Sleep'], 'slow_walk'],
                ['walk', ['idle', 'slow_walk', 'run', 'Sleep'], 'walk'],
                ['run', ['idle', 'slow_walk', 'walk', 'Sleep'], 'run'],
                ['sleep', 'idle', 'Sleep'],
                ['wake', 'Sleep', 'idle'],
            ],
        )

    def reset_animation(self):
        self.frame = 0
        self.idle_elapsed = 0
        if self.state == 'Sleep':
            self.keys.clear()
            self.direction = 0

    def handle_event(self, event):
        if event.type not in (SDL_KEYDOWN, SDL_KEYUP):
            return
        if self.state == 'Sleep' and event.type == SDL_KEYDOWN and event.key == SDLK_SPACE:
            self.wake()
            return
        if event.key not in (
            SDLK_a, SDLK_d, SDLK_LSHIFT, SDLK_RSHIFT, SDLK_LCTRL, SDLK_RCTRL,
        ):
            return
        if event.type == SDL_KEYDOWN:
            self.keys.add(event.key)
        else:
            self.keys.discard(event.key)

        self.direction = int(SDLK_d in self.keys) - int(SDLK_a in self.keys)
        if self.state == 'Sleep' and not self.direction:
            return
        if self.direction:
            self.face_dir = self.direction
            if self.keys & {SDLK_LSHIFT, SDLK_RSHIFT}:
                if self.state != 'run':
                    self.run_previous_state = (
                        self.state if self.state in ('walk', 'slow_walk') else
                        'slow_walk' if self.keys & {SDLK_LCTRL, SDLK_RCTRL} else 'walk'
                    )
                target = 'run'
            elif self.state == 'run':
                target = self.run_previous_state
            elif self.keys & {SDLK_LCTRL, SDLK_RCTRL}:
                target = 'slow_walk'
            else:
                target = 'walk'
        else:
            target = 'idle'
        if target != self.state:
            getattr(self, 'stop' if target == 'idle' else target)()

    def update(self, dt):
        if self.state == 'idle':
            self.idle_elapsed += dt
            if self.idle_elapsed >= 5.0:
                self.sleep()
        frames, fps, speed, _, _ = self.ANIMATIONS[self.state]
        self.frame = (self.frame + fps * dt) % len(frames)
        self.x = max(50, min(get_canvas_width() - 50,
                             self.x + self.direction * speed * dt))

    def draw(self):
        if self.state == 'Sleep':
            # Crop the visible upright pose so rotated padding cannot float above grass.
            left, bottom = (31, 314) if self.face_dir == 1 else (36, 214)
            self.image.clip_composite_draw(
                left, bottom, 35, 78, self.face_dir * pi / 2, '',
                self.x, self.SLEEP_GROUND_Y + 35 / 2, 35, 78,
            )
            return
        frames, _, _, right_row, left_row = self.ANIMATIONS[self.state]
        row = right_row if self.face_dir == 1 else left_row
        frame = frames[int(self.frame)]
        # Keep feet on the surface even when the source frame's padding changes.
        draw_y = self.y + 14 - self.FOOT_PADDING[row][frame]
        self.image.clip_draw(
            frame * 100, row * 100, 100, 100,
            self.x, draw_y,
        )
