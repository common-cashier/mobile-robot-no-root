from datetime import datetime
import re

import uiautomator2 as u2

from server.bots.act_scheduler.u2_helpers import DeviceHelper

__all__ = ['PSBCHelper']


class PSBCHelper:

    @staticmethod
    def get_title(d: u2.Device, source=None) -> [bool, str]:
        title = None
        x_title = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/tvTopTextTitle"]', source)
        if x_title.exists:
            ele_title = x_title.get()
            title = ele_title.attrib['content-desc'] or ele_title.text

        return (True if title else False), title

    @staticmethod
    def is_eq_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = PSBCHelper.get_title(d, source)
        return title == title_real if result and title else False

    @staticmethod
    def is_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = PSBCHelper.get_title(d, source)
        return title in title_real if result and title else False

    @staticmethod
    def convert_amount(text: str) -> float:
        return float(text.replace('￥', '').replace(',', ''))

    @staticmethod
    def get_card_no(text: str) -> str:
        return text.replace(' ', '')

    @staticmethod
    def go_back(d: u2.Device, source=None):
        x_back = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/iv_back"]', source)
        x_webview_back = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/btnTopLeft"][@content-desc="返回"]', source)
        if x_back.exists:
            x_back.click()
            return True
        elif x_webview_back.exists:
            x_webview_back.click()
            return True
        else:
            DeviceHelper.press_back(d)
            return False
