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

    @staticmethod
    def amount_fen(amount: Union[float, str]) -> int:
        return amount_to_fen(amount)

    @staticmethod
    def amount_yuan(amount: Union[int, str]) -> float:
        return amount_to_yuan(amount)

    @staticmethod
    def amount_yuan_str(amount: Union[int, str]) -> str:
        return amount_to_yuan_str(amount)

    @staticmethod
    def format_time(dt: datetime):
        return format_datetime(dt)

    @staticmethod
    def is_match_num_mask(str_mask: str, match_target: str, masks=None):
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
        return BotHelper.is_match_num_mask(card_mask, card_original)

    @staticmethod
    def is_match_card_num_tail(card_tail: str, card_original: str):
        if not card_tail:
            return False
        return BotHelper.is_match_card_num('*' + card_tail, card_original)

    @staticmethod
    def is_last_trans(trans: Transaction, last_trans: Transaction, start_time: datetime = None):
        trans_time = DateTimeHelper.to_datetime(trans.time)
        if start_time is not None and start_time > trans_time:
            return True
        if last_trans is None:
            return False
        if DateTimeHelper.to_datetime(last_trans.time) > trans_time:
            return True
        return trans.is_same_trans(last_trans)

    @staticmethod
    def is_transfer_receipt(receipt: Receipt, transferee: Transferee):

        return (transferee is not None
                and receipt.name == transferee.holder
                and receipt.amount == transferee.amount
                and (receipt.postscript == transferee.postscript if transferee.postscript else True)
                and receipt.customerAccount == transferee.account)

    @staticmethod
    def sort_trans_list(trans_list: List[Transaction]):
        if trans_list is None:
            return None
        return sorted(trans_list, reverse=True, key=lambda t: t.time)

    @staticmethod
    def sort_receipt_list(trans_list: List[Receipt]):
        if trans_list is None:
            return None
        return sorted(trans_list, reverse=True, key=lambda t: t.time)

    @staticmethod
    def get_sms_code(sms_code_func: Callable[[], str]):
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
