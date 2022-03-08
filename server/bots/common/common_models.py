from typing import List, Callable, Dict, Any


# 返回路径的返回值模型
class GoToPathRes:
    def __init__(self, idx: int = 0, current: str = ''):
        self.idx = idx
        self.current = current


# 返回路径的公共类
class GoToPath:
    def __init__(self, from_paths: List[str], to_paths: List[str], to_step: Callable = ()):
        self.from_paths = from_paths
        self.to_paths = to_paths
        self.to_step = to_step
        self.current_idx: int = 0
        self.current_path: str = ''

    # 执行返回路径返回
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

    # 执行原路返回
    def default_way(self):

        for idx in range(len(self.from_paths) - 1, -1, -1):
            self.current_idx = idx
            self.current_path = self.from_paths[idx]
            if idx > 0:
                print('default_way: current page: %s' % self.from_paths[idx])
                self.to_step()
        return GoToPathRes(self.current_idx, self.current_path)


class DistinctList:
    """列表去重类，支持添加、去重(不确定 key 处理)、比较 key、value 等"""
    data: Dict[str, Any] = {}
    # 忽略 key 列表
    _ignore_keys: List[str] = []

    def append(self, key: str, val: Any):
        self.data[key] = val

    def contains_key(self, _key: str, with_ignore=True):
        return (_key in self.data) or (with_ignore and _key in self._ignore_keys)

    def contains_val(self, _val: Any):
        return _val in self.data.values()

    def contains_key_val(self, _key: str, _val: Any):
        """是否包含 key 或 value
        1. 包含 key 或 忽略 key，返回 True
        2. 不包含 key ，但包含 value ，则添加到忽略 key 中，避免相同 value 不同 key，这样在使用`contains_key`方法可直接去重，返回 True
        3. 否则返回 False
        """
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
