import enum
from typing import Optional

import uiautomator2 as u2

from server.bots.act_scheduler.bot_exceptions import BotRunningError, BotParseError

__all__ = ['HRBNumberKeyboard', 'HRBLoginPwdKeyboard', 'HRBTransferPwdKeyboard']


@enum.unique
class KeyboardType(enum.IntEnum):
    LETTER_LOWER = 1,
    LETTER_UPPER = 2,
    DIGIT = 4,


class HRBNumberKeyboard:
    """数字键盘处理(收款账号、转账金额等)"""

    def __init__(self, d: u2.Device, source: str = None):
        parent_xpath = '//*[@resource-id="com.yitong.hrb.people.android:id/btn_confirm"]/../..'
        d.xpath(parent_xpath, source).wait(20)
        x_keyboard = d.xpath(parent_xpath, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        self._d = d
        self._source = d.dump_hierarchy() if source is None else source
        self._keyboard_xpath = x_keyboard.get().get_xpath()
        # 先清空现有文本
        self.clear()

    def _xpath_child(self, _xpath):
        return self._d.xpath(self._keyboard_xpath, self._source).child(_xpath)

    def _dump(self):
        self._source = self._d.dump_hierarchy()

    def input(self, text: str, interval: float = None, has_point=False):
        if text.isdigit():
            # com.yitong.hrb.people.android:id/btn_five
            self._xpath_child(
                f'//*[contains(@resource-id,"com.yitong.hrb.people.android:id/btn_")][@text="{text}"]').click()
        elif text == '.' and has_point:
            self._xpath_child(
                f'//*[@resource-id="com.yitong.hrb.people.android:id/btn_point"]').click()
        else:
            raise BotRunningError(f'不支持非数字字符: {text}')

        if interval is not None:
            self._d.sleep(interval)

    def delete(self):
        self._xpath_child('//*[@resource-id="com.yitong.hrb.people.android:id/btn_del"]').click()

    def clear(self):
        # 60,000
        exist_text = self._xpath_child('//*[@resource-id="com.yitong.hrb.people.android:id/digitalText"]').get_text()
        [self.delete() for _ in exist_text]

    def close(self):
        self._xpath_child('//*[@resource-id="com.yitong.hrb.people.android:id/btn_confirm"]').click()

    def check(self, text: str):
        self._dump()
        exist_text = self._xpath_child('//*[@resource-id="com.yitong.hrb.people.android:id/digitalText"]').get_text()
        return exist_text == text


class HRBLoginPwdKeyboard:
    """登录密码键盘处理"""
    _xpath_parent_number = '//android.widget.Button[@text="ABC"]/../..'
    _xpath_parent_alpha = '//android.widget.Button[@text="哈尔滨银行安全键盘"]/../..'
    _xpath_shift_alpha = '//*[@text="哈尔滨银行安全键盘"]/../../*[last()-1]/*[1]'
    _xpath_delete_alpha = '//*[@text="哈尔滨银行安全键盘"]/../../*[last()-1]/*[last()]'
    _xpath_close_alpha = '//*[@text="哈尔滨银行安全键盘"]/../*[@text="完成"]'

    def __init__(self, d: u2.Device, source: str = None):
        # 等待20秒键盘加载完成
        for _ in range(20):
            _source = d.dump_hierarchy()
            if d.xpath(self._xpath_parent_number, _source).exists \
                    or d.xpath(self._xpath_parent_alpha, _source).exists:
                break
            d.sleep(1)

        self._d = d
        self._source = d.dump_hierarchy() if source is None else source
        # 打开键盘时会还原之前状态
        self._current_type = self._recognize()
        self._last_type = self._current_type

    def _get_number_xpath(self, text: str):
        return f'{self._xpath_parent_number}//android.widget.Button[@text="{text}"]'

    def _get_alpha_xpath(self, text: str):
        return f'{self._xpath_parent_alpha}//android.widget.Button[@text="{text}"]'

    def _recognize(self):
        xpath_type = {
            KeyboardType.DIGIT: self._get_number_xpath('1'),
            KeyboardType.LETTER_LOWER: self._get_alpha_xpath('a'),
            KeyboardType.LETTER_UPPER: self._get_alpha_xpath('A'),
        }
        for t, x in xpath_type.items():
            if self._d.xpath(x, self._source).exists:
                return t
        raise BotRunningError('未识别到键盘类型')

    def _dump(self):
        self._source = self._d.dump_hierarchy()

    def _xpath_node(self, _xpath, use_source=True):
        # 输入字符时，切换大小写或数字时，切换可能会有延迟，固不采用缓存
        _source = self._source if use_source else None
        if not self._d.xpath(_xpath, _source).exists:
            print(f'不存在节点: {_xpath}')
        return self._d.xpath(_xpath, _source)

    def _switch_keyboard_type(self, target_type: KeyboardType):
        if self._current_type & target_type == target_type:
            return
        while self._current_type & target_type != target_type:
            switched_type: Optional[KeyboardType] = None  # None is not switch

            # 字母切换为数字
            if target_type & KeyboardType.DIGIT and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._xpath_node(self._get_alpha_xpath('123')).click()
                switched_type = KeyboardType.DIGIT
            # 字母切换大小写
            elif (target_type & KeyboardType.LETTER_LOWER or target_type & KeyboardType.LETTER_UPPER) and (
                    self._current_type & KeyboardType.LETTER_LOWER or self._current_type & KeyboardType.LETTER_UPPER):
                self._xpath_node(self._xpath_shift_alpha).click()
                # 小写切换大写时，需点两次表示一直大写输入
                if target_type & KeyboardType.LETTER_UPPER:
                    self._d.sleep(0.2)
                    self._dump()
                    self._xpath_node(self._xpath_shift_alpha).click()

                switched_type = target_type
            # 数字切换为字母，最后执行，保证字母和数字会同时显示
            elif self._current_type & KeyboardType.DIGIT and (
                    target_type == KeyboardType.LETTER_LOWER or target_type == KeyboardType.LETTER_UPPER):
                self._xpath_node(self._get_number_xpath('ABC')).click()
                # 还原之前字母类型
                switched_type = self._last_type

            if switched_type is not None:
                self._last_type = self._current_type
                self._current_type = switched_type
                self._dump()
            else:
                raise BotParseError('切换键盘类型失败')

    def input(self, text: str, interval: float = None):
        if text.islower():
            self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
            self._xpath_node(self._get_alpha_xpath(text)).click()
        elif text.isupper():
            self._switch_keyboard_type(KeyboardType.LETTER_UPPER)
            self._xpath_node(self._get_alpha_xpath(text)).click()
        elif text.isdigit():
            self._switch_keyboard_type(KeyboardType.DIGIT)
            self._xpath_node(self._get_number_xpath(text)).click()
        else:
            raise BotRunningError(f'不支持密码含特殊字符:{text}')

        if interval is not None:
            self._d.sleep(interval)

    def close(self):
        self._switch_keyboard_type(KeyboardType.LETTER_LOWER)
        self._xpath_node(self._xpath_close_alpha).click()


class HRBTransferPwdKeyboard:
    """转账密码处理"""

    def __init__(self, d: u2.Device, parent_xpath: str = None, source: str = None):
        d.xpath(parent_xpath, source).wait(20)
        x_keyboard = d.xpath(parent_xpath, source)
        if not x_keyboard.exists:
            raise BotParseError('未找到 键盘 节点')

        self._d = d
        self._source = d.dump_hierarchy() if source is None else source
        self._keyboard_xpath = x_keyboard.get().get_xpath()

    def _xpath_child(self, _xpath):
        return self._d.xpath(self._keyboard_xpath, self._source).child(_xpath)

    def input(self, text: str, interval: float = None):
        if text.isdigit():
            self._xpath_child(
                f'//android.widget.Button[@text="{text}"]').click()
        else:
            raise BotRunningError(f'不支持非数字字符: {text}')

        if interval is not None:
            self._d.sleep(interval)

    def close(self):
        self._xpath_child('//*[@text="完成"]').click()
