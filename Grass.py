from pathlib import Path

from pico2d import load_image

class Grass:
    def __init__(self):
        self.image = load_image(str(Path(__file__).with_name('grass.png')))

    def draw(self):
        self.image.draw(400, 30)

    def update(self):
        pass
