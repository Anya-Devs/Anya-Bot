import time
import os
import sys
from collections import deque

class MazeWatcher:
    WALLS = {'o', '|', '-'}
    EMPTY = ' '
    START = 'x'
    TARGETS = {'T', ':'}
    MOVES = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.first_run = True
        self.TRAIL = '#'

    def clear_terminal(self):
        if sys.platform.startswith('win'):
            os.system('cls')
        else:
            os.system('clear')

    def print_instructions(self):
        self.clear_terminal()
        print("""🧠 Maze Bot Active

Instructions:
- Draw your maze in "maze.txt"
- Use: 'x' (bot), ':' or 'T' (goal), 'o'/'|' (walls)
- Leave file empty if you want — bot watches constantly
- Bot will move step-by-step toward goal

✅ This program never stops. Add/remove/update live.""")

    def read_maze(self):
        if not os.path.exists(self.file_path):
            return []  
        with open(self.file_path, 'r') as f:
            lines = [list(line.rstrip('\n').rstrip()) for line in f if line.strip()]
        if not lines:  
            return [] 
        max_len = max((len(row) for row in lines), default=0)
        return [row + [' '] * (max_len - len(row)) for row in lines]

    def write_maze(self, maze):
        if maze is None:
            return 
        with open(self.file_path, 'w') as f:
            for row in maze:
                f.write(''.join(row) + '\n')

    def find_char(self, maze, chars):
        for i, row in enumerate(maze):
            for j, c in enumerate(row):
                if c in chars:
                    return (i, j)
        return None

    def is_valid(self, maze, x, y):
        return (
            0 <= x < len(maze) and
            0 <= y < len(maze[0]) and
            maze[x][y] not in self.WALLS
        )

    def bfs(self, maze, start, goal):
        q = deque([(start, [])])
        visited = set()
        while q:
            (x, y), path = q.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            if (x, y) == goal:
                return path
            for dx, dy in self.MOVES:
                nx, ny = x + dx, y + dy
                if self.is_valid(maze, nx, ny):
                    q.append(((nx, ny), path + [(nx, ny)]))
        return []

    def clear_trail(self, maze):
        with open(self.file_path, 'r') as file:
            content = file.read()
        content = content.replace(self.TRAIL, ' ') 

        with open(self.file_path, 'w') as file:
            file.write(content)

    def run(self):
        if self.first_run:
            self.print_instructions()
            self.first_run = False

        while True:
            maze = self.read_maze()
            if not maze:  
                time.sleep(1)
                continue

            start = self.find_char(maze, {self.START})
            goal = self.find_char(maze, self.TARGETS)

            if not start or not goal:
                time.sleep(1)
                continue

            path = self.bfs(maze, start, goal)
            if not path:
                time.sleep(1)
                continue

            for step in path:
                maze = self.read_maze()
                current = self.find_char(maze, {self.START})
                if not current:
                    break
                x, y = current
                nx, ny = step

                # Add bounds check
                if not (0 <= nx < len(maze) and 0 <= ny < len(maze[0])):
                    break  

                if maze[nx][ny] in self.TARGETS:
                    maze[x][y] = self.EMPTY  
                    maze[nx][ny] = self.START  
                    self.write_maze(maze)
                    maze = self.clear_trail(maze) 
                    self.write_maze(maze)
                    break

                maze[x][y] = self.TRAIL
                maze[nx][ny] = self.START
                self.write_maze(maze)
                time.sleep(0.4)  

            time.sleep(1)

if __name__ == "__main__":
    MazeWatcher("maze.txt").run()
