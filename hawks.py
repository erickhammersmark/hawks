#!/usr/bin/env python3

import disc
import math
import os
import sample
import sys
import time
from PIL import Image, ImageDraw, ImageFont, ImageColor
from threading import Timer
from urllib.parse import unquote

def running_on_pi():
  return os.uname()[1] == 'raspberrypi' or os.uname()[1] == 'hawks'

if running_on_pi():
  from rgbmatrix import RGBMatrix, RGBMatrixOptions
else:
  from mock import RGBMatrix, RGBMatrixOptions

class Settings(object):
  def __init__(self, *args, **kwargs):
    for k,v in kwargs.items():
      self.set(k, v)

  def __contains__(self, name):
    return name in self.__dict__

  def set(self, name, value):
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
    self.set("bgcolor", "blue")
    self.set("outercolor", "black")
    self.set("innercolor", "green")
    self.set("font", "FreeSansBold")
    self.set("x", 0)
    self.set("y", 2)
    self.set("big", False)
    self.set("text", "12")
    self.set("textsize", 27)
    self.set("thickness", 1)
    self.set("animation", "")
    self.set("amplitude", 0.4)
    self.set("fps", 16)
    self.set("period", 2000)
    self.set("file", "none")
    self.set("mock_square", False)
    self.set("autosize", True)
    self.set("margin", 1)
    self.set("brightness", 255)
    self.set("capture", 0)
    self.set("tempfile", "tmp.png")
    self.set("capturefile", "image.png")
    self.set("disc", False)
    self.set("brightness", 255)


class AnimState(Settings):
  def __init__(self):
    self.set("animation", None)
    self.set("start_time", None)
    self.set("period", None)
    self.set("next_updat_time", None)


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
    self.capture_image = False
    self.image_filename = "tmp.png"
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
      #self.dots = dotstar.DotStar(board.SCK, board.MOSI, 255, auto_write=True)

    self.init_matrix()

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
      if count % 32 == 0:
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
    Map image of size 64x64 to fit a 32x128 display

    rows = 64
    cols = 64
    panel_rows = 32
    panel_cols = 128

    Build a new Image of panel_rows x panel_cols
    put first panel_rows rows of original image in to new image,
    repeat with next panel_rows rows of original image, but shifted cols to the right.
    '''
    rows, cols = 64, 64
    p_rows, p_cols = 32, 128
    img = Image.new("RGB", (p_cols, p_rows), "black")
    orig_data = image.getdata()
    img_data = []
    for row in range(0, p_rows):
      for col in range(0, cols):
        img_data.append(orig_data[row * cols + col])
      for col in range(cols, p_cols):
        img_data.append(orig_data[(row + p_rows - 1) * cols + col])
    img.putdata(img_data)
    self.debug_log(img)
    return img

  def brighten(self, image):
    if self.settings.brightness == 255:
      return image

    data = image.getdata()
    newdata = []
    brt = self.settings.brightness
    for pixel in data:
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
    if self.settings.brightness != 255:
      image = self.brighten(image)

    if self.settings.capture:
      image.save(os.path.join("/tmp", self.settings.tempfile))
      os.rename(os.path.join("/tmp", self.settings.tempfile), os.path.join("/tmp", self.settings.capturefile))

    if self.settings.disc:
      self.set_disc_image(image)
      return

    if self.settings.big:
      if not running_on_pi() and self.settings.mock_square:
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

  def get_image(self):
    if not os.path.exists(os.path.join("/tmp", self.settings.capturefile)):
      return None
    with open(os.path.join("/tmp", self.settings.capturefile), "rb") as CF:
      bytes = CF.read()
      return bytes

  def init_matrix(self):
    # Configuration for the matrix
    options = RGBMatrixOptions()
    options.rows = 32
    if self.settings.big:
      options.cols = 64
      options.chain_length = 2
    else:
      options.cols = 32
      options.chain_length = 1
    options.parallel = 1
    options.gpio_slowdown = 2
    options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
    if not self.settings.disc:
      self.matrix = RGBMatrix(options = options)
    if self.settings.big:
      self.set_image(Image.new("RGB", (64, 64), "black"))
    else:
      self.set_image(Image.new("RGB", (32, 32), "black"))

  def init_anim_frames(self):
    self.anim_state.frames = [self.image.copy() for n in range(0, self.anim_state.fps)]

  def shift_column(self, image, column, delta):
    rows = 32
    if self.settings.big:
      rows = 64
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
    cols = 32
    if self.settings.big:
      cols = 64
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
    rows = 32
    cols = 32
    if self.settings.big:
      rows = 64
      cols = 64

    image = Image.new("RGB", (cols, rows), self.settings.bgcolor)
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

  def measure_text(self):
    '''
    Render text and then measure the limits of where the image is not bgcolor.
    left and top measurements are not the left and top of the rendered characters
    since x and y are 0, these will represent the characters' own left and top margins
    assume these are also right and bottom margins
    '''
    image = self.render_text()
    panel_width = 32
    if self.settings.big:
      panel_width = 64
    top = panel_width
    bottom = 0
    left = panel_width
    right = 0
    bgcolor = ImageColor.getrgb(self.settings.bgcolor)
    for idx, px in enumerate(image.getdata()):
      x = idx % panel_width
      y = idx / panel_width
      if px != bgcolor:
        if x < left:
          left = x
        if x > right:
          right = x
        if y < top:
          top = y
        if y > bottom:
          bottom = y

    width = right + left
    height = bottom + top

    return (width, height, left, top)

  def autosize(self):
    '''
    autosize algorithm:
    set x and y to 0, set textsize to something small
    render text and measure width and height
    if both are less than the display width minus the margins, increase textsize and repeat
    set x and y each to half of the size of the blank pixels
    '''
    self.settings.x = 0
    self.settings.y = 0
    self.settings.textsize = 4
    if self.settings.big:
      target_size = 64 - self.settings.margin*2
    else:
      target_size = 32 - self.settings.margin*2

    width, height, left, top = self.measure_text()

    db("Target size:", target_size)
    db("Initial width and height:", width, height)

    while width < target_size and height < target_size:
      db("Width and height", width, height, "too small for target size", target_size)
      self.settings.textsize += 1
      db("textsize is now", self.settings.textsize)
      width, height, left, top = self.measure_text()
      db("new width and height:", width, height)
      if width < 0 or height < 0:
        self.settings.textsize -= 1
        width, height, left, top = self.measure_text()
        break

    if width > target_size or height > target_size:
      self.settings.textsize -= 1
      width, height, left, top = self.measure_text()

    self.settings.x = (target_size - width)/2 + self.settings.margin - 1
    self.settings.y = (target_size - height)/2 + self.settings.margin - 1
    

  def draw_text(self):
    rows = 32
    cols = 32
    if self.settings.big:
      rows = 64
      cols = 64

    if self.settings.file and self.settings.file != "none":
      image = Image.open(self.settings.file).convert("RGB")
      if not self.settings.disc:
        image = self.resize_image(image, cols, rows)
      self.set_image(image)
      return

    if self.settings.autosize:
      self.autosize()
    image = self.render_text()
    self.set_image(image)


def main():
  h = Hawks()
  h.debug = True
  h.settings.big = True
  if len(sys.argv) > 1:
    h.settings.file = sys.argv[1]
  h.draw_text()

if __name__ == '__main__':
  main()

