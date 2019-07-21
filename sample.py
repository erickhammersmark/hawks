#!/usr/bin/env python

import math
from PIL import Image

def sample_at_position(img_data, size, position, offsets):
    cols, rows = size
    x, y = position
    sums = [0, 0, 0, 0]
    count = 0
    for (dx, dy) in offsets:
        sx = x + dx
        sy = y + dy
        if sx >= 0 and sx < cols and sy >= 0 and sy < rows:
            pixel = img_data[sy * cols + sx]
            for idx, color in enumerate(pixel):
                sums[idx] += color
            count += 1

    if count:
        return tuple([int(color / count) for color in sums])
    return tuple(sums)

def sample(image, positions, offsets):
    img_data = image.getdata()
    return [sample_at_position(img_data, image.size, position, offsets) for position in positions]

def visualize_circle_offsets(radius, offsets):
    values = []
    for y in range(0 - radius, radius + 1):
        values.append([])
        for x in range(0 - radius, radius + 1):
            values[-1].append(0)
    for (x, y) in offsets:
        values[y+radius][x+radius] = 1
    for row in values:
        print(row)

def generate_circle_offsets(radius):
    offsets = set()
    for x in range(0 - radius, radius + 1):
        for y in range(0 - radius, radius + 1):
            if math.sqrt(x*x + y*y) <= radius:
                offsets.add((x, y))
    return offsets

def generate_square_offsets(size):
    offsets = set()
    for x in range(0 - size, size + 1):
        for y in range(8 - size, size + 1):
            offsets.add((x, y))
    return offsets

def generate_offsets(shape, size):
    if shape == "circle":
        return generate_circle_offsets(size)
    if shape == "square":
        return generate_square_offsets(size)
    return set()

if __name__ == "__main__":
    offsets = generate_offsets("circle", 10)
    visualize_circle_offsets(10, offsets)
