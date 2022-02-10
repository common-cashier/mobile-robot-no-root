import enum
import io
from typing import Optional
from server.bots.act_scheduler.bot_exceptions import BotParseError, BotRunningError
from server.bots.bank_util.BCM.recognize import RecognizeNumber

import uiautomator2 as u2

__all__ = ['BCMLoginPwdKeyboard', 'BCMTransferPwdKeyboard']


@enum.unique
class KeyboardType(enum.IntEnum):
    LETTER_LOWER = 1,
    LETTER_UPPER = 2,
    DIGIT = 4,


class BCMLoginPwdKeyboard:

    _d: u2.Device
    _current_type: KeyboardType
    _source: str
    _keyboard_xpath: str

    def __init__(self, d: u2.Device, parent_xpath, source: str = None):
        self._d = d
        self._source = d.dump_hierarchy() if source is None else source

        keyboard = d.xpath(parent_xpath, source)
        if not keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        self._keyboard_xpath = keyboard.get().get_xpath()
        self._current_type = KeyboardType.LETTER_LOWER | KeyboardType.DIGIT

    def _xpath_child(self, _xpath):
        return self._d.xpath(self._keyboard_xpath, self._source).child(_xpath)

    def _dump(self):
        self._source = self._d.dump_hierarchy()

    def _sleep_when_switch(self, seconds=None):
        pass  # 不需要等待，响应很快

    def _switch_keyboard_type(self, target_type: KeyboardType):
        if self._current_type & target_type == target_type:
            return
        while self._current_type & target_type != target_type:
            switched_type: Optional[KeyboardType] = None  # None is not switch

            if target_type & KeyboardType.DIGIT and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._xpath_child('//*[contains(@resource-id,"com.bankcomm.Bankcomm:id/keyNumberic")]').click()
                switched_type = self._current_type | KeyboardType.DIGIT
            elif (target_type & KeyboardType.LETTER_LOWER or target_type & KeyboardType.LETTER_UPPER) and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._xpath_child('//*[contains(@resource-id,"com.bankcomm.Bankcomm:id/keycap1")]').click()
                letter_del = (KeyboardType.LETTER_LOWER | KeyboardType.LETTER_UPPER) ^ target_type
                switched_type = (self._current_type | target_type) ^ letter_del
            elif self._current_type & KeyboardType.DIGIT and (
                    target_type == KeyboardType.LETTER_LOWER or target_type == KeyboardType.LETTER_UPPER):
                pass

            if switched_type is not None:
                self._current_type = switched_type
                self._sleep_when_switch()
                self._dump()
                pass
            else:
                raise BotParseError('切换键盘类型失败')

    def input(self, text: str, interval: float = None):
        if text.islower():
            self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
        elif text.isupper():
            self._switch_keyboard_type(KeyboardType.LETTER_UPPER)
        elif text.isdigit():
            self._switch_keyboard_type(KeyboardType.DIGIT)
        else:
            raise BotRunningError(f'不支持密码含特殊字符:{text}')

        self._xpath_child(f'//*[contains(@resource-id,"com.bankcomm.Bankcomm:id/key")][@text="{text}"]').click()

        if interval is not None:
            self._d.sleep(interval)

    def get_confirm_node(self) -> [u2.xpath.XMLElement, bool]:
        x_confirm = self._d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/confirm"]')
        ele_confirm = x_confirm.get()
        return ele_confirm, ele_confirm.attrib.get('enabled')


class BCMTransferPwdKeyboard:

    _d: u2.Device
    _source: str
    _keyboard_xpath: str

    def __init__(self, d: u2.Device, parent_xpath, source: str = None):
        self._d = d
        self._source = d.dump_hierarchy() if source is None else source

        x_keyboard = d.xpath(parent_xpath, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        _kb_node = x_keyboard.get()
        self._keyboard_xpath = _kb_node.get_xpath()
        pos_xpath = [
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit0"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit3"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit6"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit1"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit4"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit7"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit2"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit5"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit8"]',
            '//*[@resource-id="com.bankcomm.Bankcomm:id/btnPwdDigit9"]',
        ]
        with io.BytesIO(d.screenshot(format='raw')) as _image:
            x, y, w, h = _kb_node.rect
            num_len = len(pos_xpath)
            recognize = RecognizeNumber(_image, x, y, w, h, num_len)
            pos_nums = recognize.image_str()[:num_len]
            self._num_xpath = dict([(pos_nums[_i], pos_xpath[_i]) for _i in range(len(pos_nums))])
            if len(self._num_xpath) != num_len:
                raise BotParseError(f'交易密码识别结果不匹配: {pos_nums}')

    def _xpath_child(self, _xpath):
        return self._d.xpath(self._keyboard_xpath, self._source).child(_xpath)

    def input(self, text: str, interval: float = None):
        if not text.isdigit():
            raise BotRunningError(f'不支持交易密码含非数字字符:{text}')
        if text not in self._num_xpath:
            raise BotRunningError(f'交易密码未识别字符:{text}', is_stop=True)

        _xpath = self._num_xpath[text]
        self._xpath_child(_xpath).click()

        if interval is not None:
            self._d.sleep(interval)

    def input_delete(self):
        self._xpath_child(f'//*[@resource-id="com.bankcomm.Bankcomm:id/digitkeypad_delete_auto_commit"]').click()
