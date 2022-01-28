import uiautomator2 as u2


class BotDeviceFilter:
    def do(self, d: u2.Device, source: str):
        pass


class BotDeviceProxy:
    _dump_filter: list[BotDeviceFilter] = []

    def add_filter(self, _filter: BotDeviceFilter):
        self._dump_filter.append(_filter)

    def dump_hierarchy(self, d: u2.Device, compressed=False, pretty=False, check_error=False):
        source = d.dump_hierarchy(compressed, pretty)
        if check_error and self._dump_filter:
            for _f in self._dump_filter:
                _f.do(d, source)

        return source
