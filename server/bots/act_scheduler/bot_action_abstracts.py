import enum

from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Callable
from server.models import Transaction, Receipt, Account, Transferee
from server.common_helpers import DateTimeHelper


@enum.unique
class ActionType(Enum):
    Default = auto()  # 用于默认 App 主页
    Login = auto()
    QueryAccount = auto()
    QueryTransaction = auto()
    Transfer = auto()
    QueryReceipt = auto()


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
        last_trans_time = DateTimeHelper.to_datetime(last_trans.time)
        if last_trans_time > start_time:
            start_time = last_trans_time
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
        last_transferee: Transferee = kwargs.get('last_transferee')
        max_count: int = kwargs.get('max_query_count', 3)  # 默认查询 3 条
        return last_transferee, max_count
