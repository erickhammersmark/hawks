#!/usr/bin/env python3

import io
import sys
import time
from base import Base
from math import pi, sin
from PIL import Image
from random import randint, choice
from threading import Timer


class MatrixController(Base):
    """
    Implements an RGB Matrix and Dotstar Disc controller
    """

    settings = [
        "rows",
        "cols",
        "p_rows",
        "p_cols",
        "decompose",
        "disc",
        "mock",
        "debug",
    ]

    def __init__(self, frame_queue, *args, **kwargs):
        self.rows = 32
        self.cols = 32
        self.p_rows = 32
        self.p_cols = 32
        self.decompose = False
        self.disc = False
        self._disc = None
        self.mock = False
        self.debug = False
        self.frames = []
        self.dot_frames = []
        self.next_time = 0
        self.timer = None
        self.go = True
        self.blank = Image.new("RGB", (self.cols, self.rows), "black")
        self.frame_queue = frame_queue
        self.frame = (self.blank, 0)
        self.img_ctrl = None

        for (k, v) in kwargs.items():
            setattr(self, k, v)

        self.init_matrix()

    def init_matrix(self):
        """
        The Matrix has you
        """

        self.db("Initializing matrix")

        if self.disc:
            import disc
            self._disc = disc.Disc(mock=self.mock)
            self.dot_frames = [(self._disc.sample_image(self.blank), 0)]
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
            options.gpio_slowdown = 4
            options.hardware_mapping = (
                "adafruit-hat"  # If you have an Adafruit HAT: "adafruit-hat" or "adafruit-hat-pwm"
                                    # https://github.com/hzeller/rpi-rgb-led-matrix#troubleshooting
            )
            self.matrix = RGBMatrix(options=options)

        self.show()

    def set_img_ctrl(self, img_ctrl):
        self.img_ctrl = img_ctrl

    def reshape(self, image, p_rows=32, p_cols=128):
        """
        Map image of size self.rows x self.cols to fit a
        p_rows x p_cols display. For example:

        rows = 64           AAAAAAAA  |-->
        cols = 96           AAAAAAAA  |-->  AAAAAAAABBBBBBBBCCCCCCCC
        panel_rows = 32     AAAAAAAA  |-->  AAAAAAAABBBBBBBBCCCCCCCC
        panel_cols = 192    BBBBBBBB  |-->  AAAAAAAABBBBBBBBCCCCCCCC
                            BBBBBBBB  |-->
                            BBBBBBBB  |-->
                            CCCCCCCC  |-->
                            CCCCCCCC  |-->
                            CCCCCCCC  |-->

        Build a new Image of panel_rows x panel_cols.
        """

        rows, cols = self.rows, self.cols

        if rows * cols != p_rows * p_cols:
            rows -= rows % p_rows
            cols -= p_cols % cols

        img = Image.new("RGB", (p_cols, p_rows), "black")
        orig_data = list(image.getdata())

        n_panels = int(rows / p_rows)
        if n_panels < 2:
            img.putdata(orig_data)
            return img

        img_data = []
        for row in range(0, p_rows):
            for panel_no in range(0, n_panels):
                r = row * cols + cols * p_rows * panel_no
                img_data.extend(orig_data[r:r+cols])
        img.putdata(img_data[:p_cols*p_rows])
        return img

    def shape_one_for_display(self, frame):
        """
            apply the hardware-specific changes to one frame,
            such as rendering for the dotstar disc or a chain of
            LED matrix panels.
        """
        if self.disc:
            return (self._disc.sample_image(frame[0]), frame[1])
        else:
            if self.decompose:
                if self.mock:
                    return frame
                else:
                    return (self.reshape(frame[0], p_rows=self.p_rows, p_cols=self.p_cols), frame[1])
            return frame

    def shape_for_display(self, frames):
        if self.disc:
            self.db("Sampling frames for disc")
        return [self.shape_one_for_display(frame) for frame in frames]

    def SetFrame(self, frame):
        """
        Use instead of matrix.SetImage
        This will write to the disc or to an rgb matrix
        Input is a tuple where the first element is an Image
        """
        self.db(f"SetFrame({frame})")
        image = frame[0]

        if self.disc:
            self.db("setting disc image")
            return self._disc.set_image(image)

        self.db("setting matrix image")
        self.matrix.SetImage(image)

    def update_frame(self):
        if self.img_ctrl:
            self.img_ctrl.render()
        if not self.frame_queue.empty():
            self.frame = self.shape_one_for_display(self.frame_queue.get())

    def render(self):
        # new methodology: display self.frame, ask image controller for another frame, wait, repeat
        start_time = time.time()
        self.db("render()")

        # If we have a frame update pending, cancel it
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # self.show() sets self.go to true, but hawks.show() will set it to false so
        # that we stop spending time drawing animations while it renders new frames.
        # This was originally implemented for a pi2 and might be unnecessary on a pi4.
        if not self.go:
            return

        # draw this frame on the hardware thingy (or the mock)
        if not self.frame:
            self.frame=(self.blank, 0)
            self.update_frame()
        self.SetFrame(self.frame)

        duration = self.frame[1]

        self.update_frame()

        if duration:
            # duration is in ms
            self.next_time = start_time + duration / 1000.0
            frame_interval = self.next_time - time.time()
            self.timer = Timer(frame_interval, self.render)
            self.timer.start()

    def show(self):
        """
        This is called every time something changes, like run_sign starting or
        a settings change via the API.  This is what the API calls to ensure
        that the changes it just set are acted upon.
        """

        self.db(f"show()")

        self.db("transforming frames")

        self.next_time = time.time()
        self.frame = None
        self.go = True
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
