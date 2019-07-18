#!/usr/bin/env python

'''
Implements the math to map pixel positions in an Adafruit Dotstart Disc (or
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
'''

import math

class DotstarPixel(object):
    def __init__(self, radius, position, total_pixels):
        self.radius = radius
        self.position = position
        self.total_pixels = total_pixels

    def __repr__(self):
        return "r: {0}, p: {1}, total: {2}".format(self.radius, self.position, self.total_pixels)

class Disc(object):
    '''
    pixels and methods for mapping a Dotstar Disc or similar to an x, y space

    Disc.pixels is a list of dicts.  Each pixel is a dict of:
        radius          distance from the origin of the circle
        position        ordinal position along the circle
        total_pixels    number of pixels in this circle
    '''

    def __init__(self, *args, **kwargs):
        self.pixels = []
        self.max_radius = None

    def get_pixels(self, xy_range, circles=None):
        '''
        Get all of the x,y pairs for the pixels on the disc.
        xy_range is a tuple of (x,y) sizes (result will start at 0)
        circles is a list of (radius, pixel_count) tuples.
        '''
        self.init_pixels(circles)
        return (self.calculate_xy(px, xy_range) for px in self.pixels)

    def init_pixels(self, circles=None):
        if circles == None:
            # dotstar disc numbers, radius of and count of pixels in each circle
            circles = [
                (0.0, 1),
                (0.5, 6),
                (1.0, 12),
                (1.5, 20),
                (2.0, 24),
                (2.5, 28),
                (3.0, 32),
                (3.5, 40),
                (4.0, 44),
                (4.5, 48),
            ]
        for (radius, num_pixels) in circles:
            for n in range(num_pixels):
                self.pixels.append(DotstarPixel(radius, n, num_pixels))

    def get_max_radius(self):
        if self.max_radius is None:
            self.max_radius = max(getattr(pixel, "radius") for pixel in self.pixels)
        return self.max_radius
 
    def calculate_xy(self, pixel, xy):
        '''
        Given a pixel and an xy range (dict with keys 'x' and 'y'),
        calculate the position of the pixel in the range.
        returns a tupel of x, y
        '''

        (x_range, y_range) = xy

        theta = math.radians((360.0 / pixel.total_pixels) * pixel.position)
        y = math.sin(theta) * pixel.radius + self.get_max_radius()
        x = math.cos(theta) * pixel.radius + self.get_max_radius()

        y = (y / (2 * self.get_max_radius())) * y_range
        x = (x / (2 * self.get_max_radius())) * x_range

        return (x, y)


if __name__ == "__main__":
    disc = Disc()
    disc.init_pixels()
    print(disc.pixels)
    print(disc.get_max_radius())
    print('\n'.join(str(px) for px in disc.get_pixels((100,100))))
