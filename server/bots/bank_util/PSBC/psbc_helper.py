import uiautomator2 as u2

from server.bots.act_scheduler.u2_helpers import DeviceHelper

__all__ = ['PSBCHelper']


class PSBCHelper:

    @staticmethod
    def get_title(d: u2.Device, source=None) -> [bool, str]:
        title = None
        # com.yitong.mbank.psbc.utils.webview.WebViewActivity
        # webview 标题
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
        """优先点击顶部返回，避免键盘仍处于打开状态等"""
        x_back = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/iv_back"]', source)
        # [@content-desc="返回"]
        x_webview_back = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/btnTopLeft"]', source)
        if x_back.exists:
            x_back.click()
            return True
        elif x_webview_back.exists:
            x_webview_back.click()
            return True
        else:
            DeviceHelper.press_back(d)
            return False
