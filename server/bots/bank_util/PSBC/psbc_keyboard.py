import enum
from typing import Optional

import uiautomator2 as u2

from server.bots.act_scheduler.bot_exceptions import BotRunningError, BotParseError

__all__ = ['PSBCNumberKeyboard', 'PSBCFullPwdKeyboard']


@enum.unique
class KeyboardType(enum.IntEnum):
    LETTER_LOWER = 1,
    LETTER_UPPER = 2,
    DIGIT = 4,


class PSBCNumberKeyboard:

    def __init__(self, d: u2.Device, source: str = None):
        x_keyboard = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/llayout_keyboard_panel"]', source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        self._d = d
        self._source = d.dump_hierarchy() if source is None else source
        self._keyboard_xpath = x_keyboard.get().get_xpath()

    def _xpath_child(self, _xpath):
        return self._d.xpath(self._keyboard_xpath, self._source).child(_xpath)

    def input(self, text: str, interval: float = None, has_point=False):
        if text.isdigit():
            self._xpath_child(
                f'//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_num")][@text="{text}"]').click()
        elif text == '.' and has_point:
            self._xpath_child(
                f'//*[@resource-id="com.yitong.mbank.psbc:id/btnNumBoardPoint"]').click()
        else:
            raise BotRunningError(f'手机号不支持非数字字符: {text}')

        if interval is not None:
            self._d.sleep(interval)

    def clear(self):
        self._xpath_child('//*[@resource-id="com.yitong.mbank.psbc:id/btnNumBoardClean"]').click()

    def close(self):
        self._xpath_child('//*[@resource-id="com.yitong.mbank.psbc:id/btnBoardCancel"]').click()


class PSBCFullPwdKeyboard:

    def __init__(self, d: u2.Device, kb_xpath: str, source: str = None):
        keyboard = d.xpath(kb_xpath, source)
        if not keyboard.exists:
            raise u2.exceptions.XPathElementNotFoundError('未找到 密码键盘 节点')

        self._d = d
        self._source = d.dump_hierarchy() if source is None else source
        self._keyboard_xpath = keyboard.get().get_xpath()
        self._current_type = self._recognize()

    def _recognize(self):
        xpath_type = {
            KeyboardType.DIGIT:
                '//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_num")][@text="1"]',
            KeyboardType.LETTER_LOWER:
                '//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_abc")][@text="a"]',
            KeyboardType.LETTER_UPPER:
                '//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_abc")][@text="A"]',
        }
        for t, x in xpath_type.items():
            if self._xpath_child(x, use_source=True).exists:
                return t
        raise BotRunningError('未识别到键盘类型，不支持特殊字符')

    def _xpath_child(self, _xpath, use_source=False):
        _source = self._source if use_source else None
        return self._d.xpath(self._keyboard_xpath, _source).child(_xpath)

    def _switch_keyboard_type(self, target_type: KeyboardType):
        if self._current_type & target_type == target_type:
            return
        while self._current_type & target_type != target_type:
            switched_type: Optional[KeyboardType] = None  # None is not switch

            if target_type & KeyboardType.DIGIT and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._xpath_child('//*[@resource-id="com.yitong.mbank.psbc:id/btnAbcBoardChangeNumber"]').click()
                switched_type = KeyboardType.DIGIT
            elif (target_type & KeyboardType.LETTER_LOWER or target_type & KeyboardType.LETTER_UPPER) and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._xpath_child('//*[@resource-id="com.yitong.mbank.psbc:id/btnAbcBoardUpperLowSwitch"]').click()
                letter_del = (KeyboardType.LETTER_LOWER | KeyboardType.LETTER_UPPER) ^ target_type
                switched_type = (self._current_type | target_type) ^ letter_del
            elif self._current_type & KeyboardType.DIGIT and (
                    target_type == KeyboardType.LETTER_LOWER or target_type == KeyboardType.LETTER_UPPER):
                self._xpath_child('//*[@resource-id="com.yitong.mbank.psbc:id/btnNumBoardChangeAbc"]').click()
                switched_type = KeyboardType.LETTER_LOWER
                pass

            if switched_type is not None:
                self._current_type = switched_type
            else:
                raise BotParseError('切换键盘类型失败')

    def input(self, text: str, interval: float = None):
        if text.islower():
            self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
            self._xpath_child(
                f'//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_abc")][@text="{text}"]').click()
        elif text.isupper():
            self._switch_keyboard_type(KeyboardType.LETTER_UPPER)
            self._xpath_child(
                f'//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_abc")][@text="{text}"]').click()
        elif text.isdigit():
            self._switch_keyboard_type(KeyboardType.DIGIT)
            self._xpath_child(
                f'//*[contains(@resource-id,"com.yitong.mbank.psbc:id/key_board_num")][@text="{text}"]').click()
        else:
            raise BotRunningError('不支持密码含特殊字符:{}'.format(text))

        if interval is not None:
            self._d.sleep(interval)

    def close(self):
        self._xpath_child('//*[@resource-id="com.yitong.mbank.psbc:id/btnBoardCancel"]').click()
