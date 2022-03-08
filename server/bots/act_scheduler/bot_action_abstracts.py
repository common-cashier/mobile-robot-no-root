import enum

from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Callable
from server.models import Transaction, Account, Transferee
from server.common_helpers import DateTimeHelper

__all__ = ['ActionType', 'BotActionParameter']


@enum.unique
class ActionType(Enum):
    Default = auto(), '主页'  # 用于默认 App 主页
    Login = auto(), '登录'
    QueryAccount = auto(), '查询账户'
    QueryTransaction = auto(), '查询流水'
    Transfer = auto(), '转账'
    QueryReceipt = auto(), '查询回单'

    def __init__(self, _value: str, _description: str = ''):
        self._value_ = _value
        self._description_ = _description

    def __str__(self):
        return f'{self.name}, {self.description}'

    @property
    def description(self):
        return self._description_


class BotActionParameter:

    @staticmethod
    def get_account(**kwargs):
        """获取查询账户余额参数"""
        account: Account = kwargs.get('account')
        return account

    @staticmethod
    def get_query_trans(**kwargs):
        """获取查询流水参数"""
        last_trans: Transaction = kwargs.get('last_trans')
        max_count: int = kwargs.get('max_query_count', 30)  # 默认查询 30 条

        now = datetime.now()
        start_time: datetime = kwargs.get('start_time', now - timedelta(days=1))
        if last_trans:
            last_trans_time = DateTimeHelper.to_datetime(last_trans.time)
            start_time = last_trans_time if last_trans_time > start_time else start_time
        end_time: datetime = kwargs.get('end_time', now)
        return last_trans, max_count, start_time, end_time

    @staticmethod
    def get_transfer(**kwargs):
        """获取转账参数"""
        transferee: Transferee = kwargs.get('transferee')
        sms_code_func: Callable = kwargs.get('sms_code_func')
        return transferee, sms_code_func

    @staticmethod
    def get_query_receipt(**kwargs):
        """获取查询回单参数"""
        # last_receipt: Receipt = kwargs.get('last_receipt')
        # 最后一次转账信息，目前只抓取转账匹配的1条回单
        last_transferee: Transferee = kwargs.get('last_transferee')
        max_count: int = kwargs.get('max_query_count', 3)  # 默认查询 3 条
        return last_transferee, max_count
