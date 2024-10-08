#!/usr/bin/env python3

"""
Controller for an Adafruit Dotstar disc. 255 Dotstar RGBW modules laid out
in a polar pattern.  Implements the math to map pixel positions in a disc (or
any similarly arranged concentric circles of pixels) into a rectilinear pixel
space.

Dotstar layout:

total_pixels    radius
1               0
6               0.5"
12              1"
20              1.5"
24              2"
28              2.5"
32              3"
40              3.5"
44              4"
48              4.5"
"""

mock = False
try:
    import adafruit_dotstar
    import board
except:
    from mock import adafruit_dotstar, board
    mock = True

import math
import sys
from PIL import Image
from sample import sample, generate_offsets

class DotstarPixel(object):
    def __init__(self, radius, position, total_pixels):
        self.radius = radius
        self.position = position
        self.total_pixels = total_pixels

    def __repr__(self):
        return f"r: {self.radius}, p: {self.position}, total: {self.total_pixels}"


class Disc(object):
    """
    pixels and methods for mapping a Dotstar Disc or similar to an x, y space

    Disc.pixels is a list of dicts.  Each pixel is a dict of:
        radius          distance from the origin of the circle
        position        ordinal position along the circle
        total_pixels    number of pixels in this circle
    """

    # dotstar disc numbers, radius of and count of pixels in each circle
    circles = [
        (4.5, 48),
        (4.0, 44),
        (3.5, 40),
        (3.0, 32),
        (2.5, 28),
        (2.0, 24),
        (1.5, 20),
        (1.0, 12),
        (0.5, 6),
        (0.0, 1),
    ]

    def __init__(self, *args, **kwargs):
        self.pixels = []
        self.max_radius = None
        if mock:
            self.dots = adafruit_dotstar.DotStar(board.SCK, board.MOSI, 255, auto_write=False, disc=self)
        else:
            self.dots = adafruit_dotstar.DotStar(board.SCK, board.MOSI, 255, auto_write=False)

    def set_image(self, image):
        """
        Write pixels to the DotStar disc. image should contain
        a list of 255 RGBA pixel values. If it doesn't then
        render a quare/rectangular image for a DotStar disc.
        sample_image() maps the disc's circular coordinates to
        locations in the image and samples it.
        """

        #if len(image) != 255:
        if not isinstance(image, list):
            pixels = self.sample_image(image)
        else:
            pixels = image
        for idx, pixel in enumerate(pixels):
            self.dots[idx] = pixel[0:3]
        self.dots.show()

    def blank(self):
        for idx, tup in enumerate(self.dots):
            self.dots[idx] = (0, 0, 0)
        self.dots.show()

    def get_pixels(self, xy_range):
        """
        Get all of the x,y pairs for the pixels on the disc.
        xy_range is a tuple of (x,y) sizes (result will start at 0)
        circles is a list of (radius, pixel_count) tuples.
        """
        self.init_pixels()
        return (self.calculate_xy(px, xy_range) for px in self.pixels)

    def init_pixels(self):
        self.pixels = []
        for (radius, num_pixels) in self.circles:
            for n in range(num_pixels):
                self.pixels.append(DotstarPixel(radius, n, num_pixels))

    def get_max_radius(self):
        if self.max_radius is None:
            self.max_radius = max(getattr(pixel, "radius") for pixel in self.pixels)
        return self.max_radius

    def calculate_xy(self, pixel, xy):
        """
        Given a pixel and an xy range (dict with keys 'x' and 'y'),
        calculate the position of the pixel in the range.
        returns a tupel of x, y
        """

        (x_range, y_range) = xy

        theta = math.radians((360.0 / pixel.total_pixels) * pixel.position)
        y = math.sin(theta) * pixel.radius + self.get_max_radius()
        x = math.cos(theta) * pixel.radius + self.get_max_radius()

        y = (y / (2 * self.get_max_radius())) * y_range
        x = (x / (2 * self.get_max_radius())) * x_range

        y = min(y_range - 1, int(y))
        x = min(x_range - 1, int(x))

        return (x, y)

    def sample_image(self, image, radius=1):
        pixels = self.get_pixels(image.size)
        offsets = generate_offsets("circle", radius)
        return sample(image, pixels, offsets)


if __name__ == "__main__":
    disc = Disc()
    img = Image.open("circle.jpg").convert("RGB")
    samples = disc.sample_image(img)
    # samples = sample(img, disc.get_pixels(img.size), generate_offsets("circle", 2))
    new_img = Image.new("RGB", img.size, "black")
    new_img_data = []
    new_img_data.extend(new_img.getdata())
    cols, rows = new_img.size
    for (pos, pixel) in zip(disc.get_pixels(img.size), samples):
        x, y = pos
        # print(x, y, y * cols + x)
        new_img_data[y * cols + x] = pixel
    # print(new_img_data)
    new_img.putdata(new_img_data)
    new_img.save("test.png")

    # disc.init_pixels()
    # print(disc.pixels)
    # print(disc.get_max_radius())
    # print('\n'.join(str(px) for px in disc.get_pixels((100,100))))
