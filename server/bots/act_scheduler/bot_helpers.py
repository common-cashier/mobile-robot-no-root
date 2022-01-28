import time
import traceback
from datetime import datetime
from typing import List, Callable, Union, Any, NoReturn, Optional

import uiautomator2 as u2

from server.models import Transaction, Receipt, Transferee, amount_to_fen, amount_to_yuan, amount_to_yuan_str, \
    format_datetime
from server.settings import log as common_log
from server.bots.act_scheduler.bot_exceptions import BotCategoryError, ErrorCategory, BotSessionExpiredError, \
    BotErrorBase
from server.common_helpers import DateTimeHelper
from server.models import BreakRes


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
    def is_last_trans(trans: Transaction, last_trans: Transaction, start_time: datetime = None):
        """是否为最后一条流水，无需继续查询(不含当前流水)"""
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
        """是否为转账收款人回单，无需继续查询(含当前回单)"""

        return (transferee is not None
                and receipt.name == transferee.holder
                and receipt.amount == transferee.amount
                and (receipt.postscript == transferee.postscript if transferee.postscript else True)
                and receipt.customerAccount == transferee.account)

    @staticmethod
    def sort_trans_list(trans_list: List[Transaction]):
        """排序流水列表"""
        if trans_list is None:
            return None
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


class BotExecuteWrapper:
    """自动机执行封装"""

    def __init__(self, error_callback: Callable[[BreakRes], NoReturn]):
        self.error_callback = error_callback

    def _execute(self, name: str, func: Callable, retry_limit=0,
                 error_stop=True,
                 args: tuple[Any] = None,
                 kwargs: dict = None) -> [bool, Any]:

        is_stop_error, err_msg = False, ''
        retry_count = 0
        while retry_count <= retry_limit:
            if retry_count > 0:
                common_log(f'[执行-{name}] 第 {retry_count} 次重试')
                time.sleep(1)
            retry_count += 1

            try:
                result = func(*args, **kwargs)
                return True, result
            except BotSessionExpiredError as err:
                err_msg = f'会话超时，{err.full_msg()}'
                common_log(f'[执行-{name}] 会话超时，待重新登录 {err.full_msg()}')
            except BotErrorBase as err:
                err_msg = err.full_msg()
                _stack = f'\n堆栈:\n{traceback.format_exc()}'
                common_log(f'[执行-{name}] 自定义异常: 是否停止 {err.is_stop}, {err_msg} {_stack}')
                if err.is_stop:
                    is_stop_error = True
                    break
            except Exception as err:
                err_msg = f'{repr(err)}'
                _stack = f'\n堆栈:\n{traceback.format_exc()}'
                if isinstance(err, u2.exceptions.BaseError):
                    common_log(f'[执行-{name}] U2异常: {err_msg} {_stack}')
                else:
                    common_log(f'[执行-{name}] 未知异常: {err_msg} {_stack}')

        if is_stop_error or error_stop:
            break_res = BreakRes(is_break=True, break_reason=err_msg)
            self.error_callback(break_res)
        return False, None

    def exec_wrap(self, name: str, retry_limit=0, error_stop=True):

        def _inner(func):
            def _call(*args, **kwargs):
                return self._execute(name=name, func=func, retry_limit=retry_limit, error_stop=error_stop,
                                     args=args, kwargs=kwargs)

            return _call

        return _inner


class BotSmsCode:
    """自动机短信"""
    _sms_code: Optional[str] = None

    def get_sms_code(self):
        """转账过程中回调获取验证码"""
        if self._sms_code:
            try:
                return self._sms_code
            finally:
                self._sms_code = None  # 读取后清空
        return None

    def set_sms_code(self, code: str):
        """外部通知验证码"""
        self._sms_code = code
