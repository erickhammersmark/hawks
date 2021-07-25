#!/usr/bin/env python3

import disc
import io
import sys
import time
from base import Base
from PIL import Image
from threading import Timer


class MatrixController(Base):
    """
    Implements an RGB Matrix and Dotstar Disc controller
    """

    settings = [
        "rows",
        "cols",
        "back_and_forth",
        "brightness",
        "decompose",
        "disc",
        "transpose",
        "rotate",
        "mock",
        "zoom",
        "zoom_level",
        "zoom_center",
        "x",
        "y",
        "fit",
        "debug",
    ]

    def __init__(self, *args, **kwargs):
        self.rows = 32
        self.cols = 32
        self.decompose = False
        self.brightness = 255
        self.brightness_mask = None
        self.disc = False
        self._disc = None
        self.transpose = "none"
        self.rotate = 0
        self.mock = False
        self.zoom = False
        self.image = None
        self.orig_frames = []
        self.frames = []
        self.dot_frames = []
        self.frame_no = 0
        self.next_time = 0
        self.timer = None
        self.go = True
        self.direction = 1
        self.back_and_forth = False
        self.zoom_level = 1.0
        self.zoom_center = True
        self.x = 0
        self.y = 0
        self.fit = False
        self.debug = False

        for (k, v) in kwargs.items():
            setattr(self, k, v)

        self.init_matrix()

    def init_matrix(self):
        """
        The Matrix has you
        """

        self.db("Initializing matrix")

        self.frames = [(Image.new("RGB", (self.cols, self.rows), "black"), 0)]

        if self.disc:
            self._disc = disc.Disc(mock=self.mock)
            self.dot_frames = [(self._disc.sample_image(self.frames[0][0]), 0)]
        else:
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
                "adafruit-hat-pwm"  # If you have an Adafruit HAT: "adafruit-hat" or "adafruit-hat-pwm"
                                    # https://github.com/hzeller/rpi-rgb-led-matrix#troubleshooting
            )
            self.matrix = RGBMatrix(options=options)

        self.show()

    def set_frames(self, frames):
        self.orig_frames = frames

    def set_image(self, image):
        self.orig_frames = [(image, 0)]

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
        orig_image_c, orig_image_r = image.size
        panel_c, panel_r = cols, rows
        new_c, new_r = panel_c, panel_r
        left, right, top, bottom = 0, orig_image_c - 1, 0, orig_image_r - 1

        # all of the manipulations are in image pixel space
        # the image is not scaled into panel space until the call to image.resize() at the end
        if self.zoom:
            image_c, image_r = image.size
            # zoom in on a pixel position in the image
            # calculate how much the image we are keeping in each dimension
            # bring bottom and right in total - that much
            zoomed_r = image_r / self.zoom_level
            zoomed_c = image_c / self.zoom_level
            if self.zoom_center:
                left = (image_c - zoomed_c) / 2
                right = image_c - left
                top = (image_r - zoomed_r) / 2
                bottom = image_r - top
            else:
                left = self.x
                right = left + zoomed_c
                top = self.y
                bottom = self.y + zoomed_r
            image = image.crop((left, top, right, bottom))
        if self.fit:
            # crop the image to be square, preserving all of one dimension
            image_c, image_r = image.size
            left, right, top, bottom = 0, image_c - 1, 0, image_r - 1
            if image_r > image_c:
                delta = image_r - image_c
                top = delta / 2
                bottom -= (delta - top)
            elif image_c > image_r:
                delta = image_c - image_r
                left = delta / 2
                right -= (delta - left)
            image = image.crop((left, top, right, bottom))
        else:
            # scale such that the longest dimension of the image fits on the panel
            # default is to scale to the size (panel_c, panel_r)
            # if one dimension is longer than the other, scale the shorter one
            # to less than panel_c or panel_r to preserve aspect ratio
            image_c, image_r = image.size
            if image_c > image_r:
                new_r = panel_r * float(image_r) / image_c
            elif image_r > image_c:
                new_c = panel_c * float(image_c) / image_r
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

    def make_png(self, image):
        with io.BytesIO() as output:
            image.save(output, format="PNG")
            return output.getvalue()

    def apply_transformations(self, image, max_brightness=False):
        if not self.disc:
            image = self.resize_image(image, self.cols, self.rows)

        if self.brightness != 255 and not max_brightness:
            image = self.brighten(image)

        if self.transpose != "none":
            operation = getattr(Image, self.transpose.upper(), None)
            if operation != None:
                image = image.transpose(operation)

        if self.rotate != 0:
            image = image.rotate(self.rotate)

        return image

    def SetFrame(self, frame_no):
        """
        Use instead of matrix.SetImage
        This does live last-second post-processing before calling matrix.SetImage
        """
        self.db(f"SetFrame({frame_no})")

        if self.disc:
            return self._disc.set_image(self.dot_frames[frame_no][0])

        self.db("Decomposing (if requierd) and setting matrix image")
        image = self.frames[frame_no][0]

        # TODO: why do I do this at SetFrame time? Why not pre-render this?
        if self.decompose:
            if self.mock:
                self.matrix.SetImage(image)
            else:
                self.matrix.Clear()
                self.matrix.SetImage(self.reshape(image))
        else:
            self.matrix.SetImage(image)

    def render(self):
        self.db("render()")

        if self.timer:
            self.timer.cancel()
            self.timer = None

        if not self.frames:
            return

        if not self.go:
            return

        self.SetFrame(self.frame_no)

        duration = self.frames[self.frame_no][1]

        self.frame_no += self.direction
        if self.back_and_forth:
            if self.frame_no >= len(self.frames):
                self.frame_no = len(self.frames) - 2
                self.direction = -1
            if self.frame_no <= 0:
                self.frame_no = 0
                self.direction = 1
        else:
            if self.frame_no >= len(self.frames):
                self.frame_no = 0

        if duration:
            self.next_time += duration / 1000.0
            duration = self.next_time - time.time()
            self.timer = Timer(duration, self.render)
            self.timer.start()

    def disc_animations(self):
      
        circle_colors = []
        color = 100
        for circle in self._disc.circles:
            circle_colors.append(color)
            color += 100

        def rainbow_color_from_value(value):
          border = 0
          num_buckets = 6
          max_value = 1024 # implicit min value of 0
          bucket = (max_value - border * 2) / num_buckets
          value = min(value, bucket * num_buckets) # bucket * num_buckets is the actual max value
          r = 0
          g = 0
          b = 0
          bright = self.brightness
      
          if value < border:
            # red
            r = bright
            g = 0
            b = 0
          elif value < border + bucket * 1:
            # red + increasing green
            value -= border + bucket * 0
            value = (value * bright) / bucket
            r = bright
            g = value
            b = 0
          elif value < border + bucket * 2:
            # green + decreasing red
            value -= border + bucket * 1
            value = bucket - value
            value = (value * bright) / bucket
            r = value
            g = bright
            b = 0
          elif value < border + bucket * 3:
            # green + increasing blue
            value -= border + bucket * 2
            value = (value * bright) / bucket
            r = 0
            g = bright
            b = value
          elif value < border + bucket * 4:
            # blue + decreasing green
            value -= border + bucket * 3
            value = bucket - value
            value = (value * bright) / bucket
            r = 0
            g = value
            b = bright
          elif value < border + bucket * 5:
            # blue + increasing red
            value -= border + bucket * 4
            value = (value * bright) / bucket
            r = value
            g = 0
            b = bright
          else:
            # red + decreasing blue
            value -= border + bucket * 5
            value = bucket - value
            value = (value * bright) / bucket
            r = bright
            g = 0
            b = value
          return (int(g), int(r), int(b))
      
        while True:
            p = 0
            for idx, circle in enumerate(self._disc.circles):
                color = rainbow_color_from_value(circle_colors[idx])
                for n in range(0, circle[1]):
                    self._disc.dots[p] = color
                    p += 1
                circle_colors[idx] += 7
                if circle_colors[idx] >= 1024:
                    circle_colors[idx] = 0
            self._disc.show()

    def show(self, return_image=False):
        """
        This is called every time something changes, like run_sign starting or
        a settings change via the API.  This is what the API calls to ensure
        that the changes it just set are acted upon.
        """

        self.db(f"show({return_image})")

        if return_image:
            self.db("Returning png")
            return self.make_png(self.apply_transformations(self.orig_frames[0][0], max_brightness=True))

        self.db("transforming frames")
        self.frames = [
            (self.apply_transformations(img), duration)
            for img, duration in self.orig_frames
        ]

        if self.disc:
            self.db("Sampling frames for disc")
            self.dot_frames = [(self._disc.sample_image(frame[0]), frame[1]) for frame in self.frames]

        self.frame_no = 0

        self.next_time = time.time()
        self.go = True
        self.direction = 1
        self.render()

    def stop(self):
        """
        Stop displaying new frames.
        """
        self.go = False

    def start(self):
        """
        Resume displaying new frames.
        """
        self.go = True


def main():
    ctrl = MatrixController(mock=True)
    ctrl.set_image(Image.open("img/hawks.png").convert("RGB"))
    ctrl.show()
    while True:
        time.sleep(1000)


if __name__ == "__main__":
    main()
