"""Loop timing and event routing without a window or game resources."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class MainTests(unittest.TestCase):
    def setUp(self):
        pico = ModuleType('pico2d')
        pico.SDL_QUIT, pico.SDL_KEYDOWN, pico.SDLK_ESCAPE = 1, 2, 3
        pico.get_events = Mock(return_value=[])
        self.pico = pico
        spec = importlib.util.spec_from_file_location('game_loop_under_test', Path(__file__).with_name('main.py'))
        self.main = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            'pico2d': pico, 'Boy': SimpleNamespace(Boy=Mock()),
            'Grass': SimpleNamespace(Grass=Mock()),
        }):
            spec.loader.exec_module(self.main)
        self.main.boy = Mock()
        self.main.world = [Mock(), self.main.boy]
        self.main.running = True

    def test_long_frame_preserves_time_without_a_catchup_loop(self):
        self.main.update_world(3600)
        self.main.boy.update.assert_called_once_with(3600)

    def test_zero_elapsed_time_skips_updates(self):
        self.main.update_world(0)
        self.main.boy.update.assert_not_called()

    def test_exit_events_stop_further_event_routing(self):
        for event in (SimpleNamespace(type=self.pico.SDL_QUIT),
                      SimpleNamespace(type=self.pico.SDL_KEYDOWN, key=self.pico.SDLK_ESCAPE)):
            with self.subTest(event=event):
                self.main.running = True
                self.pico.get_events.return_value = [event, SimpleNamespace(type=9)]
                self.main.handle_events()
                self.assertFalse(self.main.running)
                self.main.boy.handle_event.assert_not_called()

    def test_game_input_reaches_boy(self):
        event = SimpleNamespace(type=self.pico.SDL_KEYDOWN, key=99)
        self.pico.get_events.return_value = [event]
        self.main.handle_events()
        self.main.boy.handle_event.assert_called_once_with(event)


if __name__ == '__main__':
    unittest.main()
