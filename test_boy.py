"""Headless controller checks using the real transitions state machine."""

import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


pico = ModuleType('pico2d')
for value, name in enumerate((
    'SDL_KEYDOWN', 'SDL_KEYUP', 'SDLK_s', 'SDLK_d',
    'SDLK_LSHIFT', 'SDLK_RSHIFT', 'SDLK_LCTRL', 'SDLK_RCTRL', 'SDLK_SPACE', 'SDLK_a',
)):
    setattr(pico, name, value)
pico.load_image = Mock()
pico.get_canvas_width = lambda: 800
with patch.dict(sys.modules, pico2d=pico):
    import Boy as boy_module

Boy = boy_module.Boy


class BoyTests(unittest.TestCase):
    def setUp(self):
        self.boy = Boy()

    def key(self, key, down=True):
        self.boy.handle_event(SimpleNamespace(
            type=pico.SDL_KEYDOWN if down else pico.SDL_KEYUP, key=key,
        ))

    def test_seven_distinct_state_classes_are_registered(self):
        expected = {
            'idle': 'Idle', 'Sleep': 'Sleep', 'slow_walk': 'SlowWalk',
            'walk': 'Walk', 'run': 'Run', 'jump': 'Jump', 'autorun': 'AutoRun',
        }
        self.assertEqual(set(self.boy.machine.states), set(expected))
        for name, class_name in expected.items():
            self.assertEqual(type(self.boy.machine.get_state(name)).__name__, class_name)

    def test_stationary_jump_and_landing(self):
        ground = self.boy.y
        self.key(pico.SDLK_SPACE)
        self.assertEqual(self.boy.state, 'jump')
        self.boy.update(0.2)
        self.assertAlmostEqual(self.boy.y, ground + 420 * 0.2 - 490 * 0.2 ** 2)
        self.assertEqual(self.boy.x, 400)
        self.boy.update(0.7)
        self.assertEqual((self.boy.state, self.boy.y, self.boy.vertical_speed), ('idle', ground, 0))

    def test_jump_allows_movement_and_modifier_changes(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_SPACE)
        self.boy.update(0.1)
        self.assertEqual((self.boy.state, self.boy.x), ('jump', 416))
        self.key(pico.SDLK_LSHIFT)
        self.boy.update(0.1)
        self.assertEqual((self.boy.state, self.boy.x), ('jump', 448))
        self.boy.update(0.7)
        self.assertEqual(self.boy.state, 'run')

    def test_jump_does_not_restart_in_air_and_ignores_autorun(self):
        self.key(pico.SDLK_SPACE)
        self.boy.update(0.2)
        velocity = self.boy.vertical_speed
        self.key(pico.SDLK_SPACE, False)
        self.key(pico.SDLK_SPACE)
        self.key(pico.SDLK_a)
        self.assertEqual((self.boy.state, self.boy.vertical_speed), ('jump', velocity))

    def test_jump_release_and_reverse_lands_in_current_state(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_SPACE)
        self.boy.update(0.1)
        self.key(pico.SDLK_d, False)
        self.key(pico.SDLK_s)
        self.key(pico.SDLK_LCTRL)
        self.boy.update(0.8)
        self.assertEqual((self.boy.state, self.boy.direction), ('slow_walk', -1))

    def test_jump_height_is_frame_rate_independent(self):
        other = Boy()
        other.handle_event(SimpleNamespace(type=pico.SDL_KEYDOWN, key=pico.SDLK_SPACE))
        self.key(pico.SDLK_SPACE)
        self.boy.update(0.3)
        for _ in range(3):
            other.update(0.1)
        self.assertAlmostEqual(self.boy.y, other.y)
        self.assertAlmostEqual(self.boy.vertical_speed, other.vertical_speed)

    def test_idle_sleeps_after_fifty_tenth_second_updates(self):
        for _ in range(50):
            self.boy.update(0.1)
        self.assertEqual(self.boy.state, 'Sleep')

    def test_long_jump_update_preserves_time_after_landing(self):
        self.key(pico.SDLK_SPACE)
        self.boy.update(6)
        self.assertEqual(self.boy.state, 'Sleep')
        self.assertEqual(self.boy.y, self.boy.GROUND_Y + 36)

    def test_jump_landing_matches_small_updates(self):
        other = Boy()
        other.handle_event(SimpleNamespace(type=pico.SDL_KEYDOWN, key=pico.SDLK_SPACE))
        self.key(pico.SDLK_SPACE)
        self.boy.update(2)
        for _ in range(20):
            other.update(0.1)
        self.assertEqual(self.boy.state, other.state)
        self.assertAlmostEqual(self.boy.idle_elapsed, other.idle_elapsed)
        self.assertAlmostEqual(self.boy.frame, other.frame)

    def test_autorun_expires_after_fifty_tenth_second_updates(self):
        self.key(pico.SDLK_a)
        for _ in range(50):
            self.boy.update(0.1)
        self.assertEqual(self.boy.state, 'idle')

    def test_autorun_latches_movement_and_expires_then_sleeps(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_a)
        self.key(pico.SDLK_d, False)
        self.boy.update(0.5)
        self.assertEqual((self.boy.state, self.boy.x), ('autorun', 520))
        self.boy.update(4.5)
        self.assertEqual((self.boy.state, self.boy.direction, self.boy.keys), ('idle', 0, set()))
        self.boy.update(5)
        self.assertEqual(self.boy.state, 'Sleep')

    def test_autorun_new_state_keys_cancel_immediately(self):
        for key, state in ((pico.SDLK_s, 'walk'), (pico.SDLK_LCTRL, 'idle'),
                           (pico.SDLK_LSHIFT, 'idle'), (pico.SDLK_SPACE, 'jump')):
            with self.subTest(key=key):
                self.boy = Boy()
                self.key(pico.SDLK_d)
                self.key(pico.SDLK_a)
                self.key(pico.SDLK_d, False)
                self.key(key)
                self.assertEqual(self.boy.state, state)

    def test_autorun_latches_all_ground_states(self):
        for source in self.boy.ANIMATIONS:
            with self.subTest(source=source):
                self.boy = Boy()
                self.boy.machine.set_state(source)
                self.boy.direction = 1 if source in ('walk', 'slow_walk', 'run') else 0
                self.key(pico.SDLK_a)
                self.boy.update(0.1)
                expected = 'run' if source in ('idle', 'Sleep') else source
                self.assertEqual((self.boy.state, self.boy.auto_state), ('autorun', expected))
                self.assertAlmostEqual(self.boy.x, 400 + self.boy.ANIMATIONS[expected][2] * 1.5 * 0.1)

    def test_autorun_toggle_repeat_and_unrelated_keys(self):
        self.key(pico.SDLK_a)
        self.boy.update(4)
        self.key(pico.SDLK_a)
        self.key('unrelated')
        self.assertEqual((self.boy.state, self.boy.auto_elapsed), ('autorun', 4))
        self.key(pico.SDLK_a, False)
        self.key(pico.SDLK_a)
        self.assertEqual(self.boy.state, 'idle')

    def test_autorun_repeated_held_movement_key_does_not_cancel(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_a)
        self.key(pico.SDLK_d)
        self.assertEqual(self.boy.state, 'autorun')
        self.key(pico.SDLK_d, False)
        self.key(pico.SDLK_d)
        self.assertEqual(self.boy.state, 'walk')

    def test_autorun_timeout_preserves_remaining_idle_time(self):
        self.key(pico.SDLK_a)
        self.boy.update(9)
        self.assertEqual((self.boy.state, self.boy.idle_elapsed), ('idle', 4))

    def test_autorun_reflects_at_both_scaled_edges(self):
        for key, start, expected, direction in (
            (pico.SDLK_d, 720, 706, -1), (pico.SDLK_s, 80, 94, 1),
        ):
            with self.subTest(direction=direction):
                self.boy = Boy()
                self.boy.x = start
                self.key(key)
                self.key(pico.SDLK_a)
                self.boy.update(0.1)
                self.assertAlmostEqual(self.boy.x, expected)
                self.assertEqual((self.boy.direction, self.boy.face_dir), (direction, direction))

    def test_autorun_multiple_bounces_match_small_steps(self):
        for key in (pico.SDLK_s, pico.SDLK_d):
            self.boy = Boy()
            self.key(key)
            self.key(pico.SDLK_LSHIFT)
            self.key(pico.SDLK_a)
            other = Boy()
            for input_key in (key, pico.SDLK_LSHIFT, pico.SDLK_a):
                other.handle_event(SimpleNamespace(type=pico.SDL_KEYDOWN, key=input_key))
            self.boy.update(4.5)
            for _ in range(45):
                other.update(0.1)
            self.assertAlmostEqual(self.boy.x, other.x)
            self.assertEqual(self.boy.direction, other.direction)

    def test_autorun_scaled_feet_and_narrow_viewport(self):
        self.key(pico.SDLK_d)
        self.key(pico.SDLK_a)
        self.boy.draw()
        _, bottom, _, _, _, center_y, width, height = self.boy.image.clip_draw.call_args.args
        padding = self.boy.FOOT_PADDING[bottom // 100][0]
        self.assertEqual((width, height), (150, 150))
        self.assertEqual(center_y - height / 2 + padding * 1.5, self.boy.GROUND_Y)
        with patch.object(boy_module, 'get_canvas_width', return_value=100):
            self.boy.update(0.1)
        self.assertEqual(self.boy.x, 50)

    def test_idle_and_sleep_autorun_use_run_in_facing_direction(self):
        for source in ('idle', 'Sleep'):
            for direction in (-1, 1):
                with self.subTest(source=source, direction=direction):
                    self.boy = Boy()
                    if source == 'Sleep':
                        self.boy.update(5)
                    self.boy.face_dir = direction
                    self.key(pico.SDLK_a)
                    self.key(pico.SDLK_a, False)
                    self.assertEqual((self.boy.state, self.boy.auto_state), ('autorun', 'run'))
                    self.assertEqual(self.boy.direction, direction)
                    self.boy.update(0.1)
                    self.assertAlmostEqual(self.boy.x, 400 + direction * 48)
                    self.assertAlmostEqual(self.boy.frame, 1.6)
                    self.boy.draw()
                    args = self.boy.image.clip_draw.call_args.args
                    self.assertEqual(args[1], 100 if direction == 1 else 0)
                    self.assertEqual(args[-2:], (150, 150))

    def test_idle_and_sleep_autorun_still_expire_and_allow_state_input(self):
        for source in ('idle', 'Sleep'):
            for action in ('timeout', 'input'):
                with self.subTest(source=source, action=action):
                    self.boy = Boy()
                    if source == 'Sleep':
                        self.boy.update(5)
                    self.key(pico.SDLK_a)
                    if action == 'timeout':
                        self.boy.update(5)
                        self.assertEqual((self.boy.state, self.boy.direction), ('idle', 0))
                    else:
                        self.key(pico.SDLK_s)
                        self.assertEqual((self.boy.state, self.boy.direction), ('walk', -1))

    def test_held_space_wakes_without_immediate_jump(self):
        self.boy.update(5)
        self.key(pico.SDLK_SPACE)
        self.key(pico.SDLK_SPACE)
        self.assertEqual(self.boy.state, 'idle')
        self.key(pico.SDLK_SPACE, False)
        self.key(pico.SDLK_SPACE)
        self.assertEqual(self.boy.state, 'jump')

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
        for direction_key, direction in ((pico.SDLK_s, -1), (pico.SDLK_d, 1)):
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
        self.key(pico.SDLK_s)
        self.boy.update(0.125)
        self.key(pico.SDLK_s)
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
        self.key(pico.SDLK_s)
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
        self.key(pico.SDLK_s, False)
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
        self.key(pico.SDLK_s)
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
        self.key(pico.SDLK_s)
        self.boy.update(10)
        self.assertEqual(self.boy.x, 50)


if __name__ == '__main__':
    unittest.main()
