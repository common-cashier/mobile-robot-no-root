from datetime import datetime
from typing import List, Optional, Callable, Any, NoReturn
import threading
import traceback
import time

import uiautomator2 as u2

from server.models import BreakRes, Account, Transaction, Transferee, Receipt
from server.bots.common.common_report import (report_type_status, report_type_transactions, report_type_receipts,
                                              report_transfer_result)
from server import settings
from server.settings import log as common_log

from server.bots.act_scheduler import *

__all__ = ['BotBankHost']


class BotExecuteWrapper:
    """自动机执行封装"""

    def __init__(self, d: u2.Device, package_name: str, stop_callback: Callable[[BreakRes], NoReturn]):
        self.stop_callback = stop_callback
        self.d = d
        self.package_name = package_name
        self._cancel_signal = threading.Event()

    def cancel_exec(self):
        """取消执行，避免重试一直在运行"""
        if not self._cancel_signal.is_set():
            self._cancel_signal.set()

    def _check_running(self):
        """检查当前运行app，并做启动操作"""
        curr_package = self.d.app_current().get('package')
        if curr_package != self.package_name:
            common_log(f'检测到APP未运行，重新启动 `{self.package_name}`')
            self.d.app_start(self.package_name)
            self.d.app_wait(self.package_name)

    def _execute(self, name: str, func: Callable, retry_limit=0,
                 error_stop=True,
                 args: tuple[Any] = None,
                 kwargs: dict = None) -> [bool, Any]:
        """
        执行逻辑，重试，异常处理，状态上报
        1. 查询类重试处理，余额、流水、回单。
        2. 转账类，函数内部处理转账失败(根据异常类型，获取错误消息)
        3. 自定义异常终止 BotErrorBase(is_stop=True)
        4. 可重试异常(自定义、U2异常、系统异常)

        :param name: 执行名称
        :param func: 回调函数
        :param retry_limit: 重试次数
        :param error_stop: 重试后仍异常是否停止，True 异常上报，False 仅强制停止类异常上报
        :param args: 源函数参数
        :param kwargs: 源函数参数
        :return: [bool, Any] 是否执行成功，执行结果
        """

        is_stop_error, err_msg = False, ''
        retry_count = 0
        while retry_count <= retry_limit:
            if self._cancel_signal.is_set():
                common_log(f'[执行-{name}] 发现取消操作')
                return False, None
            if retry_count > 0:
                common_log(f'[执行-{name}] 第 {retry_count} 次重试')
                # 运行过程中 App 崩溃
                self._check_running()
                time.sleep(1)
            retry_count += 1

            try:
                result = func(*args, **kwargs)
                return True, result
            except BotSessionExpiredError as err:
                err_msg = f'会话超时，{err.full_msg()}'
                # 理论上不会在抛到此处，调度类已处理重登处理
                common_log(f'[执行-{name}] 会话超时，待重新登录 {err.full_msg()}')
            except BotErrorBase as err:
                err_msg = err.full_msg()
                _stack = f'\n堆栈:\n{traceback.format_exc()}'
                common_log(f'[执行-{name}] 自定义异常: 是否停止 {err.is_stop}, {err_msg} {_stack}')
                # 自定义异常，仅强制停止不做重试
                if err.is_stop:
                    is_stop_error = True
                    break
            except Exception as err:
                # 打印错误，方便排错
                err_msg = f'{repr(err)}'
                _stack = f'\n堆栈:\n{traceback.format_exc()}'
                # u2 的错误基类
                if isinstance(err, u2.exceptions.BaseError):
                    common_log(f'[执行-{name}] U2异常: {err_msg} {_stack}')
                else:
                    common_log(f'[执行-{name}] 未知异常: {err_msg} {_stack}')

        # 上报异常状态：停止类异常、重试后仍异常时并异常停止为True
        if is_stop_error or error_stop:
            break_res = BreakRes(is_break=True, break_reason=err_msg)
            self.stop_callback(break_res)
            # report_type_status(_account.alias, settings.Status.EXCEPTED, err_msg)
        # 执行失败，结果 None
        return False, None

    def exec_wrap(self, name: str, retry_limit=0, error_stop=True):
        """
        执行封装

        :param name: 执行名称
        :param retry_limit: 重试次数
        :param error_stop: 重试后仍异常是否停止，True 异常上报，False 仅强制停止类异常上报
        """

        def _inner(func):
            def _call(*args, **kwargs) -> tuple[bool, Any]:
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


