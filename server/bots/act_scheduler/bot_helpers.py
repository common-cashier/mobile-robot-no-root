import re
import time
from datetime import datetime
from typing import List, Callable, Union

from server.models import Transaction, Receipt, Transferee, amount_to_fen, amount_to_yuan, amount_to_yuan_str, \
    format_datetime
from server.settings import log as common_log
from server.bots.act_scheduler.bot_exceptions import BotCategoryError, ErrorCategory
from server.common_helpers import DateTimeHelper

__all__ = ['BotHelper']


class BotHelper:
    """自动机公用帮助类"""

    @staticmethod
    def amount_fen(amount: Union[float, str]) -> int:
        """转换 元单位浮点型数值 > 分单位整型数值"""
        return amount_to_fen(amount)

    @staticmethod
    def amount_yuan(amount: Union[int, str]) -> float:
        """转换 分单位整形数值 > 元单位浮点型数值"""
        return amount_to_yuan(amount)

    @staticmethod
    def amount_yuan_str(amount: Union[int, str]) -> str:
        """转换 分单位整形数值 > 元单位字符串"""
        return amount_to_yuan_str(amount)

    @staticmethod
    def format_time(dt: datetime):
        """格式化时间字符串，后台接收格式"""
        return format_datetime(dt)

    @staticmethod
    def is_match_num_mask(str_mask: str, match_target: str, masks=None):
        """是否匹配数字掩码

        :param str_mask: 数字掩码字符串
        :param match_target: 匹配目标字符串
        :param masks: 掩码字符集
        """
        if not str_mask:
            return False

        masks = masks if masks else ['*', ' ']
        re_str = ''
        is_star = False
        for ch in str_mask:
            if ch in masks:
                is_star = True
            else:
                if is_star:
                    re_str += r'\d*'
                    is_star = False
                re_str += ch

        return re.match(re_str, match_target) is not None

    @staticmethod
    def is_match_card_num(card_mask: str, card_original: str):
        """是否匹配掩码卡号"""
        return BotHelper.is_match_num_mask(card_mask, card_original)

    @staticmethod
    def is_match_card_num_tail(card_tail: str, card_original: str):
        """是否匹配银行卡尾号类型掩码"""
        if not card_tail:
            return False
        return BotHelper.is_match_card_num('*' + card_tail, card_original)

    @staticmethod
    def is_last_trans(trans: Transaction, last_trans: Transaction, start_time: datetime = None):
        """是否为最后一条流水，无需继续查询(不含当前流水)"""
        trans_time = DateTimeHelper.to_datetime(trans.time)
        # 小于起始时间限制时
        if start_time is not None and start_time > trans_time:
            return True
        # 正常情况不会为 None
        if last_trans is None:
            return False
        # 小于最后一条流水时间。新卡时，最后一条流水仅返回时间字段
        if DateTimeHelper.to_datetime(last_trans.time) > trans_time:
            return True
        # 等于最后一条流水
        return trans.is_same_trans(last_trans)

    @staticmethod
    def is_transfer_receipt(receipt: Receipt, transferee: Transferee):
        """是否为转账收款人回单，无需继续查询(含当前回单)"""

        return (transferee is not None
                and receipt.name == transferee.holder
                and receipt.amount == transferee.amount
                # 有转账附言时，同时匹配
                and (receipt.postscript == transferee.postscript if transferee.postscript else True)
                and receipt.customerAccount == transferee.account)

    @staticmethod
    def sort_trans_list(trans_list: List[Transaction]):
        """排序流水列表"""
        if trans_list is None:
            return None
        # return trans_list.sort(reverse=True, key=lambda t: t.time)
        return sorted(trans_list, reverse=True, key=lambda t: t.time)

    @staticmethod
    def sort_receipt_list(trans_list: List[Receipt]):
        """排序回单列表"""
        if trans_list is None:
            return None
        return sorted(trans_list, reverse=True, key=lambda t: t.time)

    @staticmethod
    def get_sms_code(sms_code_func: Callable[[], str]):
        """轮询获取短信验证码"""
        limits, interval, counter = 20, 5, 0
        while counter <= limits:
            counter += 1
            common_log(msg=f'第 {counter} 次获取短信验证码')
            sms_code = sms_code_func()
            if sms_code:
                common_log(msg=f'获取短信验证码成功： {sms_code}')
                return sms_code
            time.sleep(interval)
        raise BotCategoryError(ErrorCategory.Data, '未获取到短信验证码')
