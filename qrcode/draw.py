from functools import partial
from typing import Callable, Dict, List, Literal, Tuple, TypeAlias

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

import qrcode.reedsolomon as rs
from qrcode.encode import encode
from qrcode.custom_types import CoordinateValueMap, ECL
from qrcode.utils import convert_to_grid_size, convert_to_version, get_mask_penalty_points, get_masks

"""
TODO:

next: Draw format information and then calculate mask penalty points on the entire grid.

- Format information - DONE
- Mask penalty points - NEXT
- Use bytearray instead of strings?
"""

WHITE = 0
BLACK = 1
DEFAULT_VALUE = -1
DUMMY_VALUE = -2


def get_empty_grid(size: int = 21):
    grid = np.zeros((size, size))
    return grid


def get_timing_pattern(grid_size: int = 21) -> CoordinateValueMap:
    fixed_row, fixed_col = 6, 6
    timing_pattern_row_black = {(fixed_row, x): BLACK for x in range(0, grid_size, 2)}
    timing_pattern_row_white = {(fixed_row, x): WHITE for x in range(1, grid_size, 2)}
    timing_pattern_col_black = {(x, fixed_col): BLACK for x in range(0, grid_size, 2)}
    timing_pattern_col_white = {(x, fixed_col): WHITE for x in range(1, grid_size, 2)}
    result: CoordinateValueMap = {
        **timing_pattern_row_black,
        **timing_pattern_row_white,
        **timing_pattern_col_black,
        **timing_pattern_col_white,
    }
    return result


def create_row(fixed_row_index, col_start, col_end, value):
    return {(fixed_row_index, col): value for col in range(col_start, col_end)}


def create_col(fixed_col_index, row_start, row_end, value):
    return {(row, fixed_col_index): value for row in range(row_start, row_end)}


def finder_pattern_generator(row, col, grid_size) -> CoordinateValueMap:
    result = {}
    for r in range(-1, 8):
        if row + r <= -1 or grid_size <= row + r:
            continue

        for c in range(-1, 8):
            if col + c <= -1 or grid_size <= col + c:
                continue

            if (0 <= r <= 6 and c in {0, 6}) or (0 <= c <= 6 and r in {0, 6}) or (2 <= r <= 4 and 2 <= c <= 4):
                result[(row + r, col + c)] = BLACK
            else:
                result[(row + r, col + c)] = WHITE
    return result


def get_finder_patterns(
    finder_pattern_generator: Callable[[int, int, int], CoordinateValueMap], grid_size
) -> CoordinateValueMap:
    top_left = finder_pattern_generator(0, 0, grid_size)
    bottom_left = finder_pattern_generator(grid_size - 7, 0, grid_size)
    top_right = finder_pattern_generator(0, grid_size - 7, grid_size)
    return {**top_left, **bottom_left, **top_right}


def get_seperator_pattern(grid_size) -> CoordinateValueMap:
    length = 8
    length_index = length - 1

    create_white_row = partial(create_row, value=WHITE)
    create_white_col = partial(create_col, value=WHITE)

    top_left_row = create_white_row(fixed_row_index=length_index, col_start=0, col_end=length)
    top_left_col = create_white_col(fixed_col_index=length_index, row_start=0, row_end=length)

    top_right_row = create_white_row(fixed_row_index=length_index, col_start=grid_size - length, col_end=grid_size)
    top_right_col = create_white_col(fixed_col_index=grid_size - length, row_start=0, row_end=length)

    bottom_right_row = create_white_row(fixed_row_index=grid_size - length, col_start=0, col_end=length)
    bottom_right_col = create_white_col(fixed_col_index=length_index, row_start=grid_size - length, row_end=grid_size)

    result = {**top_left_row, **top_left_col, **top_right_row, **top_right_col, **bottom_right_row, **bottom_right_col}
    return result


def add_quiet_zone(grid):
    horizontal_zone = np.zeros((grid.shape[0], 1))
    grid = np.hstack((grid, horizontal_zone))
    grid = np.hstack((horizontal_zone, grid))

    vertical_zone = np.zeros((1, grid.shape[1]))
    grid = np.vstack((grid, vertical_zone))
    grid = np.vstack((vertical_zone, grid))

    return grid


def override_grid(grid, indexes: Dict[tuple, int]):
    for index, value in indexes.items():
        i, j = index
        grid[i][j] = value
    return grid


def draw_grid_with_pil(grid: np.ndarray, cell_size: int = 20):
    """
    Draw a grid using PIL based on a 2D numpy array.

    Parameters:
    - grid: A 2D numpy array of shape (n, n) containing 0, 1, -1, -2.
    - cell_size: The size of each cell in the grid in pixels.
    """

    # Validate the shape of the grid
    if grid.shape[0] != grid.shape[1]:
        raise ValueError("The input grid must be square (n x n).")

    # Initialize an image object with white background
    img_size = grid.shape[0] * cell_size
    img = Image.new("RGB", (img_size, img_size), "lightgray")
    draw = ImageDraw.Draw(img)

    color_map = {WHITE: "white", BLACK: "black", DEFAULT_VALUE: "lightgray", DUMMY_VALUE: "darkgray"}

    for i in range(grid.shape[0]):  # Rows
        for j in range(grid.shape[1]):  # Columns
            x0, y0 = j * cell_size, i * cell_size  # Corrected here
            x1, y1 = x0 + cell_size, y0 + cell_size
            cell_value = grid[i, j]
            cell_color = color_map.get(cell_value, "white")
            draw.rectangle(((x0, y0), (x1, y1)), fill=cell_color, outline="black")

    img.show()


