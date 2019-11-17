#!/usr/bin/env python3

import disc
import io
import math
import os
import sample
import sys
import time
from PIL import Image, ImageDraw, ImageFont, ImageColor
from threading import Timer
from urllib.parse import unquote

try:
  from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:
  from mock import RGBMatrix, RGBMatrixOptions

class Settings(object):
  def __init__(self, *args, **kwargs):
    self.helptext = {}
    for k,v in kwargs.items():
      self.set(k, v)

  def __contains__(self, name):
    return name in self.__dict__

  def set(self, name, value, helptext=None):
    if helptext:
      self.helptext[name] = helptext
    existing = self.get(name)
    if type(existing) == int:
      try:
        value = int(value)
      except:
        pass
    elif type(existing) == float:
      try:
        value = float(value)
      except:
        pass
    setattr(self, name, value)

  def get(self, name):
    if name in self.__dict__:
      return self.__dict__[name]
    return None

DEBUG = False
def db(*args):
  if DEBUG:
    sys.stderr.write(' '.join([str(arg) for arg in args]) + '\n')


class HawksSettings(Settings):
  def __init__(self):
    super().__init__(self)
    self.set("bgcolor", "blue", helptext="Background color when rendering text")
    self.set("outercolor", "black", helptext="Outer color of rendered text")
    self.set("innercolor", "green", helptext="Inner color of rendered text")
    self.set("font", "FreeSansBold", helptext="Font to use when rendering text")
    self.set("x", 0)
    self.set("y", 0)
    self.set("rows", 32, helptext="Image height")
    self.set("cols", 32, helptext="Image width")
    self.set("decompose", False, helptext="Display is a chain of two 64x32 RGB LED matrices arranged to form a big square")
    self.set("text", "12", helptext="Text to render (if file is \"none\")")
    self.set("textsize", 27)
    self.set("thickness", 1, helptext="Thickness of outercolor border around text")
    self.set("animation", "none", helptext="Options are \"waving\" or \"none\"")
    self.set("amplitude", 0.4, helptext="Amplitude of waving animation")
    self.set("fps", 16, helptext="FPS of waving animation")
    self.set("period", 2000, helptext="Period of waving animation")
    self.set("file", "none", helptext="Image file to display (or \"none\")")
    self.set("file_path", "img", helptext="Directory in which to find files")
    self.set("autosize", True)
    self.set("margin", 2, helptext="Margin of background color around text")
    self.set("brightness", 255, helptext="Image brighness, full bright = 255")
    self.set("disc", False, helptext="Display is a 255-element DotStar disc")
    self.set("transpose", "none", helptext="PIL transpose operations are supported")
    self.set("rotate", 0, helptext="Rotation in degrees")
    self.set("mock", False, helptext="Display is mock rgbmatrix")
    self.set("mode", "text", helptext="Valid modes are 'text', 'file', and 'network_weather'")


class AnimState(Settings):
  def __init__(self):
    self.set("animation", None)
    self.set("start_time", None)
    self.set("period", None)
    self.set("next_update_time", None)


