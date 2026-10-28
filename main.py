from pico2d import *
from time import perf_counter

from Grass import Grass
from Boy import Boy


def handle_events():
    global running

    event_list = get_events()
    for event in event_list:
        if event.type == SDL_QUIT:
            running = False
            break
        elif event.type == SDL_KEYDOWN and event.key == SDLK_ESCAPE:
            running = False
            break
        else:
            boy.handle_event(event)


def reset_world():
    global world
    global boy

    world = []

    grass = Grass()
    world.append(grass)

    boy = Boy()
    world.append(boy)



def update_world(dt):
    # Subdivide physics without dropping elapsed time from the five-second timers.
    while dt > 0:
        step = min(dt, 0.1)
        for o in world:
            if o is boy:
                o.update(step)
            else:
                o.update()
        dt -= step


def render_world():
    clear_canvas()
    for o in world:
        o.draw()
    update_canvas()


if __name__ == '__main__':
    running = True
    open_canvas()
    try:
        reset_world()
        previous_time = perf_counter()
        while running:
            current_time = perf_counter()
            dt = current_time - previous_time
            previous_time = current_time
            handle_events()
            if not running:
                break
            update_world(dt)
            render_world()
            delay(0.01)
    finally:
        close_canvas()
