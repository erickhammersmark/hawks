#!/usr/bin/env python3

import disc
import io
import sys
import time
from PIL import Image
from threading import Timer


class MatrixController(object):
    """
    Implements an RGB Matrix and Dotstar Disc controller
    """

    settings = [
        "rows",
        "cols",
        "decompose",
        "brightness",
        "disc",
        "transpose",
        "rotate",
        "mock",
    ]

    def __init__(self, *args, **kwargs):
        self.dots = None
        self.rows = 32
        self.cols = 32
        self.decompose = False
        self.brightness = 255
        self.brightness_mask = None
        self.disc = False
        self.transpose = "none"
        self.rotate = 0
        self.mock = False
        self.image = None
        self.orig_frames = []
        self.frames = []
        self.frame_no = 0
        self.next_time = 0
        self.timer = None

        for (k, v) in kwargs.items():
            setattr(self, k, v)

        if self.disc:
            import board
            import adafruit_dotstar as dotstar

            self.dots = dotstar.DotStar(board.SCK, board.MOSI, 255, auto_write=False)

        self.init_matrix()

    def init_matrix(self):
        """
        The Matrix has you
        """

        if self.mock:
            from mock import RGBMatrix, RGBMatrixOptions
        else:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions

        options = RGBMatrixOptions()
        options.cols = self.cols
        if self.decompose:
            options.rows = int(self.rows / 2)
            options.chain_length = 2
        else:
            options.rows = self.rows
            options.chain_length = 1
        options.parallel = 1
        options.gpio_slowdown = 2
        options.hardware_mapping = (
            "adafruit-hat"  # If you have an Adafruit HAT: "adafruit-hat"
        )
        if not self.disc:
            self.matrix = RGBMatrix(options=options)
        self.frames = [(Image.new("RGB", (self.cols, self.rows), "black"), 0)]
        self.render()

    def set_frames(self, frames):
        self.orig_frames = frames
        self.show()

    def set_image(self, image):
        self.orig_frames = [(image, 0)]
        self.show()

    def fill_out(self, image):
        """
        If an image doesn't have enough rows or columns to fill the matrix,
        fill it in with black rows or columns.
        """
        cols, rows = image.size
        if cols >= self.cols and rows >= self.rows:
            return image

        new_image = Image.new("RGB", (self.cols, self.rows), "black")
        x = int((self.cols - cols) / 2)
        y = int((self.rows - rows) / 2)

        data = list(image.getdata())
        new_data = list(new_image.getdata())
        old_pixels = cols * rows
        new_pixels = self.cols * self.rows
        pos = 0
        new_pos = self.cols * y + x
        while new_pos < new_pixels and pos < old_pixels:
            new_data[new_pos : new_pos + cols] = data[pos : pos + cols]
            pos += cols
            new_pos += self.cols
        new_image.putdata(new_data)
        return new_image

    def resize_image(self, image, cols, rows):
        orig_c, orig_r = image.size
        new_c, new_r = cols, rows
        if orig_c > orig_r:
            new_r = new_r * float(orig_r) / orig_c
        elif orig_r > orig_c:
            new_c = new_c * float(orig_c) / orig_r
        image = image.resize((int(new_c), int(new_r)))
        if new_c < self.cols or new_r < self.rows:
            image = self.fill_out(image)
        return image

    def reshape(self, image):
        """
        Map image of size rows x cols to fit a
        rows/2 x cols*2 display. For example:

        rows = 64           AAAAAAAA  -->
        cols = 64           AAAAAAAA  -->  AAAAAAAABBBBBBBB
        panel_rows = 32     BBBBBBBB  -->  AAAAAAAABBBBBBBB
        panel_cols = 128    BBBBBBBB  -->

        Build a new Image of panel_rows x panel_cols,
        put first panel_rows rows of original image
        in to new image, repeat with next panel_rows
        rows of original image, but shifted cols to
        the right.
        """

        rows, cols = self.rows, self.cols
        p_rows, p_cols = int(rows / 2), cols * 2
        img = Image.new("RGB", (p_cols, p_rows), "black")
        orig_data = image.getdata()
        img_data = []
        for row in range(0, p_rows):
            r = row * cols
            for col in range(0, cols):
                img_data.append(orig_data[r + col])
            r = (row + p_rows - 1) * cols
            for col in range(cols, p_cols):
                img_data.append(orig_data[r + col])
        img.putdata(img_data)
        return img

    def brighten(self, image):
        """
        Fun fact: this will only ever darken.
        """
        if self.brightness == 255:
            return image

        data = list(image.getdata())
        newdata = []
        for idx, pixel in enumerate(data):
            brt = self.brightness
            if self.brightness_mask:
                brt = self.brightness_mask[idx]
                if brt < 0:
                    brt = self.brightness
            newdata.append(tuple(int(c * brt / 255) for c in pixel))
        image.putdata(newdata)
        return image

    def set_disc_image(self, image):
        """
        Renders a square/rectangular image for a DotStart disc.
        sample_image() maps the disc's circular coordinates to
        locations in the image and samples it.
        """
        self.disc = disc.Disc()
        pixels = self.disc.sample_image(image)
        for idx, pixel in enumerate(pixels):
            self.dots[idx] = pixel[0:3]
        self.dots.show()

    def make_png(self, image):
        with io.BytesIO() as output:
            image.save(output, format="PNG")
            return output.getvalue()

    def apply_transformations(self, image):
        if not self.disc:
            image = self.resize_image(image, self.cols, self.rows)

        if self.brightness != 255:
            image = self.brighten(image)

        if self.transpose != "none":
            operation = getattr(Image, self.transpose.upper(), None)
            if operation != None:
                image = image.transpose(operation)

        if self.rotate != 0:
            image = image.rotate(self.rotate)

        return image

    def SetImage(self, image):
        """
        Use instead of matrix.SetImage
        This does live last-second post-processing before calling matrix.SetImage
        """
        if self.disc:
            self.set_disc_image(image)
            return

        if self.decompose:
            if self.mock:
                setattr(self.matrix, "mock_square", True)
                self.matrix.SetImage(image)
            else:
                self.matrix.SetImage(self.reshape(image))
        else:
            self.matrix.SetImage(image)

    def render(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

        if not self.frames:
            return

        self.SetImage(self.frames[self.frame_no][0])

        duration = self.frames[self.frame_no][1]

        self.frame_no += 1
        if self.frame_no >= len(self.frames):
            self.frame_no = 0

        if duration:
            self.next_time += duration / 1000.0
            duration = self.next_time - time.time()
            self.timer = Timer(duration, self.render)
            self.timer.start()

    def show(self, return_image=False):
        """
        This is called every time something changes, like run_sign starting or
        a settings change via the API.  This is what the API calls to ensure
        that the changes it just set are acted upon.
        """

        self.frames = [
            (self.apply_transformations(img), duration)
            for img, duration in self.orig_frames
        ]
        self.frame_no = 0

        if return_image:
            if not self.frames:
                return None
            return self.make_png(self.frames[0][0])

        self.next_time = time.time()
        self.render()


def main():
    ctrl = MatrixController(mock=True)
    ctrl.set_image(Image.open("img/hawks.png").convert("RGB"))
    while True:
        time.sleep(1000)


if __name__ == "__main__":
    main()
