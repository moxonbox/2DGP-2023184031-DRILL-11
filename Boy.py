from pathlib import Path
from math import isclose, pi, sqrt

from pico2d import (
    load_image, get_canvas_width, SDL_KEYDOWN, SDL_KEYUP,
    SDLK_s, SDLK_d, SDLK_LSHIFT, SDLK_RSHIFT, SDLK_LCTRL, SDLK_RCTRL,
    SDLK_SPACE, SDLK_a,
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
        active_dt = min(dt, max(0.0, 5.0 - boy.idle_elapsed))
        boy.animate_and_move(active_dt)
        boy.idle_elapsed += active_dt
        if isclose(boy.idle_elapsed, 5.0, rel_tol=0, abs_tol=1e-9):
            boy.sleep()
            if dt > active_dt:
                boy.update(dt - active_dt)


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
        boy.update_jump(dt)


class AutoRun(BoyState):
    def __init__(self):
        super().__init__('autorun')

    def update(self, boy, dt):
        remaining = max(0.0, 5.0 - boy.auto_elapsed)
        active_dt = min(dt, remaining)
        boy.animate_and_move(active_dt, bounce=True)
        boy.auto_elapsed += active_dt
        if isclose(boy.auto_elapsed, 5.0, rel_tol=0, abs_tol=1e-9):
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
    JUMP_SPEED = 420
    GRAVITY = 980
    AUTO_MULTIPLIER = 1.5
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
        self.vertical_speed = 0
        self.air_state = 'idle'
        self.auto_state = 'idle'
        self.auto_elapsed = 0
        self.auto_key_down = False
        self.machine = Machine(
            model=self,
            states=[Idle(), Sleep(), SlowWalk(), Walk(), Run(), Jump(), AutoRun()],
            initial='idle',
            auto_transitions=False, after_state_change='reset_animation',
            transitions=[
                ['stop', ['slow_walk', 'walk', 'run', 'jump', 'autorun'], 'idle'],
                ['slow_walk', ['idle', 'walk', 'run', 'Sleep', 'jump', 'autorun'], 'slow_walk'],
                ['walk', ['idle', 'slow_walk', 'run', 'Sleep', 'jump', 'autorun'], 'walk'],
                ['run', ['idle', 'slow_walk', 'walk', 'Sleep', 'jump', 'autorun'], 'run'],
                ['sleep', 'idle', 'Sleep'],
                ['wake', 'Sleep', 'idle'],
                ['jump', ['idle', 'slow_walk', 'walk', 'run'], 'jump'],
                ['autorun', ['idle', 'slow_walk', 'walk', 'run', 'Sleep'], 'autorun'],
            ],
        )

    def reset_animation(self):
        self.frame = 0
        self.idle_elapsed = 0

    def handle_event(self, event):
        if event.type not in (SDL_KEYDOWN, SDL_KEYUP):
            return
        if event.key == SDLK_a:
            if event.type == SDL_KEYUP:
                self.auto_key_down = False
            elif not self.auto_key_down:
                self.auto_key_down = True
                if self.state == 'autorun':
                    self.stop()
                    self.apply_movement()
                elif self.state != 'jump':
                    self.auto_state = self.state
                    self.auto_elapsed = 0
                    self.autorun()
            return
        if self.state == 'Sleep' and event.type == SDL_KEYDOWN and event.key == SDLK_SPACE:
            self.keys.add(SDLK_SPACE)
            self.wake()
            return
        if event.key not in (
            SDLK_s, SDLK_d, SDLK_LSHIFT, SDLK_RSHIFT, SDLK_LCTRL, SDLK_RCTRL,
            SDLK_SPACE,
        ):
            return
        if event.type == SDL_KEYDOWN:
            if event.key in self.keys:
                return
            self.keys.add(event.key)
        else:
            self.keys.discard(event.key)
        if self.state == 'autorun':
            if event.type == SDL_KEYUP:
                return
            self.stop()
        if event.key == SDLK_SPACE:
            if event.type == SDL_KEYDOWN and self.state != 'jump':
                self.apply_movement()
                self.air_state = self.state
                self.jump()
            return
        self.apply_movement()

    def apply_movement(self):
        movement_state = self.air_state if self.state == 'jump' else self.state
        self.direction = int(SDLK_d in self.keys) - int(SDLK_s in self.keys)
        if self.state == 'Sleep' and not self.direction:
            return
        if self.direction:
            self.face_dir = self.direction
            if self.keys & {SDLK_LSHIFT, SDLK_RSHIFT}:
                if movement_state != 'run':
                    self.run_previous_state = (
                        movement_state if movement_state in ('walk', 'slow_walk') else
                        'slow_walk' if self.keys & {SDLK_LCTRL, SDLK_RCTRL} else 'walk'
                    )
                target = 'run'
            elif movement_state == 'run':
                target = self.run_previous_state
            elif self.keys & {SDLK_LCTRL, SDLK_RCTRL}:
                target = 'slow_walk'
            else:
                target = 'walk'
        else:
            target = 'idle'
        if self.state == 'jump':
            self.air_state = target
            return
        if target != self.state:
            getattr(self, 'stop' if target == 'idle' else target)()

    def update(self, dt):
        self.machine.get_state(self.state).update(self, dt)

    def update_jump(self, dt):
        ground_y = self.GROUND_Y + 36
        height = max(0.0, self.y - ground_y)
        landing_time = (self.vertical_speed + sqrt(
            self.vertical_speed ** 2 + 2 * self.GRAVITY * height
        )) / self.GRAVITY
        active_dt = min(dt, landing_time)
        self.animate_and_move(active_dt)
        self.y += self.vertical_speed * active_dt - 0.5 * self.GRAVITY * active_dt ** 2
        self.vertical_speed -= self.GRAVITY * active_dt
        if dt >= landing_time:
            self.y = ground_y
            self.vertical_speed = 0
            target = self.air_state
            getattr(self, 'stop' if target == 'idle' else target)()
            if dt > active_dt:
                self.update(dt - active_dt)

    def animation_state(self):
        if self.state == 'jump':
            return self.air_state
        if self.state == 'autorun':
            return self.auto_state
        return self.state

    def animate_and_move(self, dt, bounce=False):
        frames, fps, speed, _, _ = self.ANIMATIONS[self.animation_state()]
        self.frame = (self.frame + fps * dt) % len(frames)
        half_width = 50 * self.sprite_scale()
        left, right = half_width, get_canvas_width() - half_width
        if right <= left:
            self.x = get_canvas_width() / 2
            return
        self.x = max(left, min(right, self.x))
        if bounce:
            speed *= self.AUTO_MULTIPLIER
        position = self.x + self.direction * speed * dt
        if bounce and speed and self.direction:
            # Fold the travelled distance into the viewport, including multiple bounces.
            span = right - left
            phase = (position - left) % (2 * span)
            self.x = left + (phase if phase <= span else 2 * span - phase)
            if phase == 0:
                self.direction = 1
            elif phase == span:
                self.direction = -1
            elif phase > span:
                self.direction *= -1
            self.face_dir = self.direction
        else:
            self.x = max(left, min(right, position))

    def sprite_scale(self):
        if self.state == 'autorun' and self.ANIMATIONS[self.auto_state][2]:
            return self.AUTO_MULTIPLIER
        return 1

    def draw(self):
        self.machine.get_state(self.state).draw(self)

    def draw_sleep(self):
        # Crop padding so the rotated body rests at y=40.
        left, bottom = (31, 314) if self.face_dir == 1 else (36, 214)
        self.image.clip_composite_draw(
            left, bottom, 35, 78, self.face_dir * pi / 2, '',
            self.x, self.SLEEP_GROUND_Y + 35 / 2, 35, 78,
        )

    def draw_sprite(self):
        frames, _, _, right_row, left_row = self.ANIMATIONS[self.animation_state()]
        row = right_row if self.face_dir == 1 else left_row
        frame = frames[int(self.frame)]
        # Keep feet on the surface even when the source frame's padding changes.
        scale = self.sprite_scale()
        feet_y = self.y - 36
        draw_y = feet_y + (50 - self.FOOT_PADDING[row][frame]) * scale
        size = () if scale == 1 else (100 * scale, 100 * scale)
        self.image.clip_draw(
            frame * 100, row * 100, 100, 100,
            self.x, draw_y, *size,
        )
