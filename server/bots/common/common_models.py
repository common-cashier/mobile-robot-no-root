<<<<<<< HEAD
from typing import List, Callable, Dict, Any


class GoToPathRes:
    def __init__(self, idx: int = 0, current: str = ''):
        self.idx = idx
        self.current = current


class GoToPath:
    def __init__(self, from_paths: List[str], to_paths: List[str], to_step: Callable = ()):
        self.from_paths = from_paths
        self.to_paths = to_paths
        self.to_step = to_step
        self.current_idx: int = 0
        self.current_path: str = ''

    def to_go(self) -> GoToPathRes:
        for idx in range(len(self.from_paths) - 1, -1, -1):
            print('to_go: current page: %s' % self.from_paths[idx])
            self.current_idx = idx
            self.current_path = self.from_paths[idx]
            for path in self.to_paths:
                if self.from_paths[idx] == path:
                    print('to_go: common page: %s' % path)
                    return GoToPathRes(self.current_idx, self.current_path)
            if idx > 0:
                self.to_step()
        return GoToPathRes(self.current_idx, self.current_path)

    def default_way(self):

        for idx in range(len(self.from_paths) - 1, -1, -1):
            self.current_idx = idx
            self.current_path = self.from_paths[idx]
            if idx > 0:
                print('default_way: current page: %s' % self.from_paths[idx])
                self.to_step()
        return GoToPathRes(self.current_idx, self.current_path)


class DistinctList:
    data: Dict[str, Any] = {}
    _ignore_keys: List[str] = []

    def append(self, key: str, val: Any):
        self.data[key] = val

    def contains_key(self, _key: str, with_ignore=True):
        return (_key in self.data) or (with_ignore and _key in self._ignore_keys)

    def contains_val(self, _val: Any):
        return _val in self.data.values()

    def contains_key_val(self, _key: str, _val: Any):
        if self.contains_key(_key):
            return True
        if self.contains_val(_val):
            self._ignore_keys.append(_key)
            return True
        return False

    def data_list(self):
        return list(self.data.values())

    def count(self):
        return len(self.data)

    def reset(self):
        self.data.clear()
        self._ignore_keys.clear()

    def __len__(self):
        return len(self.data)


if __name__ == '__main__':
    from_path = ['A', 'B', 'C', 'D', 'E']
    to_path = ['A', 'B', 'C', 'H', 'I']


    def go_to_step():
        print('going back!')


    go_to_path = GoToPath(from_path, to_path, go_to_step)
    go_to_path.to_go()
    go_to_path.default_way()
=======
from typing import List, Callable, Dict, Any


class GoToPathRes:
    def __init__(self, idx: int = 0, current: str = ''):
        self.idx = idx
        self.current = current


class GoToPath:
    def __init__(self, from_paths: List[str], to_paths: List[str], to_step: Callable = ()):
        self.from_paths = from_paths
        self.to_paths = to_paths
        self.to_step = to_step
        self.current_idx: int = 0
        self.current_path: str = ''

    def to_go(self) -> GoToPathRes:
        for idx in range(len(self.from_paths) - 1, -1, -1):
            print('to_go: current page: %s' % self.from_paths[idx])
            self.current_idx = idx
            self.current_path = self.from_paths[idx]
            for path in self.to_paths:
                if self.from_paths[idx] == path:
                    print('to_go: common page: %s' % path)
                    return GoToPathRes(self.current_idx, self.current_path)
            if idx > 0:
                self.to_step()
        return GoToPathRes(self.current_idx, self.current_path)

    def default_way(self):

        for idx in range(len(self.from_paths) - 1, -1, -1):
            self.current_idx = idx
            self.current_path = self.from_paths[idx]
            if idx > 0:
                print('default_way: current page: %s' % self.from_paths[idx])
                self.to_step()
        return GoToPathRes(self.current_idx, self.current_path)


class DistinctList:
    data: Dict[str, Any] = {}
    _ignore_keys: List[str] = []

    def append(self, key: str, val: Any):
        self.data[key] = val

    def contains_key(self, _key: str, with_ignore=True):
        return (_key in self.data) or (with_ignore and _key in self._ignore_keys)

    def contains_val(self, _val: Any):
        return _val in self.data.values()

    def contains_key_val(self, _key: str, _val: Any):
        if self.contains_key(_key):
            return True
        if self.contains_val(_val):
            self._ignore_keys.append(_key)
            return True
        return False

    def data_list(self):
        return list(self.data.values())

    def count(self):
        return len(self.data)

    def reset(self):
        self.data.clear()
        self._ignore_keys.clear()

    def __len__(self):
        return len(self.data)


if __name__ == '__main__':
    from_path = ['A', 'B', 'C', 'D', 'E']
    to_path = ['A', 'B', 'C', 'H', 'I']


    def go_to_step():
        print('going back!')


    go_to_path = GoToPath(from_path, to_path, go_to_step)
    go_to_path.to_go()
    go_to_path.default_way()
>>>>>>> 9106ec0777a2e9e0e3255c47bc883216c62945f8