def iterate_over_grid(grid_size) -> List[Tuple[int, int]]:
    """Iterates over all grid cells in zig-zag pattern and returns an iterator of tuples (row, col)."""
    result = []
    up = True
    for column in range(grid_size - 1, 0, -2):
        if column <= 6:  # skip column 6 because of timing pattern
            column -= 1

        if up:
            row = 20
        else:
            row = 0

        for _ in range(grid_size):
            for col in (column, column - 1):
                result.append((row, col))
            if up:
                row -= 1
            else:
                row += 1
        if up:
            up = False
        else:
            up = True
    return result


def get_codeword_placement(binary_str, grid, grid_iterator) -> CoordinateValueMap:
    result = {}
    for row, col in grid_iterator:
        if not binary_str:
            break
        if grid[row][col] == -1:
            result[(row, col)] = binary_str[0]
            binary_str = binary_str[1:]
        else:
            continue
    return result


def get_format_information(ecl: ECL, mask_reference: int) -> int:
    ecl_binary_indicator_map = {ECL.L: 1, ECL.M: 0, ECL.Q: 3, ECL.H: 2}
    genpoly = [1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 1]
    mask = 21522

    ecl_binary_indicator = ecl_binary_indicator_map[ecl]
    data = ecl_binary_indicator << 3 | mask_reference
    data_binary_str: str = f"{data:05b}"
    data_list = [int(x) for x in data_binary_str]

    format_info = rs.encode(data_list, ecclen=10, genpoly=genpoly)
    format_info = int("".join(map(str, format_info)), 2)
    result = format_info ^ mask
    return result


def get_dummy_format_information(grid_size) -> CoordinateValueMap:
    result = {}
    for col in range(grid_size):
        if (col <= 7) or (col >= grid_size - 8):
            result[(row := 8, col)] = DUMMY_VALUE

    for row in range(grid_size):
        if row <= 8 or row >= grid_size - 8:
            result[(row, col := 8)] = DUMMY_VALUE

    result[(grid_size - 8, 8)] = BLACK
    return result


def apply_mask(mask: Callable, data: CoordinateValueMap) -> CoordinateValueMap:
    result = {}
    for coordinate, value in data.items():
        i, j = coordinate
        result[(i, j)] = mask(i, j) ^ int(value)  # int(value) may not be needed if value already int
    return result


def get_version_information(version: int) -> CoordinateValueMap:
    if version <= 6:
        return {}
    else:
        # TODO: TO BE IMPLEMENTED - it should return non-empty dict.
        raise NotImplementedError("Currently only versions below 7 are supported.")


def draw(binary_string: str, version: int, error_correction_level: ECL):
    grid_size = convert_to_grid_size(version)

    version_information = get_version_information(version)

    dummy_format_information = get_dummy_format_information(grid_size)
    finder_patterns = get_finder_patterns(finder_pattern_generator, grid_size)
    seperator_pattern = get_seperator_pattern(grid_size)
    timing_pattern = get_timing_pattern(grid_size)

    grid = np.full((grid_size, grid_size), -1, dtype=int)

    grid = override_grid(grid, dummy_format_information)
    grid = override_grid(grid, timing_pattern)
    grid = override_grid(grid, finder_patterns)
    grid = override_grid(grid, seperator_pattern)
    grid = override_grid(grid, version_information)

    grid_iterator = iterate_over_grid(grid_size)
    codeword_placement = get_codeword_placement(binary_string, grid, grid_iterator)
    grid = override_grid(grid, codeword_placement)

    masks = get_masks()
    best_mask_ref, lowest_penalty_points = (0, 100_000)  # arbitrary large number
    for mask_reference, mask in enumerate(masks):
        masked_codewords = apply_mask(mask, codeword_placement)
        masked_grid = override_grid(grid, masked_codewords)

        format_information = get_format_information(error_correction_level, mask_reference)

        continue
        # grid = override_grid(format_information)

        points = get_mask_penalty_points(masked_grid)
        if points < lowest_penalty_points:
            best_mask_ref, lowest_penalty_points = (mask_reference, points)

    print("best_mask_ref, lowest_penalty_points", best_mask_ref, lowest_penalty_points)
    best_mask = masks[best_mask_ref]
    masked_codewords = apply_mask(best_mask, codeword_placement)
    masked_grid = override_grid(grid, masked_codewords)

    grid = add_quiet_zone(grid)
    # draw_grid_with_pil(grid)


def qr_check_format(fmt):
    g = 0x537  # = 0b10100110111 in python 2.6+
    for i in range(4, -1, -1):
        if fmt & (1 << (i + 10)):
            fmt ^= g << i
    return fmt


if __name__ == "__main__":
    from pprint import pprint

    ecl = ECL.M
    binary_str = encode("hello", ecl=ecl)
    # draw(binary_str, version=1, error_correction_level=ecl)

    result_format_info = get_format_information(ECL.M, 5)
    expected_format_info = "001010011011100"
    print(result_format_info, expected_format_info)
    assert result_format_info == expected_format_info

    # format = 0b000111101011001
    # fmt = (format << 10) + qr_check_format(format << 10)
    # print(bin(fmt))