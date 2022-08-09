from typing import List, NamedTuple
import random
from enum import Enum
from collections import deque
import os


class GameStatus(Enum):
    IN_GAME = 1
    LOST = 2
    WIN = 3


# If board is 3x3 (or less) and the black hole is in the middle, then there is no free cell on the board.
# The initial idea is that the first click should open anything but the black hole cell
# (actually it must be a free cell even without numbers, but this option is out of the scope of this task)
SMALLEST_BOARD_SIZE = 3

# From a technical perspective this class is a overkill
# But heavily using coordinates x and y may lead to the mess so it's better to specify x and y explicitly.
class Coord(NamedTuple):
    x: int
    y: int


# Let's keep everything about cell in single class for the sake of simplicity.
# The only property that can be added in future is a flag attribute to mark cell as plausible black hole.
# Since it is pretty simple class it could be rewritten as dataclass
class Cell:
    def __init__(self, is_hole: bool = False):
        self.is_hole = is_hole
        self.holes_around = 0
        self.is_opened = False


# This class contains the logic of randomization.
# In the production code this separation will allow to mock this class to return pre-defined set of black holes.
# Writing tests for board would be much easier in this way
class HolesGenerator:
    def __init__(self, size: int, holes_num: int):
        self.width = size
        self.height = size
        self.holes_num = holes_num

    def generate_holes(self, skip_cell: Coord) -> List[Coord]:
        # In order to get some random coordinates of the holes excluding first cell
        # This approach allows to use sample method from random library.
        # Otherwise we have to generate random coordinates and check if it is already generated.
        # When number of black holes is near the size of the board it would take a lot of time.
        # Let's hope that random.sample generates uniform distribution of values.
        available_places = []
        for x in range(self.width):
            for y in range(self.height):
                coord = Coord(x=x, y=y)
                if coord == skip_cell:
                    continue
                available_places.append(coord)

        holes_coords = list(
            random.sample(
                available_places,
                k=self.holes_num,
            )
        )

        return holes_coords

    def board_size(self) -> int:
        return self.width * self.height

    def _to_flat_coord(self, coord: Coord) -> int:
        return coord.x + coord.y * self.width

    def _from_flat_coord(self, coord: int) -> Coord:
        y, x = divmod(coord, self.height)
        return Coord(x=x, y=y)


class Board:
    # Pre-calculated relative coordinates of the adjacent cells
    neighbors = [Coord(x=x, y=y) for x in range(-1, 2) for y in range(-1, 2) if not (x == 0 and y == 0)]

    def __init__(self, size: int, holes_num: int, holes_generator: HolesGenerator, first_coord: Coord):
        if size <= SMALLEST_BOARD_SIZE:
            raise ValueError(
                f"Size {size} is too small. Board must be larger than {SMALLEST_BOARD_SIZE} otherwise it may not have any "
            )
        if size**2 - SMALLEST_BOARD_SIZE**2 <= holes_num:
            raise ValueError(
                f"{holes_num} holes is too many for the board of the size {size}. Number of black holes must be at least 9 less than number of the board cells"
            )

        # The board is square but it is more natural to check appropriate side rather than abstract size
        self.width = size
        self.height = size

        self.status = GameStatus.IN_GAME

        # required to check if game can be stopped
        self.cells_to_open = self.width * self.height - holes_num

        """
        PART 1

        Size of the board is known and it is tiny so simple structure like list of rows is fine.
        It allows to keep everything in single matrix
        In case of huge board it it possible to keep data in bit matrix or use dict to associate coordinates with values
        Like Dict[(x, y)] = Cell
        It allows to minimize memory usage for sparse data.
        Hint: Numpy also can be used to keep matrix.

        Important Note:
        Why first_coord is required here?
        Original game does not allow to fail at the first step. So we have to generate the board AFTER the first step
        so that specified coordinates are of safe cell
        """
        self.board: List[List[Cell]] = [[Cell() for _ in range(self.width)] for _ in range(self.height)]
        self._generate_board(holes_generator, first_coord)
        self.click_on(first_coord)

    def _generate_board(self, holes_generator: HolesGenerator, first_coord: Coord):
        self._generate_holes(holes_generator, first_coord)
        self._generate_holes_adjacent()

    def _generate_holes(self, holes_generator: HolesGenerator, first_cell: Coord):
        """
        PART 2

        See HolesGenerator class for details
        """
        holes: List[Coord] = holes_generator.generate_holes(skip_cell=first_cell)
        for hole_coord in holes:
            hole_cell = self.at(hole_coord)
            hole_cell.is_hole = True

    def _generate_holes_adjacent(self):
        """
        PART 3

        Go through all the cells and calc neighbor black holes
        """
        for y in range(self.height):
            for x in range(self.width):
                coord = Coord(x=x, y=y)
                cell = self.at(coord)
                if cell.is_hole:
                    continue
                cell.holes_around = sum(int(adjacent_cell.is_hole) for adjacent_cell in self._get_adjacent_cells(coord))

    def _get_adjacent_coords(self, coord: Coord) -> List[Coord]:
        adjacent_coords = []
        for neighbor in self.neighbors:
            adjacent_coord = Coord(x=neighbor.x + coord.x, y=neighbor.y + coord.y)
            if (
                adjacent_coord.x < 0
                or adjacent_coord.x >= self.width
                or adjacent_coord.y < 0
                or adjacent_coord.y >= self.height
            ):
                continue
            adjacent_coords.append(adjacent_coord)
        return adjacent_coords

    def _get_adjacent_cells(self, coord: Coord) -> List[Cell]:
        return [self.at(adjacent_coord) for adjacent_coord in self._get_adjacent_coords(coord)]

    def click_on(self, coord: Coord):
        """
        PART 4

        If we click on black hole then game is over
        Otherwise open the cell and check adjacent in case the cell is empty.
        If all cells are opened except black holes then the game is over.
        """
        cell = self.at(coord)

        if cell.is_hole:
            self.status = GameStatus.LOST
            return

        self._open_cells(coord)

    def _open_cells(self, coord: Coord):
        """
        This is good old DFS:
        1. add element to the queue
        2. while queue is not empty, extract one element, check the adjacent and add them the queue if required

        It is possible to archive the same result with recursion. But on large boards we can reach the recursion limit.
        """
        queue = deque([coord])

        while queue:
            coord = queue.popleft()
            cell = self.at(coord)
            self._open_cell(cell)

            if cell.holes_around:
                continue

            for adjacent_coord in self._get_adjacent_coords(coord):
                adjacent_cell = self.at(adjacent_coord)
                if adjacent_cell.is_hole:
                    continue
                if adjacent_cell.is_opened:
                    continue
                queue.append(adjacent_coord)

    def _open_cell(self, cell: Cell):
        if cell.is_opened:
            return

        cell.is_opened = True
        self.cells_to_open -= 1
        if not self.cells_to_open:
            self.status = GameStatus.WIN

    def at(self, coord: Coord) -> Cell:
        return self.board[coord.y][coord.x]


