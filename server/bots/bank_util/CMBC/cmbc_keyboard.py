import enum
from typing import Optional
from server.bots.act_scheduler.bot_exceptions import BotParseError, BotRunningError

import uiautomator2 as u2

__all__ = ['CMBCLoginPwdKeyboard', 'CMBCAmountKeyboard', 'CMBCTransferPwdKeyboard']


def list_char_steps(chars: list, start, step):
    data = list()
    for ind, _c in enumerate(chars):
        data.append((_c, round(start + ind * step, 3)))
    return data


@enum.unique
class KeyboardType(enum.IntEnum):
    LETTER_LOWER = 1,
    LETTER_UPPER = 2,
    DIGIT = 4,


class KeyType(enum.Enum):
    Capital = 'cap'
    Number = 'num'
    Letter = 'abc'
    Delete = 'del'
    Close = 'close'


class KeyboardConfig:

    def __init__(self, letters, numbers, width, height, start_y):
        self.letters = letters
        self.numbers = numbers
        self.width = width
        self.height = height
        self.start_y = start_y

    def find_pos(self, _char: str, height=None):
        all_configs = [self.letters, self.numbers]
        for chars_config in all_configs:
            if chars_config is None:
                continue
            lines = len(chars_config)
            each_y = (height if height else self.height) / lines
            for line, chars in chars_config.items():
                for char_pos in chars:
                    _c, _pos_percent = char_pos
                    if _c == _char:
                        return (_pos_percent * self.width), (self.start_y + ((line - 0.5) * each_y))  # 行 y 中间
        raise BotRunningError(f'未找到字符配置:{_char}')


