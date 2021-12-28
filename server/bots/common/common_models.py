from typing import List, Callable


class GoToPath:
    def __init__(self, from_paths: List[str] = '', to_paths: List[str] = '', to_step: Callable = ()):
        self.from_paths = from_paths
        self.to_paths = to_paths
        self.to_step = to_step

    def to_go(self) -> str:
        for idx in range(len(self.from_paths) - 1, -1, -1):
            print('current page: %s' % self.from_paths[idx])
            for path in self.to_paths:
                if self.from_paths[idx] == path:
                    print('common page: %s' % path)
                    return path
            if idx > 0:
                self.to_step()


if __name__ == '__main__':
    from_path = ['A', 'B', 'C', 'D', 'E']
    to_path = ['A', 'B', 'C', 'H', 'I']


    def go_to_step():
        print('going')


    go_to_path = GoToPath(from_path, to_path, go_to_step)
    go_to_path.to_go()
