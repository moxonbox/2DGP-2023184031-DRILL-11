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
        elif event.type == SDL_KEYDOWN and event.key == SDLK_ESCAPE:
            running = False
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
    for o in world:
        if o is boy:
            o.update(dt)
        else:
            o.update()


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
            dt = min(current_time - previous_time, 0.1)
            previous_time = current_time
            handle_events()
            update_world(dt)
            render_world()
            delay(0.01)
    finally:
        close_canvas()