class CMBCLoginPwdKeyboard:

    _d: u2.Device
    _current_type: KeyboardType
    _source: str
    _keyboard_xpath: str

    def __init__(self, d: u2.Device, parent_path: str, source: str = None):
        self._d = d
        self._source = d.dump_hierarchy() if source is None else source

        x_keyboard = d.xpath(parent_path, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        letters = {
            1: list_char_steps(['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'], 0.056, 0.099),
            2: list_char_steps(['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'], 0.1, 0.099),
            3: [(KeyType.Capital.value, 0.08)] + list_char_steps(['z', 'x', 'c', 'v', 'b', 'n', 'm'], 0.2,
                                                                 0.099) + [
                   (KeyType.Delete.value, 0.925)],
            4: [(KeyType.Number.value, 0.105), (KeyType.Close.value, 0.9)],
        }
        numbers = {
            1: list_char_steps(['1', '2', '3'], 0.17, 0.33),
            2: list_char_steps(['4', '5', '6'], 0.17, 0.33),
            3: list_char_steps(['7', '8', '9'], 0.17, 0.33),
            4: list_char_steps([KeyType.Letter.value, '0', KeyType.Delete.value], 0.17, 0.33),
        }
        self._x, self._y, self._width, self._height = x_keyboard.get().rect
        self._kb_config = KeyboardConfig(letters, numbers, self._width, self._height, self._y)
        self._keyboard_xpath = parent_path
        self._current_type = KeyboardType.LETTER_LOWER

    def _dump(self):
        self._source = self._d.dump_hierarchy()

    def _sleep_when_switch(self, seconds=None):
        pass  # 不需要等待，响应很快

    def _switch_keyboard_type(self, target_type: KeyboardType):
        if self._current_type & target_type == target_type:
            return

        while self._current_type & target_type != target_type:
            switched_type: Optional[KeyboardType] = None  # None is not switch
            if self._current_type & KeyboardType.DIGIT:
                if target_type == KeyboardType.LETTER_LOWER or target_type == KeyboardType.LETTER_UPPER:
                    self._click_char(KeyType.Letter.value)
                    switched_type = KeyboardType.LETTER_LOWER
            elif target_type & KeyboardType.DIGIT and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._click_char(KeyType.Number.value)
                switched_type = target_type
            elif (target_type & KeyboardType.LETTER_LOWER or target_type & KeyboardType.LETTER_UPPER) and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._click_char(KeyType.Capital.value)
                switched_type = target_type

            if switched_type is not None:
                self._current_type = switched_type
                self._sleep_when_switch()
                self._dump()
                pass
            else:
                raise BotRunningError('切换键盘类型失败')

    def _click_char(self, _char: str):
        pos_x, pos_y = self._kb_config.find_pos(_char.lower())  # 需统一转换为小写
        self._d.click(pos_x, pos_y)

    def input(self, text: str, interval: float = None):
        if text.islower():
            self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
        elif text.isupper():
            self._switch_keyboard_type(KeyboardType.LETTER_UPPER)
        elif text.isdigit():
            self._switch_keyboard_type(KeyboardType.DIGIT)
        else:
            raise BotRunningError(f'不支持密码含特殊字符:{text}')

        self._click_char(text)

        if interval is not None:
            self._d.sleep(interval)

    def close(self):
        self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
        self._click_char(KeyType.Close.value)


class CMBCAmountKeyboard:

    _d: u2.Device
    _current_type: KeyboardType
    _source: str
    _keyboard_xpath: str

    def __init__(self, d: u2.Device, parent_xpath: str, source: str = None):
        self._d = d
        self._source = d.dump_hierarchy() if source is None else source

        x_keyboard = d.xpath(parent_xpath, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')
        self._keyboard_xpath = x_keyboard.get().get_xpath()

    def _dump(self):
        self._source = self._d.dump_hierarchy()

    def _xpath_child(self, _xpath):
        return self._d.xpath(self._keyboard_xpath, self._source).child(_xpath)

    def input(self, text: str, interval: float = None):
        if text == '.':
            self._xpath_child(
                f'//*[contains(@resource-id,"cn.com.cmbc.newmbank:id/btn_point")]').click()
        elif text == '-':
            self._xpath_child(
                f'//*[contains(@resource-id,"cn.com.cmbc.newmbank:id/btn_sub")]').click()
        elif text.isdigit():
            self._xpath_child(
                f'//*[contains(@resource-id,"cn.com.cmbc.newmbank:id/btn_")][@text="{text}"]').click()
        else:
            raise BotRunningError(f'不支持金额含特殊字符:{text}')

        if interval is not None:
            self._d.sleep(interval)

    def delete(self, text: str):
        for _ in text:
            self._xpath_child('//*[@resource-id="cn.com.cmbc.newmbank:id/btn_del"]').click()
            self._d.sleep(0.1)


class CMBCTransferPwdKeyboard:

    _d: u2.Device
    _source: str
    _keyboard_xpath: str

    def __init__(self, d: u2.Device, parent_path: str, source: str = None):
        self._d = d

        x_keyboard = d.xpath(parent_path, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        numbers = {
            1: list_char_steps(['1', '2', '3'], 0.17, 0.33),
            2: list_char_steps(['4', '5', '6'], 0.17, 0.33),
            3: list_char_steps(['7', '8', '9'], 0.17, 0.33),
            4: list_char_steps([KeyType.Close.value, '0', KeyType.Delete.value], 0.17, 0.33),
        }
        self._x, self._y, self._width, self._height = x_keyboard.get().rect
        self._kb_config = KeyboardConfig(None, numbers, self._width, self._height, self._y)

    def _click_char(self, _char: str):
        pos_x, pos_y = self._kb_config.find_pos(_char.lower())  # 需统一转换为小写
        self._d.click(pos_x, pos_y)

    def input(self, text: str, interval: float = None):
        if not text.isdigit():
            raise BotRunningError(f'不支持交易密码含非数字字符:{text}')

        self._click_char(text)

        if interval is not None:
            self._d.sleep(interval)

    def close(self):
        self._click_char(KeyType.Close.value)
