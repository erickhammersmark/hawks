#!/usr/bin/env python3

import math
import time
from base import Base
from PIL import Image
from queue import Queue
from threading import Timer


class MatrixController(Base):
    """
    Implements an RGB Matrix and Dotstar Disc controller
    """

    def __init__(self, frame_queue, settings):
        self.frame_queue = frame_queue
        self.settings = settings

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
        self.nodisplay = False
        self.img_ctrl = None
        self.row_address_type = 0

        for (k, v) in self.settings:
            setattr(self, k, v)

        self.blank = Image.new("RGB", (self.cols, self.rows), "black")
        self.frame = (self.blank, 0)

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
                try:
                    from rgbmatrix import RGBMatrix, RGBMatrixOptions
                except ModuleNotFoundError:
                    self.mock = True
                    print("module 'rgbmatrix' not found, using mock instead")
                    from mock import RGBMatrix, RGBMatrixOptions

            options = RGBMatrixOptions()
            options.row_address_type = self.row_address_type

            m_rows = self.rows
            m_cols = self.cols

            options.chain_length = 1
            if self.decompose:
                options.chain_length = 2
                if not self.p_rows or self.p_rows == self.rows:
                    self.p_rows = int(self.rows / 2)
                    self.p_cols = int(2 * self.cols)
                m_cols = self.cols
                m_rows = self.p_rows

            options.cols = m_cols
            options.rows = m_rows
            options.parallel = 1
            options.gpio_slowdown = 4
            options.hardware_mapping = (
                "adafruit-hat"  # If you have an Adafruit HAT: "adafruit-hat" or "adafruit-hat-pwm"
                                    # https://github.com/hzeller/rpi-rgb-led-matrix#troubleshooting
            )
            print(options.cols, options.rows, options.chain_length)
            self.matrix = RGBMatrix(options=options)

        self.show()

    def set_img_ctrl(self, img_ctrl):
        self.img_ctrl = img_ctrl

    def set_image(self, image):
        self.stop()
        if self.img_ctrl:
            self.img_ctrl.stop()
            self.img_ctrl = None
        while not self.frame_queue.empty():
            self.frame_queue.get()
        self.frame_queue.put((image, 0))
        self.show()

    def reshape(self, image):
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
        p_rows, p_cols = self.p_rows, self.p_cols

        if rows * cols != p_rows * p_cols:
            rows -= rows % p_rows
            cols -= p_cols % cols

        img = Image.new("RGB", (p_cols, p_rows), "black")
        orig_data = list(image.getdata())

        n_panels = int(rows / p_rows)
        if n_panels == 1:
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

            Consider some kind of cache for this.

            Doing this in real time for a decomposed matrix is fine, with
            a fast enough pi. On the pi zero I use to run my Dotstar disc,
            doing the sampling in real time will be very slow. Caching may
            be enough for a repeating animation, but it will not help for
            a continuously generated visualization.
        """
        if self.disc:
            if type(frame[0]) == list:
                # if the frame is already a list of pixels specifically
                # for the disc, just keep it.
                return frame
            return (self._disc.sample_image(frame[0]), frame[1])
        else:
            if self.decompose:
                if self.mock:
                    return frame
                else:
                    return (self.reshape(frame[0]), frame[1])
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
        if self.nodisplay:
            return

        if self.disc:
            self.db("setting disc image")
            return self._disc.set_image(image)

        self.db("setting matrix image")
        self.matrix.SetImage(image)

    def render(self):
        self.db("render()")

        # If we have a frame update pending, cancel it
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # self.show() sets self.go to true, but hawks.show() will set it to false so
        # that we stop spending time drawing animations while it renders new frames.
        # Also used by hawks.show() to make this ImageController exit so a new one
        # can be the only thing writing to the frame queue.
        if not self.go:
            return

        # draw this frame on the hardware thingy (or the mock)
        if self.frame and self.frame_queue.empty():
            # we were showing something and have nothing: leave it up for another duration ms
            pass
        elif not self.frame_queue.empty():
            # it's time for a new one and there's something in the queue. get it.
            self.frame = self.shape_one_for_display(self.frame_queue.get())
        if not self.frame:
            # if it's time for a new frame and we don't have one at all,
            # blank for 100ms, then try again
            self.frame=(self.blank, 100)

        self.SetFrame(self.frame)

        duration = self.frame[1]

        if duration:
            # duration is in ms
            self.next_time = self.next_time + duration / 1000.0
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
        if getattr(self, "timer", None):
            self.timer.cancel()

    def start(self):
        """
        Resume displaying new frames.
        """
        self.go = True


def main():
    frame_queue = Queue()
    ctrl = MatrixController(frame_queue, (("rows", 128), ("cols", 128), ("p_cols", 128), ("p_rows", 64), ("decompose", True)))
    ctrl.set_image(Image.open("img/hawks.png").convert("RGB"))
    while True:
        time.sleep(1000)


if __name__ == "__main__":
    main()