class DisplayBoard:
    """
    Utility class for displaying board
    Not required for task
    """

    def __init__(self, board: Board):
        self.board = board

    def show_raw_board(self):
        print("  ", " ".join([str(x) for x in range(self.board.width)]))
        print(" ", "-" * self.board.width * 2)
        for y, row in enumerate(self.board.board):
            print(f"{y}|", " ".join([self._raw_cell(cell) for cell in row]))

    def _raw_cell(self, cell: Cell):
        if cell.is_hole:
            return "H"
        if cell.holes_around:
            return str(cell.holes_around)
        return "."

    def show_game_board(self):
        print("  ", " ".join([str(x) for x in range(self.board.width)]))
        print(" ", "-" * self.board.width * 2)
        for y, row in enumerate(self.board.board):
            print(f"{y}|", " ".join([self._game_cell(cell) for cell in row]))

    def _game_cell(self, cell: Cell):
        if not cell.is_opened:
            return "*"
        if cell.is_hole:
            return "H"
        if cell.holes_around:
            return str(cell.holes_around)
        return "."


def get_coord_to_open(size: int) -> Coord:
    # Pseudo TUI interface for interacting with user
    print("\n")
    while True:
        raw_input = input("Provide coordinates to open, like 'x y': ")
        try:
            raw_x, raw_y = raw_input.split(" ")
            x = int(raw_x)
            y = int(raw_y)
            if x < 0 or x >= size:
                print("x is incorrect")
            if y < 0 or y >= size:
                print("y is incorrect")
            print()
            return Coord(x=x, y=y)
        except Exception as ex:
            print("Incorrect coordinates, try once again", ex)


def main():
    """
    This is how game flow might look like with interface
    """

    os.system("clear")

    size = 8
    holes_num = 5

    first_coord = get_coord_to_open(size)

    board = Board(
        size=size,
        holes_num=holes_num,
        holes_generator=HolesGenerator(size=size, holes_num=holes_num),
        first_coord=first_coord,
    )

    display = DisplayBoard(board)
    print("Cheat board with all info exposed")
    display.show_raw_board()
    print("\n")
    display.show_game_board()

    # main game loop
    while True:
        coord = get_coord_to_open(size)
        board.click_on(coord)
        display.show_game_board()
        if board.status != GameStatus.IN_GAME:
            break

    result = "WIN" if board.status == GameStatus.WIN else "LOST"
    print(f"Congratulation, sailor, you {result} the game")
    print("\n")
    display.show_raw_board()


if __name__ == "__main__":
    main()
