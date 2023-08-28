from functools import partial
from typing import Dict, List

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

np.set_printoptions(formatter={"all": lambda x: str(int(x))})  # type: ignore

WHITE = 0
BLACK = 1


def get_empty_grid(size: int = 21):
    grid = np.zeros((size, size))
    return grid


def get_timing_pattern(grid_size: int = 21) -> Dict[tuple, int]:
    grid = np.zeros((grid_size, grid_size))
    fixed_row, fixed_col = 6, 6
    timing_pattern_row_black = {(fixed_row, x): BLACK for x in range(0, grid_size, 2)}
    timing_pattern_row_white = {(fixed_row, x): WHITE for x in range(1, grid_size, 2)}
    timing_pattern_col_black = {(x, fixed_col): BLACK for x in range(0, grid_size, 2)}
    timing_pattern_col_white = {(x, fixed_col): WHITE for x in range(1, grid_size, 2)}
    result = {
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


def get_finder_pattern_module_b(top_left_row_index, top_left_col_index):
    module_size = 5
    value = 2
    top_row = create_row(
        fixed_row_index=top_left_row_index,
        col_start=top_left_col_index,
        col_end=top_left_col_index + module_size,
        value=WHITE,
    )
    bottom_row = create_row(
        fixed_row_index=top_left_row_index + module_size - 1,
        col_start=top_left_col_index,
        col_end=top_left_col_index + module_size,
        value=WHITE,
    )
    left_col = create_col(
        fixed_col_index=top_left_col_index,
        row_start=top_left_row_index,
        row_end=top_left_row_index + module_size,
        value=WHITE,
    )
    right_col = create_col(
        fixed_col_index=top_left_col_index + module_size - 1,
        row_start=top_left_row_index,
        row_end=top_left_row_index + module_size,
        value=WHITE,
    )
    return {**top_row, **right_col, **bottom_row, **left_col}


def get_finder_pattern_module_c(top_left_row_index, top_left_col_index):
    module_size = 7
    value = 1
    top_row = create_row(
        fixed_row_index=top_left_row_index,
        col_start=top_left_col_index,
        col_end=top_left_col_index + module_size,
        value=value,
    )
    bottom_row = create_row(
        fixed_row_index=top_left_row_index + module_size - 1,
        col_start=top_left_col_index,
        col_end=top_left_col_index + module_size,
        value=value,
    )
    left_col = create_col(
        fixed_col_index=top_left_col_index,
        row_start=top_left_row_index,
        row_end=top_left_row_index + module_size,
        value=value,
    )
    right_col = create_col(
        fixed_col_index=top_left_col_index + module_size - 1,
        row_start=top_left_row_index,
        row_end=top_left_row_index + module_size,
        value=value,
    )
    return {**top_row, **right_col, **bottom_row, **left_col}


def get_finder_pattern(grid_size: int = 21):
    module_a_top_left = {(x, y): BLACK for x in range(2, 5) for y in range(2, 5)}
    module_a_top_right = {(x, y): BLACK for x in range(2, 5) for y in range(grid_size - 5, grid_size - 2)}
    module_a_bottom_left = {(x, y): BLACK for x in range(grid_size - 5, grid_size - 2) for y in range(2, 5)}
    module_a = {**module_a_top_left, **module_a_top_right, **module_a_bottom_left}
    module_b_size = 5
    module_b_top_left = get_finder_pattern_module_b(top_left_row_index=1, top_left_col_index=1)
    module_b_top_right = get_finder_pattern_module_b(
        top_left_row_index=1, top_left_col_index=grid_size - module_b_size - 1
    )
    module_b_bottom_left = get_finder_pattern_module_b(
        top_left_row_index=grid_size - module_b_size - 1, top_left_col_index=1
    )
    module_b = {**module_b_top_left, **module_b_top_right, **module_b_bottom_left}

    module_c_size = 7
    module_c_top_left = get_finder_pattern_module_c(top_left_row_index=0, top_left_col_index=0)
    module_c_top_right = get_finder_pattern_module_c(top_left_row_index=0, top_left_col_index=grid_size - module_c_size)
    module_c_bottom_left = get_finder_pattern_module_c(
        top_left_row_index=grid_size - module_c_size, top_left_col_index=0
    )
    module_c = {**module_c_top_left, **module_c_top_right, **module_c_bottom_left}

    return {**module_a, **module_b, **module_c}


def get_seperator_pattern(grid_size):
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


def override_grid(grid, indexes: Dict[tuple, int]):
    for index, value in indexes.items():
        i, j = index
        grid[i][j] = value
    return grid


def draw_grid_with_pil(grid: np.ndarray, cell_size: int = 20):
    """
    Draw a grid using PIL based on a 2D numpy array.

    Parameters:
    - grid: A 2D numpy array of shape (n, n) containing 0, 1, or -1.
    - cell_size: The size of each cell in the grid in pixels.

    The function will color the cells as follows:
    - 0 will be white
    - 1 will be black
    - -1 will be light gray
    """

    # Validate the shape of the grid
    if grid.shape[0] != grid.shape[1]:
        raise ValueError("The input grid must be square (n x n).")

    # Initialize an image object with white background
    img_size = grid.shape[0] * cell_size
    img = Image.new("RGB", (img_size, img_size), "lightgray")
    draw = ImageDraw.Draw(img)

    # Define the colors
    color_map = {0: "white", 1: "black", -1: "lightgray"}

    # Loop through the grid and fill in the colors
    for i in range(grid.shape[0]):  # Rows
        for j in range(grid.shape[1]):  # Columns
            x0, y0 = j * cell_size, i * cell_size  # Corrected here
            x1, y1 = x0 + cell_size, y0 + cell_size
            cell_value = grid[i, j]
            cell_color = color_map.get(cell_value, "white")
            draw.rectangle(((x0, y0), (x1, y1)), fill=cell_color)

    img.show()


def draw(binary_string: str, grid_size: int = 21):
    timing_pattern = get_timing_pattern(grid_size)
    finder_pattern = get_finder_pattern(grid_size)
    seperator_pattern = get_seperator_pattern(grid_size)

    grid = np.full((grid_size, grid_size), -1)

    grid = override_grid(grid, timing_pattern)
    grid = override_grid(grid, finder_pattern)
    grid = override_grid(grid, seperator_pattern)
    print(grid)
    draw_grid_with_pil(grid)


if __name__ == "__main__":
    draw("011")
