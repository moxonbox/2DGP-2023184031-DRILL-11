"""Capture the game's SDL framebuffer without desktop automation."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))

import pico2d.pico2d as pico
import main

output = Path(__file__).parent / sys.argv[1]
output.mkdir(exist_ok=True)
pico.open_canvas()
if not pico.renderer:
    pico.renderer = pico.SDL_CreateRenderer(pico.window, -1, pico.SDL_RENDERER_SOFTWARE)
if not pico.renderer:
    raise RuntimeError(pico.SDL_GetError())
try:
    main.reset_world()
    surface = pico.SDL_CreateRGBSurfaceWithFormat(0, 800, 600, 32, pico.SDL_PIXELFORMAT_RGBA32)
    if not surface:
        raise RuntimeError('Cannot allocate capture surface')
    try:
        states = (*main.boy.ANIMATIONS, 'jump', 'autorun')
        for state in states:
            for direction in (1, -1):
                main.reset_world()
                if state == 'jump':
                    main.boy.jump()
                    main.boy.update(0.2)
                elif state == 'autorun':
                    for key in (pico.SDLK_d if direction == 1 else pico.SDLK_s, pico.SDLK_a):
                        main.boy.handle_event(SimpleNamespace(type=pico.SDL_KEYDOWN, key=key))
                else:
                    main.boy.machine.set_state(state)
                main.boy.face_dir = direction
                main.boy.frame = 0
                pico.clear_canvas()
                for obj in main.world:
                    obj.draw()
                if pico.SDL_RenderReadPixels(pico.renderer, None, surface.contents.format.contents.format,
                                             surface.contents.pixels, surface.contents.pitch) != 0:
                    raise RuntimeError(pico.SDL_GetError())
                path = output / f'{state}_{direction}.png'
                if pico.IMG_SavePNG(surface, str(path).encode('utf-8')) != 0:
                    raise RuntimeError(pico.SDL_GetError())
                pico.update_canvas()
        print(f'Captured {len(states) * 2} actual SDL frames: {output}')
    finally:
        pico.SDL_FreeSurface(surface)
finally:
    pico.close_canvas()
