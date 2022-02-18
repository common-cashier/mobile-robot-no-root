import base64
from typing import List

import uiautomator2 as u2

from server.bots.act_scheduler.bot_exceptions import BotRunningError, BotParseError

__all__ = ['DeviceHelper', 'XPathHelper']


class DeviceHelper:
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
    def is_in_activity(d: u2.Device, activities: List[str]):
        return DeviceHelper.current_activity(d) in activities

    @staticmethod
    def swipe_up_until(d: u2.Device, win_height: int, move_height: float) -> bool:
        had_move = False  # move once will be True
        max_move = win_height / float(2)  # center height
        while move_height > 0:
            move = min(max_move, move_height)
            scale = move / float(max_move)
            if scale < 0.03:
                break
            else:
                had_move = True

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
        retry_limit = 5
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
                x_input.set_text(text)
            else:
                had_clear = True
                x_input.click()
                d.clear_text()
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
        while True:
            dump_source = d.dump_hierarchy() if hierarchy_func is None else hierarchy_func(d=d)
            x_input = d.xpath(_xpath, dump_source)
            if not x_input.exists:
                raise BotParseError(f'[清空文本检查] 未找到节点 {_xpath}')
            exist_text = x_input.get_text()

            if not exist_text.replace(ignore_str, ''):
                break
            else:
                if clear_func:
                    clear_func(text=exist_text)
                else:
                    x_input.click()
                    d.clear_text()
            d.sleep(1)

    @staticmethod
    def ele_set_text(d: u2.Device, ele: u2.xpath.XMLElement, text: str):
        ele.click()
        d.xpath.send_text(text)

    @staticmethod
    def screenshot_base64(d: u2.Device):
        content = d.screenshot(format='raw')
        return str(base64.b64encode(content), "utf-8")

    @staticmethod
    def get_child_selector(d: u2.Device, p_xpath: str, child_xpath: str, _source=None) -> u2.xpath.XPathSelector:
        return d.xpath(p_xpath, _source).child(child_xpath)


class XPathHelper:

    @staticmethod
    def get_first_child(d: u2.Device, parent_xpath: str, source: str = None):
        return d.xpath(parent_xpath, source).child('/*[1]')

    @staticmethod
    def get_all_texts(d: u2.Device, parent_xpath: str, source: str = None, filters=None) -> List[tuple[str, str]]:
        had_text_xpath = '//*[string-length(@text)>0 or string-length(@content-desc)>0]'
        nodes = d.xpath(parent_xpath, source).child(had_text_xpath).all()
        result = []
        for _n in nodes:
            text = _n.text or _n.attrib.get('content-desc') or ''
            if filters and text in filters:
                continue
            result.append((text, _n.get_xpath()))
        return result
