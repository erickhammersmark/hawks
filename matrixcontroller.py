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

    def __init__(self, frame_queue, *args, **kwargs):
        self.rows = 32
        self.cols = 32
        self.p_rows = 32
        self.p_cols = 32
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
        self.final_frames = []
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
        self.render_state = {"callback": None}
        self.rendered_frames = None
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
            final_frames are the frames that also have the hardware-specific
            changes applied, such as rendering for the dotstar disc or a chain of
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
            #return self._disc.set_image(self.dot_frames[frame_no][0])

        self.db("setting matrix image")
        self.matrix.SetImage(image)

    def render(self):
        start_time = time.time()
        # new methodology: display self.frame, ask image controller for another frame, wait, repeat
        self.db("render()")

        # If we have a frame update pending, cancel it
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # self.final_frames should contain frames already prepared for this matrix
        #if not self.final_frames:
        #    return

        # self.show() sets self.go to true, but hawks.show() will set it to false so
        # that we stop spending time drawing animations while it renders new frames.
        # This was originally implemented for a pi2 and might be unnecessary on a pi4.
        if not self.go:
            return

        # rendered_frames is a way to wedge in last-minute animations, potentially
        # expanding each frame to a sequence of frames. This is for stuff like
        # random glitches, flashes, anything that needs randomness over time.
        """
        if self.rendered_frames:
            try:
                frame = next(self.rendered_frames)
            except StopIteration:
                self.rendered_frames = None

        if not self.rendered_frames:
            if self.render_state.get("callback", None):
                self.rendered_frames = self.render_state["callback"](self.orig_frames[self.frame_no])
            else:
                # if we don't have a render callback defined, just wrap an interator around the current frame
                self.rendered_frames = iter([self.final_frames[self.frame_no]])
            frame = next(self.rendered_frames)

            # adjust frame_no for the next time we render() on an empty set of self.rendered_frames
            self.frame_no += self.direction
            if self.back_and_forth:
                if self.frame_no >= len(self.final_frames):
                    self.frame_no = len(self.final_frames) - 2
                    self.direction = -1
                if self.frame_no <= 0:
                    self.frame_no = 0
                    self.direction = 1
            else:
                if self.frame_no >= len(self.final_frames):
                    self.frame_no = 0
        """

        # draw this frame on the hardware thingy (or the mock)
        self.SetFrame(self.frame)
        duration = self.frame[1]
        if self.img_ctrl:
            self.img_ctrl.render()
        if not self.frame_queue.empty():
            self.frame = self.shape_one_for_display(self.frame_queue.get())

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

        Use self.orig_frames as the source data
        Generate self.frames which are the device-agnostic expression of
        self.orig_frames + all of the applied transformations
        Generate self.final_frames which are self.frames with the
        device-specific transformations also applied.
        """

        self.db(f"show()")

        self.db("transforming frames")
        #self.final_frames = self.notransform_and_reshape(self.orig_frames)

        #self.frame_no = 0

        self.next_time = time.time()
        self.go = True
        #self.direction = 1
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
