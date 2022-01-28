import enum
from typing import Optional
from server.bots.act_scheduler.bot_exceptions import BotParseError, BotRunningError

import uiautomator2 as u2


def list_char_steps(chars: list, start, step):
    data = list()
    for ind, _c in enumerate(chars):
        data.append((_c, round(start + ind * step, 3)))
    return data


@enum.unique
class KeyboardType(enum.IntEnum):
    LETTER_LOWER = 1,
    LETTER_UPPER = 2,
    # LETTER = 3,  # letter_small + letter_upper
    DIGIT = 4,
    # LETTER_DIGIT = 7,  # letter + digit
    # SPECIAL = 8,
    # ALL = 15,  # letter + digit + special


class KeyType(enum.Enum):
    Capital = 'cap'
    Number = 'num'
    Letter = 'abc'
    Delete = 'del'
    Close = 'close'


class KeyboardConfig:
    """键盘配置
    字符格式: 行、列 (字符，宽比)
    字符配置: 字母、数字、符号、忽略
    功能配置: 切换大小写、切换数字、切换字母
    辅助功能键: 删除、关闭键盘
    """

    def __init__(self, letters, numbers, width, height, start_y):
        # 行 : 字符和宽比 数组
        self.letters = letters
        self.numbers = numbers
        self.width = width
        self.height = height
        self.start_y = start_y

    def find_pos(self, _char: str, height=None):
        # 优先查找字符集，再找数字集
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
    """CMBC 登录密码键盘处理"""

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

        # 行 : 字符和宽比 数组
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
        # seconds = 0.01 if seconds is None else seconds
        # self._d.sleep(seconds)

    def _switch_keyboard_type(self, target_type: KeyboardType):
        if self._current_type & target_type == target_type:
            return

        # print('current:{}, target:{}'.format(self._current_type, target_type))
        while self._current_type & target_type != target_type:
            switched_type: Optional[KeyboardType] = None  # None is not switch
            # 切换为字母
            if self._current_type & KeyboardType.DIGIT:
                # 切换字母时，会自动还原为小写，由轮询再次切换为大写
                if target_type == KeyboardType.LETTER_LOWER or target_type == KeyboardType.LETTER_UPPER:
                    self._click_char(KeyType.Letter.value)
                    switched_type = KeyboardType.LETTER_LOWER
            # 切换为数字
            elif target_type & KeyboardType.DIGIT and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._click_char(KeyType.Number.value)
                switched_type = target_type
            # 切换为字母大小写
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
        # 计算坐标位置，并点击
        pos_x, pos_y = self._kb_config.find_pos(_char.lower())  # 需统一转换为小写
        self._d.click(pos_x, pos_y)
        # print(f'{_char} 坐标: {pos_x},{pos_y}')

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
        # self._d.press('back')
        # 关闭按钮在字母面板
        self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
        self._click_char(KeyType.Close.value)


class CMBCAmountKeyboard:
    """CMBC 转账 金额/收款卡号 键盘处理"""

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
    """CMBC 转账 短信验证码/交易密码 键盘处理"""

    _d: u2.Device
    _source: str
    _keyboard_xpath: str

    def __init__(self, d: u2.Device, parent_path: str, source: str = None):
        self._d = d
        # self._source = d.dump_hierarchy() if source is None else source

        x_keyboard = d.xpath(parent_path, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        # 行 : 字符和宽比 数组
        numbers = {
            1: list_char_steps(['1', '2', '3'], 0.17, 0.33),
            2: list_char_steps(['4', '5', '6'], 0.17, 0.33),
            3: list_char_steps(['7', '8', '9'], 0.17, 0.33),
            4: list_char_steps([KeyType.Close.value, '0', KeyType.Delete.value], 0.17, 0.33),
        }
        self._x, self._y, self._width, self._height = x_keyboard.get().rect
        self._kb_config = KeyboardConfig(None, numbers, self._width, self._height, self._y)
        # self._keyboard_xpath = parent_path

    def _click_char(self, _char: str):
        # 计算坐标位置，并点击
        pos_x, pos_y = self._kb_config.find_pos(_char.lower())  # 需统一转换为小写
        self._d.click(pos_x, pos_y)
        # print(f'{_char} 坐标: {pos_x},{pos_y}')

    def input(self, text: str, interval: float = None):
        if not text.isdigit():
            raise BotRunningError(f'不支持交易密码含非数字字符:{text}')

        self._click_char(text)

        if interval is not None:
            self._d.sleep(interval)

    def close(self):
        self._click_char(KeyType.Close.value)
