#!/usr/bin/env python3

import sys


class RGBMatrix(object):
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():

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

    def print_image(self, image):
        count = 0
        output = []
        output.append("\033[2J\033[H")
        output.append("\n")
        data = image.getdata()

        # filthy hack inside a kind of nice hack
        if len(data) == 1024:
            cols = 32
        else:
            cols = 128
        if hasattr(self, "mock_square") and getattr(self, "mock_square"):
            cols = 64

        for px in data:
            output.append(self.text_as_color("  ", px))
            count += 1
            if count % cols == 0:
                output.append("\n")
        output.append("\n")

        sys.stdout.write("".join(output))

    def SetImage(self, image, *args, **kwargs):
        self.print_image(image)


class RGBMatrixOptions(object):
    def __init__(self, *args, **kwargs):
        pass