class BotBankHost(object):
    """自动机银行宿主类"""
    # 中断参数
    _break_res: Optional[BreakRes] = None
    # 是否停止运行
    _is_stopped: bool = False
    # 上次查询余额信息
    _last_qry_balance: int = 0
    _last_qry_balance_time: Optional[datetime] = None
    # 上次查询流水信息
    _last_qry_trans_time: Optional[datetime] = None

    def __init__(self, d: u2.Device, package_name: str,
                 account: Account,
                 scheduler: BotActionScheduler):
        self._d = d
        self._package_name = package_name
        self._account = account
        self._scheduler = scheduler
        self._scheduler.account = self._account
        self._wrapper = BotExecuteWrapper(d, package_name,
                                          lambda *_args, **_kwargs: self._stop_callback(*_args, **_kwargs))
        self._sms_code = BotSmsCode()

    def can_run(self, workflow: settings.WorkFlow) -> bool:
        """是否可以运行工作流"""
        if workflow == settings.WorkFlow.START:
            return True
        # 如果有终止，无需继续处理。避免流程继续运行，直到检测 Break 彻底停止
        _break_res = self.break_workflow()
        if _break_res is not None and _break_res.is_break and workflow != settings.WorkFlow.BREAK:
            common_log(f'执行 {workflow} ，检测到已中断 {_break_res.break_reason}')
            return False
        return True

    def transaction(self, last_trans: Transaction):
        """抓流水"""

        @self._wrapper.exec_wrap(name='查询余额', retry_limit=5)
        def _qry_balance() -> int:
            account_result = self._scheduler.execute(ActionType.QueryAccount)
            return account_result.get('balance', 0)

        @self._wrapper.exec_wrap(name='查询流水', retry_limit=5)
        def _qry_transaction(_last_trans: Transaction) -> List[Transaction]:
            return self._scheduler.execute(ActionType.QueryTransaction,
                                           last_trans=_last_trans,
                                           max_query_count=30)

        # 查询余额间隔 30 秒
        if self._last_qry_balance_time is not None:
            interval_seconds = (datetime.now() - self._last_qry_balance_time).seconds
            remain_seconds = 30 - interval_seconds
            # 与上次查询间隔小于 120 秒，则不做查询流水
            if remain_seconds > 0:
                common_log(f'暂停 {remain_seconds} 秒后查询余额')
                self._d.sleep(remain_seconds)

        exec_result, balance = _qry_balance()
        if not exec_result:
            return
        common_log(f'余额: {balance}')
        self._last_qry_balance = balance
        self._last_qry_balance_time = datetime.now()

        # 相同余额时，查询流水间隔 120 秒
        if self._last_qry_trans_time is not None and self._last_qry_balance == balance:
            interval_seconds = (datetime.now() - self._last_qry_trans_time).seconds
            if interval_seconds < 120:
                return

        exec_result, trans_list = _qry_transaction(last_trans)
        if not exec_result:
            return
        common_log(f'流水列表: {trans_list}')
        self._last_qry_trans_time = datetime.now()
        # 上报数据，金额已经转换为分
        report_type_transactions(self._account.alias, balance, trans_list, is_fen_amount=True)

    def transfer(self):
        """转账"""

        # 转账错误后不强制停止，因转账未有重试
        @self._wrapper.exec_wrap(name='转账', retry_limit=0, error_stop=False)
        def _transfer(transferee: Transferee):
            """转账"""
            trans_result, trans_msg = False, '转账失败'
            try:
                trans_result, trans_msg = self._scheduler.execute(ActionType.Transfer,
                                                                  transferee=transferee,
                                                                  sms_code_func=self._sms_code.get_sms_code)
            except Exception as err:
                trans_result = False
                if isinstance(err, BotErrorBase):
                    trans_msg = err.full_msg()
                else:
                    trans_msg = f'转账处理异常: {repr(err)}'
                # 再继续抛异常，由外层继续处理
                raise
            finally:
                common_log(f'转账结果: 单号-{transferee.order_id}, 结果-{trans_result}, 消息-{trans_msg}')
                report_transfer_result(self._account.alias, transferee.order_id, trans_result, trans_msg)

        _transfer(settings.transferee)

    def receipt(self):
        """抓回单"""

        # 查询回单最多重试 1 次，不是必须结果，避免影响正常业务
        @self._wrapper.exec_wrap(name='查询回单', retry_limit=1)
        def _qry_receipt(last_transferee: Transferee) -> List[Receipt]:
            # 查询回单，查找上次转账匹配项，默认最多查2条
            return self._scheduler.execute(ActionType.QueryReceipt,
                                           last_transferee=last_transferee,
                                           max_query_count=2)

        exec_result, receipt_list = _qry_receipt(settings.transferee)
        if not exec_result:
            return
        common_log(f'回单列表: {receipt_list}')
        # 上报数据，金额已经转换为分
        report_type_receipts(self._account.alias, receipt_list, is_fen_amount=True)

    def input_sms(self, sms_msg: str):
        """输入短信验证码"""
        self._sms_code.set_sms_code(sms_msg)

    def stop(self):
        """停止运行"""
        self._wrapper.cancel_exec()
        self._is_stopped = True

    def break_workflow(self):
        """中断工作流"""
        if self._break_res and self._break_res.is_break:
            return self._break_res
        if self._is_stopped:
            return BreakRes(is_break=True, break_reason='程序已停止')
        return BreakRes()

    def _stop_callback(self, break_res: BreakRes):
        self._break_res = break_res
        report_type_status(self._account.alias, settings.Status.EXCEPTED, self._break_res.break_reason)
