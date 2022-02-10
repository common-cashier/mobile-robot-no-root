import uiautomator2 as u2

__all__ = ['CMBCActivityWebView', 'CMBCHelper']


class CMBCActivityWebView:
    @staticmethod
    def get_title(d: u2.Device, source=None) -> [bool, str]:
        x_title = d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/tv_title"]', source)
        if x_title.exists:
            ele_title = x_title.get()
            return True, ele_title.attrib['content-desc'] or ele_title.text
        return False, None

    @staticmethod
    def is_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = CMBCActivityWebView.get_title(d, source)
        return title in title_real if result and title else False

    @staticmethod
    def is_eq_title(d: u2.Device, source, title: str) -> bool:
        result, title_real = CMBCActivityWebView.get_title(d, source)
        return title == title_real if result and title else False


class CMBCHelper:
    @staticmethod
    def convert_amount(text: str) -> float:
        return float(text.replace('￥', '').replace(' ', '').replace(',', ''))

    @staticmethod
    def trim_none(text: str):
        return text if text != '暂无数据' else ''

    @staticmethod
    def get_card_no(text: str) -> str:
        return text.replace(' ', '')

    @staticmethod
    def get_child_ele(d: u2.Device, _source, card_xpath: str, child_xpath: str):
        return d.xpath(card_xpath, _source).child(child_xpath)
