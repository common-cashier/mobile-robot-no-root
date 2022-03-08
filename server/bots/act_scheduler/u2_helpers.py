import base64
from typing import List, Union, Optional

import uiautomator2 as u2

from server.bots.act_scheduler.bot_exceptions import BotRunningError, BotParseError

__all__ = ['DeviceHelper', 'XPathHelper']


class DeviceHelper:
    # 是否可用 fastInput，None 未知，True 可用，False 不可用
    __can_fastinput: Optional[bool] = None

    @staticmethod
    def _can_fastinput(d: u2.Device):
        if DeviceHelper.__can_fastinput is not None:
            return DeviceHelper.__can_fastinput

        try:
            d.wait_fastinput_ime(timeout=5)
            DeviceHelper.__can_fastinput = True
        except EnvironmentError:
            DeviceHelper.__can_fastinput = False
        return DeviceHelper.__can_fastinput

    @staticmethod
    def set_text(d: u2.Device, selector: Union[u2.xpath.XPathSelector, u2.xpath.XMLElement, str], text: str,
                 delay: float = 0, swipe_up: float = 0, close_kb=False, single_input=False):
        """聚焦节点并输入文本

        :param d: Device
        :param selector: 支持多种节点类型
        :param text: 输入文本
        :param delay: 点击节点后延迟输入文本
        :param swipe_up: 点击节点后向上滑动比例，使用非fastinput输入时，元素可能会被遮挡
        :param close_kb: 输入完成后是否关闭键盘
        :param single_input: 文本是否单个字符输入
        """
        if isinstance(selector, u2.xpath.XPathSelector):
            selector.click()
        elif isinstance(selector, u2.xpath.XMLElement):
            selector.click()
        elif isinstance(selector, str):
            d.xpath(selector).click()
        else:
            raise BotRunningError(f'不支持 {selector} 节点类型输入文本')
        if delay > 0:
            d.sleep(delay)
        if swipe_up > 0:
            d.swipe_ext(direction='up', scale=swipe_up)
        DeviceHelper.send_keys(d=d, text=text, close_kb=close_kb, single_input=single_input)

    @staticmethod
    def send_keys(d: u2.Device, text: str, close_kb=False, single_input=False):
        """输入文本

        :param d: Device
        :param text: 输入文本
        :param close_kb: 输入完成后是否关闭键盘
        :param single_input: 文本是否单个字符输入
        """
        input_texts = [text] if not single_input else [_t for _t in text]
        # 检查输入键盘类型，使用缓存。避免部分机型无法切换输入法
        can_fastinput = DeviceHelper._can_fastinput(d)
        if can_fastinput:
            [d.send_keys(_t) for _t in input_texts]
        else:
            # 同一文本节点单独输入时，会清空之前内容。仅对多个文本框自动切换时生效(例如:短信验证码)
            [d(focused=True).set_text(_t) for _t in input_texts]
        # 关闭键盘，点击返回
        if close_kb:
            DeviceHelper.press_back(d)

    @staticmethod
    def is_installed_pkg(d: u2.Device, package_name: str):
        return package_name in d.app_list(package_name)

    @staticmethod
    def is_running_pkg(d: u2.Device, package_name: str):
        return package_name in d.app_list_running()

    @staticmethod
    def is_current_pkg(d: u2.Device, package_name: str):
        return DeviceHelper.current_package(d) == package_name

    @staticmethod
    def current_package(d: u2.Device):
        pkg_name = d.app_current().get('package')
        return pkg_name if pkg_name else d.info.get('currentPackageName')

    @staticmethod
    def current_activity(d: u2.Device):
        return d.app_current().get('activity')

    @staticmethod
    def is_activity(d: u2.Device, activity: str):
        return DeviceHelper.current_activity(d) == activity

    @staticmethod
    def is_activity_contains(d: u2.Device, activity: str):
        return activity in DeviceHelper.current_activity(d)

    @staticmethod
    def is_in_activity(d: u2.Device, activities: List[str]):
        return DeviceHelper.current_activity(d) in activities

    @staticmethod
    def swipe_up_until(d: u2.Device, win_height: int, move_height: float) -> bool:
        had_move = False  # move once will be True
        max_move = win_height / float(2)  # center height
        while move_height > 0:
            # print(f'swipe_up_until - remain: {move_height}')
            move = min(max_move, move_height)
            scale = move / float(max_move)
            if scale < 0.03:
                # print(f'swipe_up_until - ignore swipe: {move}/{max_move}')
                break
            else:
                had_move = True

            # list_ele.swipe('up', scale)
            d.swipe_ext('up', scale)
            move_height -= move
        return had_move

    @staticmethod
    def press_back(d: u2.Device):
        d.press('back')

    @staticmethod
    def orientation_natural(d: u2.Device):
        d.set_orientation("n")

    @staticmethod
    def click_ele_position(d: u2.Device, ele: u2.xpath.XMLElement, count: int, click_index: int, direction='x'):
        if count < 1:
            raise BotRunningError('[节点位置点击] 切割数量 不能小于1')
        if click_index < 1:
            raise BotRunningError('[节点位置点击] 点击索引不能小于1，索引从1开始')
        if click_index > count:
            raise BotRunningError('[节点位置点击] 点击索引不能大于 切割数量')
        if direction not in ['x', 'y']:
            raise BotRunningError('[节点位置点击] 点击方向只能为 x 或 y')

        lx, ly, width, height = ele.rect
        if direction == 'x':
            each_width = width / float(count)
            btn_x_center = each_width * (click_index - 0.5)
            btn_y_center = height * 0.5
        else:
            each_height = height / float(count)
            btn_x_center = width * 0.5
            btn_y_center = each_height * (click_index - 0.5)

        click_x = lx + btn_x_center
        click_y = ly + btn_y_center
        print(f'[节点位置点击]: {click_x}, {click_y}, {ele.bounds}')
        d.click(click_x, click_y)

    @staticmethod
    def input_correct(d: u2.Device, _xpath: str, text: str, hierarchy_func=None, ignore_str=' '):
        # 保证卡号输入正确，因之前有输入卡号时，再次输入时可能会清空失败，需要多次清空才生效
        retry_limit = 5
        # 清空一次即可，避免h5中placeholder不能清除
        success, had_clear = False, False
        while retry_limit >= 0:
            retry_limit -= 1
            dump_source = d.dump_hierarchy() if hierarchy_func is None else hierarchy_func(d=d)
            x_input = d.xpath(_xpath, dump_source)
            if not x_input.exists:
                raise BotParseError(f'[输入文本检查] 未找到节点 {_xpath}')
            exist_text = x_input.get_text()

            if exist_text.replace(ignore_str, '') == text:
                success = True
                break
            elif had_clear or exist_text == '':
                # x_input.set_text(text)
                DeviceHelper.set_text(d, x_input, text)
            else:
                # print(f'[输入文本检查] 清空已输入文本: {exist_text}')
                had_clear = True
                x_input.click()
                d.clear_text()
            # 过快会导致 dump 卡住
            d.sleep(1)
        if not success:
            raise BotRunningError('[输入文本检查] 重试次数过多')

    @staticmethod
    def close_kb(d: u2.Device):
        d.set_fastinput_ime(False)

    @staticmethod
    def input_close_kb(d: u2.Device, _selector: u2.xpath.XPathSelector, text: str):
        _selector.set_text(text)
        d.set_fastinput_ime(False)

    @staticmethod
    def input_clear(d: u2.Device, _xpath: str, hierarchy_func=None, ignore_str=' ', clear_func=None):
        # 保证卡号输入正确，因之前有输入卡号时，再次输入时可能会清空失败，需要多次清空才生效
        while True:
            dump_source = d.dump_hierarchy() if hierarchy_func is None else hierarchy_func(d=d)
            x_input = d.xpath(_xpath, dump_source)
            if not x_input.exists:
                raise BotParseError(f'[清空文本检查] 未找到节点 {_xpath}')
            exist_text = x_input.get_text()

            if not exist_text.replace(ignore_str, ''):
                break
            else:
                # print(f'[清空文本检查] 清空已输入文本: {exist_text}')
                if clear_func:
                    clear_func(text=exist_text)
                else:
                    x_input.click()
                    d.clear_text()
            # 过快会导致 dump 卡住
            d.sleep(1)

    @staticmethod
    def screenshot_base64(d: u2.Device):
        content = d.screenshot(format='raw')
        return str(base64.b64encode(content), "utf-8")

    @staticmethod
    def get_child_selector(d: u2.Device, p_xpath: str, child_xpath: str, _source=None) -> u2.xpath.XPathSelector:
        return d.xpath(p_xpath, _source).child(child_xpath)


class XPathHelper:
    """xpath 帮助类"""

    @staticmethod
    def get_first_child(d: u2.Device, parent_xpath: str, source: str = None):
        return d.xpath(parent_xpath, source).child('/*[1]')

    @staticmethod
    def get_all_texts(d: u2.Device, parent_xpath: str, source: str = None, filters=None) -> List[tuple[str, str]]:
        """获取 xpath 包含 text 或 content-desc 的所有子节点数据

        :return: list[tuple], item0 为子节点xpath，item1 为子节点文本
        """
        # 包含数据的所有子节点
        had_text_xpath = '//*[string-length(@text)>0 or string-length(@content-desc)>0]'
        nodes = d.xpath(parent_xpath, source).child(had_text_xpath).all()
        result = []
        for _n in nodes:
            text = _n.text or _n.attrib.get('content-desc') or ''
            if filters and text in filters:
                continue
            result.append((text, _n.get_xpath()))
        return result
