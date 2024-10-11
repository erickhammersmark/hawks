#!/usr/bin/env python3

import sys
from PIL import Image
from sample import generate_offsets

class RGBMatrix(object):
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.clear_image = Image.new("RGB", (self.options.cols, self.options.rows), (0, 0, 0, 0))
        self.frame = None
        self.image = None

    def text_as_color(self, text, rgb):
        """
        Return string with text prefixed by ANSI escape
        code to set the backgorund to the color specified
        by "rgb" (a tuple of r, g, b bytes).  The string
        also include the escape sequence to set the terminal
        back to its default colors.
        """
        escape_seq = "\033[48;2;{0};{1};{2}m{3}\033[10;m"
        return escape_seq.format(*rgb[0:3], text)

    def print_image(self, image, cols=None):
        if image is self.image and self.frame:
            return
        count = 0
        output = []
        output.append("\033[2J\033[H")
        output.append("\n")
        data = image.getdata()

        if cols is None:
            cols = self.options.cols
            if cols == 4 * self.options.rows:
                cols /= 2

        for px in data:
            output.append(self.text_as_color("  ", px))
            count += 1
            if count % cols == 0:
                output.append("\n")
        output.append("\n")

        self.image = image
        self.frame = "".join(output)
        sys.stdout.write(self.frame)

    def SetImage(self, image, *args, **kwargs):
        self.print_image(image)

    def Clear(self):
        self.print_image(self.clear_image)


class RGBMatrixOptions(object):
    def __init__(self, *args, **kwargs):
        pass


class board(object):
    MOSI = 0
    SCK = 0


class adafruit_dotstar(object):
    class DotStar(object):
        def __init__(self, sck, mosi, num_pixels, auto_write=True, disc=None):
            self.dots = list((0, 0, 0, 0) * 255)
            self.disc = disc
        def __setitem__(self, idx, value):
            self.dots[idx] = value
        def show(self):
            pixels = self.disc.get_pixels((64, 64))
            image = Image.new("RGB", (64, 64), (0, 0, 0, 0))
            data = list(image.getdata())
            for idx, pixel in enumerate(pixels):
                data[pixel[0] + 64 * pixel[1]] = self.dots[idx]
            image.putdata(data)
            options = RGBMatrixOptions()
            setattr(options, "cols", 64)
            setattr(options, "rows", 64)
            matrix = RGBMatrix(options=options)
            matrix.print_image(image)