class Hawks(object):
  PRESETS = {
      "dark": {"bgcolor": "black", "innercolor": "blue", "outercolor": "green"},
      "bright": {"bgcolor": "blue", "innercolor": "black", "outercolor": "green"},
      "blue_on_green": {"bgcolor": "green", "innercolor": "blue", "outercolor": "black"},
      "green_on_blue": {"bgcolor": "blue", "innercolor": "green", "outercolor": "black"},
      "christmas": {"bgcolor": "green", "innercolor": "red", "outercolor": "black", "text": "12", "textsize": 27, "x": 0, "y": 2, "animation": "none", "thickness": 1},
      "none": {},
  }

  ANIMATIONS = [ "waving" ]

  def __init__(self, *args, **kwargs):
    self.settings = HawksSettings()
    self.port = 1212
    self.debug = False
    self.timer = None
    self.dots = None

    preset = None

    for k,v in kwargs.items():
      if k in self.settings:
        self.settings.set(k, v)
      elif k == "preset":
        preset = v
      else:
        setattr(self, k, v)

    if self.settings.disc:
      import board
      import adafruit_dotstar as dotstar
      self.dots = dotstar.DotStar(board.SCK, board.MOSI, 255, auto_write=False)

    if self.settings.mock:
      from mock import RGBMatrix, RGBMatrixOptions

    self.init_matrix()

    self.network_weather_image = Image.new("RGB", (self.settings.cols, self.settings.rows), "black")

    #
    # on a 32x32 6mm pitch LED matrix
    # if you happen to have a 5 7/8" wide Google Cloud Platform plexiglass logo
    # if you center it horizontally and align its top with the top of the panel
    # these are the lights that it will cover.
    #
    # no one else will use this EVER
    #
    self.gcp_logo_pixels = [
                                                      14, 15, 16, 17,

                                          43, 44, 45, 46, 47, 48, 49, 50, 51, 52,

                                     74,  75,  76,  77,  78,  79,  80,  81,  82,  83,  84,  85,

                               105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118,

                          136, 137, 138, 139, 140, 141,                          147, 148, 149, 150, 151,

                          168, 169, 170, 171,                                              181, 182, 183, 184,

                     199, 200, 201, 202, 203, 204,                                         213, 214, 215, 216,

                230, 231, 232, 233, 234, 235, 236, 237, 238,                               245, 246, 247, 248,

                262, 263, 264, 265, 266, 267, 268, 269, 270, 271,                               278, 279, 280, 281,

           293, 294, 295, 296, 297, 298, 299, 300, 301, 302,                                    310, 311, 312, 313, 314,

      324, 325, 326, 327, 328,                     332, 333,                                         343, 344, 345, 346, 347,

      356, 357, 358, 359,                                                                                 376, 377, 378, 379,

      388, 389, 390, 391,                                                                                 408, 409, 410, 411,

      420, 421, 422, 423,                                                                                 440, 441, 442, 443,

      452, 453, 454, 455,                                                                                 472, 473, 474, 475,

      484, 485, 486, 487, 488,                                                                       503, 504, 505, 506, 507,

           517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 533, 534, 535, 536, 537, 538,

                550, 551, 552, 553, 554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569,

                     583, 584, 585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596, 597, 598, 599, 600,

                               617, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627, 628, 629, 630
    ]

    if preset:
      self.apply_preset(preset)

  def debug_log(self, obj):
    if self.debug:
      sys.stderr.write(str(obj) + "\n")

  def text_as_color(self, text, rgb):
    '''
    Return string with text prefixed by ANSI escape
    code to set the backgorund to the color specified
    by 'rgb' (a tuple of r, g, b bytes).  The string
    also include the escape sequence to set the terminal
    back to its default colors.
    '''
    escape_seq = '\033[48;2;{0};{1};{2}m{3}\033[10;m'
    r, g, b = rgb
    return escape_seq.format(r, g, b, text)

  def print_image(self, image):
    #\033[38;2;255;82;197;48;2;155;106;0mHello
    count = 0
    print
    for px in image.getdata():
      sys.stdout.write(self.text_as_color('  ', px))
      count += 1
      if count % self.settings.cols == 0:
        print
    print

  def transform(self, image, func):
    img = Image.new("RGB", image.size, "black")
    orig_data = image.getdata()
    img_data = [func(p) for p in orig_data]
    img.putdata(img_data)
    return img

  def reshape(self, image):
    '''
    Map image of size rows x cols to fit a
    rows/2 x cols*2 display. For example:

    rows = 64
    cols = 64
    panel_rows = 32
    panel_cols = 128

    Build a new Image of panel_rows x panel_cols,
    put first panel_rows rows of original image
    in to new image, repeat with next panel_rows
    rows of original image, but shifted cols to
    the right.
    '''

    rows, cols = self.settings.rows, self.settings.cols
    p_rows, p_cols = int(rows/2), cols * 2
    img = Image.new("RGB", (p_cols, p_rows), "black")
    orig_data = image.getdata()
    img_data = []
    for row in range(0, p_rows):
      r = row * cols
      for col in range(0, cols):
        img_data.append(orig_data[r + col])
      r = (row * p_rows - 1) * cols
      for col in range(cols, p_cols):
        img_data.append(orig_data[r + col])
    img.putdata(img_data)
    return img

  def brighten(self, image):
    if self.settings.brightness == 255:
      return image

    data = list(image.getdata())
    newdata = []
    brt = self.settings.brightness
    for idx, pixel in enumerate(data):
      if idx in self.gcp_logo_pixels:
        newdata.append(pixel)
      else:
        newdata.append(tuple(int(c * brt / 255) for c in pixel))
    image.putdata(newdata)
    return image

  def set_disc_image(self, image):
    self.disc = disc.Disc()
    pixels = self.disc.sample_image(image)
    for idx, pixel in enumerate(pixels):
        self.dots[idx] = pixel[0:3]
    self.dots.show()

  def SetImage(self, image):
    '''
    Use instead of matrix.SetImage
    Distinct from set_image(), which sets self.image and kicks off animations if necessary.
    This does live last-second post-processing before calling matrix.SetImage
    '''
    if self.settings.disc:
      self.set_disc_image(image)
      return

    if self.settings.decompose:
      if self.settings.mock:
        setattr(self.matrix, "mock_square", True)
        self.matrix.SetImage(image)
      else:
        self.matrix.SetImage(self.reshape(image))
    else:
      self.matrix.SetImage(image)

  def set_image(self, image):
    self.image = image
    if self.settings.animation == "waving":
      self.waving_start()
    else:
      self.SetImage(image)

  def init_matrix(self):
    # Configuration for the matrix
    options = RGBMatrixOptions()
    options.cols = self.settings.cols
    if self.settings.decompose:
      options.rows = int(self.settings.rows / 2)
      options.chain_length = 2
    else:
      options.rows = self.settings.rows
      options.chain_length = 1
    options.parallel = 1
    options.gpio_slowdown = 2
    options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
    if not self.settings.disc:
      self.matrix = RGBMatrix(options = options)
    self.set_image(Image.new("RGB", (self.settings.cols, self.settings.rows), "black"))

  def init_anim_frames(self):
    self.anim_state.frames = [self.image.copy() for n in range(0, self.anim_state.fps)]

  def shift_column(self, image, column, delta):
    rows = self.settings.rows
    if delta == 0:
      return image
    if delta > 0:
      # positive == up
      # from 0 to rows-delta, pull from row+delta.
      # from rows-delta to rows-1, black
      for n in range(0, rows - delta):
        image.putpixel((column, n), image.getpixel((column, n + delta)))
      for n in range(rows - delta, rows):
        image.putpixel((column, n), (0, 0, 0))
    else:
      # negative == down
      # make delta positive
      # from rows-1 to delta, pull from row-delta
      # from delta to 0, black
      delta = 0 - delta
      for n in range(rows - 1, delta, -1):
        image.putpixel((column, n), image.getpixel((column, n - delta)))
      for n in range(0, delta):
        image.putpixel((column, n), (0, 0, 0))

  def frames_equal(self, one, two):
    if not one or not two:
      return False
    for o,t in zip(one.getdata(), two.getdata()):
      if o != t:
        return False
    return True

  def multiply_pixel(self, pixel, value):
    return tuple([int(c * value) for c in pixel])

  def average_anim_frames(self, group):
    '''
    group is a list of indices of self.anim_stat.frames
    The frames should represent repetitions of the first image
    and one instnace of the next image, a set of duplicate
    frames and one instance of what the next frame will be.  This
    method should leave the first and last frames untouched and
    replace each of the intermediate frames with a combination of the two.
    '''

    if not group:
      return
    num_frames = len(group)
    if num_frames <= 2:
      return
    num_frames -= 1

    saf = self.anim_state.frames
    # we can redo this to only fetch the first and last.  we compute the ones in the middle.
    group_data = [saf[n].getdata() for n in group]
    new_data = [[] for n in group]
    num_pixels = len(list(group_data[0]))

    for pixel_no in range(0, num_pixels):
      first = group_data[0][pixel_no]
      last = group_data[-1][pixel_no]
      for idx, frame_no in enumerate(group):
        left = self.multiply_pixel(
            group_data[0][pixel_no],
            float(num_frames - idx) / num_frames)
        right = self.multiply_pixel(
            group_data[-1][pixel_no],
            float(idx) / num_frames)
        new_data[idx].append(tuple([l + r for l, r in zip(left, right)]))
    for idx, frame_no in enumerate(group):
      if idx == 0 or idx == num_frames:
        continue
      saf[frame_no].putdata(new_data[idx])

  def waving_setup(self):
    if self.timer:
      self.timer.cancel()
    cols = self.settings.cols
    self.init_anim_frames()
    saf = self.anim_state.frames
    self.anim_state.set("ms_per_frame", self.settings.period / self.anim_state.fps)
    wavelength_radians = math.pi * 2.0
    phase_step_per_frame = wavelength_radians / self.anim_state.fps
    radians_per_pixel = wavelength_radians / cols
    phase = 0.0
    amplitude = self.settings.amplitude
    # first pass
    for n in range(0, self.anim_state.fps):
      for c in range(0, cols):
        radians = radians_per_pixel * c + phase
        delta_y = int(round((math.sin(radians) * amplitude) / radians_per_pixel)) # assumes rows == cols!
        self.shift_column(saf[n], c, delta_y)
      phase -= phase_step_per_frame
    # second pass
    group = []
    for n in range(0, self.anim_state.fps):
      group.append(n)
      if not self.frames_equal(saf[group[0]], saf[n]):
        self.average_anim_frames(group)
        group = [n]
    self.anim_state.set("frame_no", 0)

  def waving_do(self):
    print("waving_do at {0}".format(time.time()))
    if self.settings.animation == "waving" and time.time()*1000 >= self.anim_state.next_update_time:
      print("waving_do {0} is later than {1}".format(time.time()*1000, self.anim_state.next_update_time))
      self.anim_state.next_update_time += self.anim_state.ms_per_frame
      self.SetImage(self.anim_state.frames[self.anim_state.frame_no])
      self.anim_state.frame_no += 1
      if self.anim_state.frame_no >= len(self.anim_state.frames):
        self.anim_state.frame_no = 0
      print("setting timer for {0} seconds".format(self.anim_state.ms_per_frame / 1000.0))
      if self.timer:
        self.timer.cancel()
      self.timer = Timer(self.anim_state.ms_per_frame / 1000.0, self.waving_do)
      self.timer.start()

  def waving_start(self):
    setattr(self, "anim_state", AnimState())
    self.anim_state.set("start_time", time.time()*1000)
    self.anim_state.set("next_update_time", self.anim_state.start_time)
    self.anim_state.set("fps", self.settings.fps)
    self.waving_setup()
    self.waving_do()

  def resize_image(self, image, cols, rows):
    orig_c, orig_r = image.size
    new_c, new_r = cols, rows
    if orig_c > orig_r:
      new_r = new_r * float(orig_r) / orig_c
    elif orig_r > orig_c:
      new_c = new_c * float(orig_c) / orig_r
    return image.resize((int(new_c), int(new_r)))

  def apply_preset(self, preset):
    if preset in Hawks.PRESETS:
      for k,v in Hawks.PRESETS[preset].items():
        self.settings.set(k, v)
      self.draw_text()
      return True
    return False

  def render_text(self):
    image = Image.new("RGB", (self.settings.cols, self.settings.rows), self.settings.bgcolor)
    draw = ImageDraw.Draw(image)
    text = unquote(self.settings.text.upper())
    font = ImageFont.truetype(self.settings.font, self.settings.textsize)

    (x, y) = (self.settings.x, self.settings.y)

    for dx in range(0 - self.settings.thickness, self.settings.thickness + 1):
      for dy in range(0 - self.settings.thickness, self.settings.thickness + 1):
        draw.text((x-dx, y-dy), text, fill=self.settings.outercolor, font=font)
        draw.text((x+dx, y-dy), text, fill=self.settings.outercolor, font=font)
        draw.text((x-dx, y+dy), text, fill=self.settings.outercolor, font=font)
        draw.text((x+dx, y+dy), text, fill=self.settings.outercolor, font=font)

    draw.text((x, y), text, fill=self.settings.innercolor, font=font)

    return image

  def col_only_bgcolor(self, image_data, col):
    if col < 0 or col >= self.settings.cols:
      raise Exception("Column {0} is out of bounds (0, {1})".format(col, self.settings.cols))

    bgcolor = ImageColor.getrgb(self.settings.bgcolor)
    px_no = col
    while px_no < len(image_data):
      if image_data[px_no] != bgcolor:
        return False
      px_no += self.settings.cols
    return True

  def row_only_bgcolor(self, image_data, row):
    if row < 0 or row >= self.settings.rows:
      raise Exception("Column {0} is out of bounds (0, {1})".format(row, self.settings.rows))

    bgcolor = ImageColor.getrgb(self.settings.bgcolor)
    px_no = row * self.settings.cols
    while px_no < (row + 1) * self.settings.cols and px_no < len(image_data):
      if image_data[px_no] != bgcolor:
        return False
      px_no += 1
    return True

  def measure_left_margin(self, image_data):
    col = 0
    while col < self.settings.cols and self.col_only_bgcolor(image_data, col):
      col += 1
    return col

  def measure_right_margin(self, image_data):
    col = self.settings.cols - 1
    while col >= 0 and self.col_only_bgcolor(image_data, col):
      col -= 1
    return self.settings.cols - col - 1

  def measure_top_margin(self, image_data):
    row = 0
    while row < self.settings.rows and self.row_only_bgcolor(image_data, row):
      row += 1
    return row

  def measure_bottom_margin(self, image_data):
    row = self.settings.rows - 1
    while row >= 0 and self.row_only_bgcolor(image_data, row):
      row -= 1
    return self.settings.rows - row - 1

  def align_and_measure(self):
    image_data = self.render_text().getdata()

    left_margin = self.measure_left_margin(image_data)
    self.settings.x += self.settings.margin - left_margin

    top_margin = self.measure_top_margin(image_data)
    self.settings.y += self.settings.margin - top_margin

    if self.settings.margin != left_margin or self.settings.margin != top_margin:
      image = self.render_text()
      image_data = image.getdata()
    
    left_margin = self.measure_left_margin(image_data)
    top_margin = self.measure_top_margin(image_data)
    right_margin = self.measure_right_margin(image_data)
    bottom_margin = self.measure_bottom_margin(image_data)

    return (left_margin, right_margin, top_margin, bottom_margin)

  def autosize(self):
    self.settings.x = 0
    self.settings.y = 0
    self.settings.textsize = 10

    left_margin, right_margin, top_margin, bottom_margin = self.align_and_measure()

    # make the text big enough
    while right_margin > self.settings.margin and bottom_margin > self.settings.margin:
      self.settings.textsize += min(right_margin, bottom_margin)
      left_margin, right_margin, top_margin, bottom_margin = self.align_and_measure()

    # make sure it is not too big
    while right_margin < self.settings.margin or bottom_margin < self.settings.margin:
      self.settings.textsize -= 1
      left_margin, right_margin, top_margin, bottom_margin = self.align_and_measure()

    # center the text in both dimensions
    self.settings.x += int((right_margin - left_margin) / 2)
    self.settings.y += int((bottom_margin - top_margin) / 2)

  def mirror_x(self, pixel_no):
    x_pos = pixel_no % self.settings.cols
    new_x_pos = self.settings.cols - x_pos
    delta_x = new_x_pos - x_pos - 1
    return pixel_no + delta_x

  def network_weather(self):
    #not_gcp_logo_pixels = [p for p in range(0, 1023) if p not in gcp_logo_pixels]

    self.network_color = "red"
    img = Image.new("RGB", (self.settings.cols, self.settings.rows), self.network_color)
    img_data = list(img.getdata())
    for p in self.gcp_logo_pixels:
      img_data[p] = (255, 255, 255)
    
    self.network_weather_image.putdata(img_data)
    return self.network_weather_image

  def make_png(self, image):
    with io.BytesIO() as output:
      image.save(output, format="PNG")
      return output.getvalue()

  def draw_text(self, return_image=False):
    if self.settings.mode == "file" and self.settings.file != "none":
      image = Image.open(os.path.join(self.settings.file_path, self.settings.file)).convert("RGB")
      if not self.settings.disc:
        image = self.resize_image(image, self.settings.cols, self.settings.rows)
    elif self.settings.mode == "network_weather":
        image = self.network_weather()
    else:
      if self.settings.autosize:
        self.autosize()
      image = self.render_text()

    if self.settings.brightness != 255:
      image = self.brighten(image)

    if self.settings.transpose != "none":
      operation = getattr(Image, self.settings.transpose, None)
      if operation != None:
        image = image.transpose(operation)

    if self.settings.rotate != 0:
      image = image.rotate(self.settings.rotate)

    if return_image:
      return self.make_png(image)
    self.set_image(image)


def main():
  h = Hawks()
  h.debug = True
  h.settings.decompose = True
  if len(sys.argv) > 1:
    h.settings.file = sys.argv[1]
  h.draw_text()

if __name__ == '__main__':
  main()

