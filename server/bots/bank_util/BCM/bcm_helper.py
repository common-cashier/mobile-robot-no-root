from datetime import datetime
import re

import uiautomator2 as u2

from server.bots.act_scheduler.u2_helpers import DeviceHelper

__all__ = ['BCMHelper']


class BCMHelper:

    @staticmethod
    def is_webview_done(d: u2.Device, source=None):
        return d.xpath('//android.webkit.WebView/*', source).exists

    @staticmethod
    def get_title(d: u2.Device, source=None) -> [bool, str]:
        title = None
        x_title = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/webview_header_title"]', source)
        if x_title.exists:
            ele_title = x_title.get()
            title = ele_title.attrib['content-desc'] or ele_title.text
        x_title = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/title"]', source)
        if x_title.exists:
            ele_title = x_title.get()
            title = ele_title.attrib['content-desc'] or ele_title.text

        return (True if title else False), title

    @staticmethod
    def is_eq_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = BCMHelper.get_title(d, source)
        return title == title_real if result and title else False

    @staticmethod
    def is_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = BCMHelper.get_title(d, source)
        return title in title_real if result and title else False

    @staticmethod
    def convert_amount(text: str) -> float:
        return float(text.replace('￥', '').replace(' ', '').replace(',', '').replace('元', ''))

    @staticmethod
    def get_card_no(text: str) -> str:
        return text.replace(' ', '').replace('尾', '*').replace('号', '*')

    @staticmethod
    def cn_to_datetime(text: str):

        def _cn_remove_ten(_s):
            return _s[0] + _s[2] if len(_s) == 3 else _s

        def _num_remove_ten_zero(_s):
            return _s[0] + _s[2] if len(_s) == 3 else _s

        text_groups = re.match(r'(.+)年(.+)月(.+)[日|号](.+)[时|点](.+)分(.+)秒', text).groups()
        year = text_groups[0]
        month = text_groups[1]
        day = _cn_remove_ten(text_groups[2])
        hour = _cn_remove_ten(text_groups[3])
        minute = _cn_remove_ten(text_groups[4])
        second = _cn_remove_ten(text_groups[5])

        cn_num = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        year = ''.join(str(cn_num[i]) for i in year)
        month = _num_remove_ten_zero(''.join(str(cn_num[i]) for i in month))
        day = _num_remove_ten_zero(''.join(str(cn_num[i]) for i in day))
        hour = _num_remove_ten_zero(''.join(str(cn_num[i]) for i in hour))
        minute = _num_remove_ten_zero(''.join(str(cn_num[i]) for i in minute))
        second = _num_remove_ten_zero(''.join(str(cn_num[i]) for i in second))
        return datetime(year=int(year), month=int(month), day=int(day),
                        hour=int(hour), minute=int(minute), second=int(second))

    @staticmethod
    def cn_to_number(text: str):
        cn_num = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        return ''.join(str(cn_num[i] if i in cn_num else i) for i in text)

    @staticmethod
    def go_back(d: u2.Device, source=None):
        x_back = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/web_icon_left1"]', source)
        if x_back.exists:
            x_back.click()
            return True
        else:
            DeviceHelper.press_back(d)
            return False
