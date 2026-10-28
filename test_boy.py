"""Headless controller checks using the real transitions state machine."""

import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


pico = ModuleType('pico2d')
for value, name in enumerate((
    'SDL_KEYDOWN', 'SDL_KEYUP', 'SDLK_a', 'SDLK_d',
    'SDLK_LSHIFT', 'SDLK_RSHIFT', 'SDLK_LCTRL', 'SDLK_RCTRL', 'SDLK_SPACE',
)):
    setattr(pico, name, value)
pico.load_image = Mock()
pico.get_canvas_width = lambda: 800
with patch.dict(sys.modules, pico2d=pico):
    from Boy import Boy


class BoyTests(unittest.TestCase):
    def setUp(self):
        self.boy = Boy()

    def key(self, key, down=True):
        self.boy.handle_event(SimpleNamespace(
            type=pico.SDL_KEYDOWN if down else pico.SDL_KEYUP, key=key,
        ))

    def test_idle_loops_without_moving(self):
        self.assertEqual(self.boy.state, 'idle')
        self.boy.update(0.25)
        self.assertEqual(self.boy.frame, 1)
        self.boy.draw()
        self.assertEqual(self.boy.image.clip_draw.call_args.args[:4], (100, 300, 100, 100))
        self.boy.update(1.75)
        self.assertEqual(self.boy.frame, 0)
        self.assertEqual(self.boy.x, 400)

    def test_walk_run_walk_idle(self):
        self.key(pico.SDLK_d)
        self.assertEqual(self.boy.state, 'walk')
        self.boy.update(0.25)
        self.assertEqual(self.boy.x, 440)
        self.key(pico.SDLK_LSHIFT)
        self.assertEqual((self.boy.state, self.boy.frame), ('run', 0))
        self.boy.update(0.25)
        self.assertEqual(self.boy.x, 520)
        self.key(pico.SDLK_LSHIFT, False)
        self.assertEqual(self.boy.state, 'walk')
        self.key(pico.SDLK_d, False)
        self.assertEqual(self.boy.state, 'idle')

    def test_sleep_after_five_seconds_and_space_wakes(self):
        self.boy.update(4.5)
        self.key(pico.SDLK_LSHIFT)
        self.boy.update(0.5)
        self.assertEqual(self.boy.state, 'Sleep')
        self.assertEqual(self.boy.keys, set())
        self.key(pico.SDLK_d, False)
        self.key(pico.SDLK_SPACE, False)
        self.boy.update(1)
        self.assertEqual((self.boy.state, self.boy.x), ('Sleep', 400))
        self.key(pico.SDLK_SPACE)
        self.assertEqual((self.boy.state, self.boy.idle_elapsed), ('idle', 0))
        self.boy.update(4.5)
        self.assertEqual(self.boy.state, 'idle')
        self.boy.update(0.5)
        self.assertEqual(self.boy.state, 'Sleep')

    def test_idle_timer_restarts_after_movement(self):
        self.boy.update(4)
        self.key(pico.SDLK_d)
        self.boy.update(1)
        self.key(pico.SDLK_d, False)
        self.boy.update(4)
        self.assertEqual(self.boy.state, 'idle')
        self.boy.update(1)
        self.assertEqual(self.boy.state, 'Sleep')

    def test_sleep_rotated_sprite_uses_lower_placement(self):
        self.boy.update(5)
        for direction, crop in ((1, (31, 314)), (-1, (36, 214))):
            self.boy.face_dir = direction
            self.boy.draw()
            args = self.boy.image.clip_composite_draw.call_args.args
            self.assertEqual(args[:4], (*crop, 35, 78))
            self.assertAlmostEqual(abs(args[4]), 1.5707963267948966)
            self.assertEqual(args[7] - args[8] / 2, 40)
        self.key(pico.SDLK_SPACE)
        self.assertEqual(self.boy.y, self.boy.GROUND_Y + 36)

    def test_sleep_enters_requested_movement_state(self):
        for direction_key, direction in ((pico.SDLK_a, -1), (pico.SDLK_d, 1)):
            for modifier, state, speed in (
                (None, 'walk', 160),
                (pico.SDLK_LCTRL, 'slow_walk', 60),
                (pico.SDLK_RCTRL, 'slow_walk', 60),
                (pico.SDLK_LSHIFT, 'run', 320),
                (pico.SDLK_RSHIFT, 'run', 320),
            ):
                with self.subTest(direction=direction, state=state, modifier=modifier):
                    self.boy = Boy()
                    self.boy.update(5)
                    if modifier is not None:
                        self.key(modifier)
                        self.assertEqual(self.boy.state, 'Sleep')
                    self.key(direction_key)
                    self.assertEqual((self.boy.state, self.boy.direction), (state, direction))
                    self.boy.update(0.25)
                    self.assertEqual(self.boy.x, 400 + direction * speed * 0.25)
                    if state == 'run':
                        self.key(modifier, False)
                        self.assertEqual(self.boy.state, 'walk')

    def test_modifier_release_and_unrelated_key_keep_sleep(self):
        self.boy.update(5)
        self.key(pico.SDLK_LSHIFT)
        self.key(pico.SDLK_LSHIFT, False)
        self.key('unrelated')
        self.assertEqual(self.boy.state, 'Sleep')
        self.key(pico.SDLK_d)
        self.assertEqual(self.boy.state, 'walk')

    def test_every_frame_places_feet_on_grass(self):
        for state in ('idle', 'slow_walk', 'walk', 'run'):
            self.boy.machine.set_state(state)
            for direction in (1, -1):
                self.boy.face_dir = direction
                for frame in range(8):
                    with self.subTest(state=state, direction=direction, frame=frame):
                        self.boy.frame = frame
                        self.boy.draw()
                        _, bottom, _, _, _, center_y = self.boy.image.clip_draw.call_args.args
                        padding = self.boy.FOOT_PADDING[bottom // 100][frame]
                        self.assertEqual(center_y - 50 + padding, self.boy.GROUND_Y)

    def test_key_repeat_preserves_animation(self):
        self.key(pico.SDLK_a)
        self.boy.update(0.125)
        self.key(pico.SDLK_a)
        self.assertEqual(self.boy.frame, 1)
        self.boy.draw()
        self.assertEqual(self.boy.image.clip_draw.call_args.args[1], 0)

    def test_sheet_rows_for_every_state_and_direction(self):
        for state, right_row, left_row in (
            ('idle', 3, 2), ('slow_walk', 3, 2), ('walk', 1, 0), ('run', 1, 0),
        ):
            self.boy.machine.set_state(state)
            for direction, row in ((1, right_row), (-1, left_row)):
                with self.subTest(state=state, direction=direction):
                    self.boy.face_dir = direction
                    self.boy.draw()
                    self.assertEqual(self.boy.image.clip_draw.call_args.args[:4],
                                     (0, row * 100, 100, 100))

    def test_run_restores_slow_walk_after_ctrl_release(self):
        self.key(pico.SDLK_LCTRL)
        self.assertEqual(self.boy.state, 'idle')
        self.key(pico.SDLK_a)
        self.assertEqual(self.boy.state, 'slow_walk')
        self.boy.update(0.5)
        self.assertEqual(self.boy.x, 370)
        self.key(pico.SDLK_LSHIFT)
        self.assertEqual(self.boy.state, 'run')
        self.boy.update(0.25)
        self.assertEqual(self.boy.x, 290)
        self.key(pico.SDLK_RCTRL)
        self.key(pico.SDLK_LCTRL, False)
        self.assertEqual(self.boy.state, 'run')
        self.key(pico.SDLK_RCTRL, False)
        self.assertEqual(self.boy.state, 'run')
        self.key(pico.SDLK_LSHIFT)
        self.key(pico.SDLK_RSHIFT)
        self.key(pico.SDLK_LSHIFT, False)
        self.assertEqual(self.boy.state, 'run')
        self.key(pico.SDLK_RSHIFT, False)
        self.assertEqual(self.boy.state, 'slow_walk')
        self.key(pico.SDLK_LCTRL)
        self.key(pico.SDLK_a, False)
        self.assertEqual(self.boy.state, 'idle')

    def test_slow_walk_returns_to_walk(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_RCTRL)
        self.assertEqual(self.boy.state, 'slow_walk')
        self.key(pico.SDLK_RCTRL, False)
        self.assertEqual((self.boy.state, self.boy.frame), ('walk', 0))

    def test_run_restores_walk_after_ctrl_press(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_LSHIFT)
        self.key(pico.SDLK_LCTRL)
        self.assertEqual(self.boy.state, 'run')
        self.key(pico.SDLK_LSHIFT, False)
        self.assertEqual(self.boy.state, 'walk')

    def test_unrelated_movement_keys_do_nothing(self):
        for key in ('W', 'LEFT', 'RIGHT'):
            self.key(key)
        self.assertEqual((self.boy.state, self.boy.direction), ('idle', 0))

    def test_opposite_arrows_cancel_and_resume(self):
        self.key(pico.SDLK_a)
        self.key(pico.SDLK_d)
        self.assertEqual(self.boy.state, 'idle')
        self.boy.update(0.25)
        self.assertEqual(self.boy.x, 400)
        self.key(pico.SDLK_d, False)
        self.assertEqual((self.boy.state, self.boy.direction), ('walk', -1))

    def test_both_shift_keys_and_shift_before_movement(self):
        self.key(pico.SDLK_LSHIFT)
        self.assertEqual(self.boy.state, 'idle')
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_RSHIFT)
        self.key(pico.SDLK_LSHIFT, False)
        self.assertEqual(self.boy.state, 'run')
        self.key(pico.SDLK_RSHIFT, False)
        self.assertEqual(self.boy.state, 'walk')

    def test_bounds_and_frame_rate_independence(self):
        other = Boy()
        self.key(pico.SDLK_d)
        other.handle_event(SimpleNamespace(type=pico.SDL_KEYDOWN, key=pico.SDLK_d))
        self.boy.update(0.5)
        for _ in range(5):
            other.update(0.1)
        self.assertAlmostEqual(self.boy.x, other.x)
        self.assertAlmostEqual(self.boy.frame, other.frame)
        self.boy.update(10)
        self.assertEqual(self.boy.x, 750)
        self.key(pico.SDLK_d, False)
        self.key(pico.SDLK_a)
        self.boy.update(10)
        self.assertEqual(self.boy.x, 50)


if __name__ == '__main__':
    unittest.main()
