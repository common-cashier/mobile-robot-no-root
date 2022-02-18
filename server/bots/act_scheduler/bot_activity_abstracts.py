import os
import time
import enum
from typing import Callable, Any
from enum import Enum, auto

import uiautomator2 as u2

from server.bots.act_scheduler.bot_exceptions import BotParseError
from server.common_helpers import DateTimeHelper
from server.models import Account
from server.settings import Level, log as common_log
from server.bots.act_scheduler.bot_filter import BotDeviceProxy

__all__ = ['BotActivityType', 'ActivityContext', 'ActivityCheckContext', 'ActivityExecuteContext', 'BotActivityConfig',
           'BotActivityExecutor']


@enum.unique
class BotActivityType(Enum):
    Default = auto()
    Startup = auto()
    Guide = auto()
    Transition = auto()
    Main = auto()
    Login = auto()
    QueryAccount = auto()
    QueryTrans = auto()
    QueryTransDetail = auto()
    Transfer = auto()
    TransferIndex = auto()
    TransferConfirm = auto()
    TransferVerify = auto()
    TransferResult = auto()
    QueryReceiptTransition = auto()
    QueryReceipt = auto()
    QueryReceiptDetail = auto()
    QueryReceiptDetailImage = auto()


class ActivityContext:
    _source: str
    _curr_activity: str
    _win_size_width: int = None
    _win_size_height: int = None

    def __init__(self, d: u2.Device, curr_activity: str = None, source: str = None):
        self.d = d
        self._curr_activity = curr_activity
        self._source = source

    @property
    def win_size_width(self):
        if not self._win_size_width:
            self.__init_win_size()
        return self._win_size_width

    @property
    def win_size_height(self):
        if not self._win_size_height:
            self.__init_win_size()
        return self._win_size_height

    def __init_win_size(self):
        self._win_size_width, self._win_size_height = self.d.window_size()

    @property
    def source(self):
        if not self._source:
            self._source = self.d.dump_hierarchy()
        return self._source

    @source.setter
    def source(self, value):
        self._source = value

    @property
    def current_activity(self):
        if not self._curr_activity:
            self._curr_activity = self.d.app_current().get('activity')
        return self._curr_activity

    @current_activity.setter
    def current_activity(self, value):
        self._curr_activity = value

    def reset(self, source: str = None, current_activity: str = None):
        self.source = source
        self.current_activity = current_activity


class ActivityCheckContext(ActivityContext):
    def __init__(self, d: u2.Device, curr_activity: str = None, source: str = None):
        super(ActivityCheckContext, self).__init__(d, curr_activity, source)


class ActivityExecuteContext(ActivityContext):
    def __init__(self, d: u2.Device, account: Account, curr_activity: str = None, source: str = None,
                 activity_type: BotActivityType = None):
        super(ActivityExecuteContext, self).__init__(d, curr_activity, source)
        self.activity_type = activity_type
        self.account = account


class BotActivityConfig:

    def __init__(self, proxy: BotDeviceProxy = None):
        self.d_proxy = proxy


class BotActivityExecutor:

    def __init__(self, name: str, activity_type: BotActivityType, act_config: BotActivityConfig = None):
        self.name = name
        self.activity_type = activity_type
        self.act_config = act_config

    def _exec_retry(self, name: str, retry_limit: int
                    , func: Callable[[], Any]
                    , interval_second: float = 1
                    , with_error=False) -> Any:
        while retry_limit > 0:
            func_result = func()
            if func_result:
                return func_result
            retry_limit -= 1
            if retry_limit > 0:
                self._log(f'[{name}] 重试剩余 {retry_limit} 次')
                time.sleep(interval_second)
        if with_error:
            raise BotParseError(f'{name}，加载失败')
        return None

    def _log(self, msg, level: Level = None, hide: bool = False):
        full_msg = f'[{self.__class__.__name__}] - {msg}'
        if level is None:
            level = Level.APP
        common_log(full_msg, level, hide)

    def _dump_hierarchy(self, d: u2.Device, check_error=True):

        if self.act_config and self.act_config.d_proxy is not None:
            return self.act_config.d_proxy.dump_hierarchy(d, check_error=check_error)
        else:
            return d.dump_hierarchy()

    def _save_screenshot_receipt(self, d: u2.Device, receipt_time, name: str):
        _dt = DateTimeHelper.to_datetime(receipt_time)
        self.__save_screenshot(d, 'receipt_record', f'{DateTimeHelper.to_str(_dt, "%Y%m%d_%H%M%S")}_{name}')

    def _save_screenshot_transfer(self, d: u2.Device, name: str):
        self.__save_screenshot(d, 'transfer_record', f'{DateTimeHelper.now_str("%Y%m%d_%H%M%S_%f")}_{name}')

    def __save_screenshot(self, d: u2.Device, dir_name: str, name: str):
        if dir_name not in os.listdir():
            self._log(f'创建子文件夹: {dir_name}')
            os.mkdir(dir_name)
        file_name = os.path.join(os.getcwd(), dir_name, f'{name}.png')
        d.screenshot(file_name)

    def check(self, ctx: ActivityCheckContext):
        pass

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        pass

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        pass

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        ctx.d.press('back')  # default is back
        self._log('触发页面默认返回')
