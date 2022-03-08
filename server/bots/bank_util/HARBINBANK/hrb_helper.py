from typing import List

import uiautomator2 as u2

from server.bots.act_scheduler.u2_helpers import DeviceHelper
from server.common_helpers import StrHelper

__all__ = ['HRBHelper']


class HRBHelper:

    @staticmethod
    def get_title(d: u2.Device, source=None) -> [bool, str]:
        title = None
        x_title = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/ivLogo"]', source)
        if x_title.exists:
            ele_title = x_title.get()
            title = ele_title.attrib['content-desc'] or ele_title.text

        return (True if title else False), title

    @staticmethod
    def is_eq_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = HRBHelper.get_title(d, source)
        return title == title_real if result and title_real else False

    @staticmethod
    def is_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = HRBHelper.get_title(d, source)
        return title in title_real if result and title_real else False

    @staticmethod
    def any_title(d: u2.Device, source, titles: List[str]) -> bool:
        result, title_real = HRBHelper.get_title(d, source)
        return StrHelper.any_contains(titles, title_real) if result and title_real else False

    @staticmethod
    def convert_amount(text: str) -> float:
        return float(text.replace('￥', '').replace(',', '').replace('元', ''))

    @staticmethod
    def get_card_no(text: str) -> str:
        return text.replace(' ', '')

    @staticmethod
    def go_back(d: u2.Device, source=None):
        x_back = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/iv_back_login"]', source)
        x_webview_back = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/iv_back"]', source)
        if x_back.exists:
            x_back.click()
            return True
        elif x_webview_back.exists:
            x_webview_back.click()
            return True
        else:
            DeviceHelper.press_back(d)
            return False
