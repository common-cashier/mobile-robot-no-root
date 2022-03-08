from datetime import datetime
import re

import uiautomator2 as u2

from server.bots.act_scheduler.u2_helpers import DeviceHelper

__all__ = ['BCMHelper']


class BCMHelper:

    @staticmethod
    def is_webview_done(d: u2.Device, source=None):
        # 有子节点时
        return d.xpath('//android.webkit.WebView/*', source).exists

    @staticmethod
    def get_title(d: u2.Device, source=None) -> [bool, str]:
        title = None
        # com.bankcomm.module.biz.webcontainer.BCMHtml5Activity
        # webview 标题
        x_title = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/webview_header_title"]', source)
        if x_title.exists:
            ele_title = x_title.get()
            title = ele_title.attrib['content-desc'] or ele_title.text
        # app 标题
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
        """
        中文日期时间 转换为 datetime 类型
        """

        def _cn_remove_ten(_s):
            # 去掉中文中的十(例如"三十一"转化为"三一")
            return _s[0] + _s[2] if len(_s) == 3 else _s

        def _num_remove_ten_zero(_s):
            # 去掉数字中的0(例如"十二"月转换为"102",只取"1"和"2")，(例如"二十"日转换为"210",只取"2"和"0")
            return _s[0] + _s[2] if len(_s) == 3 else _s

        # 例如: 二零二二年一月十日十八时五十五分三十七秒
        text_groups = re.match(r'(.+)年(.+)月(.+)[日|号](.+)[时|点](.+)分(.+)秒', text).groups()
        year = text_groups[0]
        month = text_groups[1]
        day = _cn_remove_ten(text_groups[2])
        hour = _cn_remove_ten(text_groups[3])
        minute = _cn_remove_ten(text_groups[4])
        second = _cn_remove_ten(text_groups[5])
        # year = text.split('年')[0]
        # month = text.split('年')[1].split('月')[0]
        # day = _cn_remove_ten(text.split('月')[1].split('日')[0])
        # hour = _cn_remove_ten(text.split('日')[1].split('时')[0])
        # minute = _cn_remove_ten(text.split('时')[1].split('分')[0])
        # second = _cn_remove_ten(text.split('分')[1].split('秒')[0])

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
        """
        中文 转换为 数字
        """
        cn_num = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        # 不符合中文的保留原字符
        return ''.join(str(cn_num[i] if i in cn_num else i) for i in text)

    @staticmethod
    def go_back(d: u2.Device, source=None):
        """
        优先点击顶部返回，避免键盘仍处于打开状态等
        """
        x_back = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/web_icon_left1"]', source)
        if x_back.exists:
            x_back.click()
            return True
        else:
            DeviceHelper.press_back(d)
            return False
