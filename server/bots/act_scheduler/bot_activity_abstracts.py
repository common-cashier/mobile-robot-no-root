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
    # 用于未知活动类型时，回退到上页继续查找
    Default = auto()
    Startup = auto()
    Guide = auto()
    # 用于过渡页面使用
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
    TransferResultTransition = auto()
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
        """重置 或 重新加载 页面结构"""
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
    """执行 Activity 配置"""

    def __init__(self, proxy: BotDeviceProxy = None):
        self.d_proxy = proxy


class BotActivityExecutor:
    """银行 Activity 执行类"""

    def __init__(self, name: str, activity_type: BotActivityType, act_config: BotActivityConfig = None):
        self.name = name
        self.activity_type = activity_type
        self.act_config = act_config

    def _exec_retry(self, name: str, retry_limit: int
                    , func: Callable[[], Any]
                    , interval_second: float = 1
                    , with_error=False) -> Any:
        """执行重试
        :return: None or 函数结果值
        """
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
        """记录日志"""
        full_msg = f'[{self.__class__.__name__}] - {msg}'
        if level is None:
            level = Level.APP
        common_log(full_msg, level, hide)

    def _dump_hierarchy(self, d: u2.Device, check_error=True):
        """加载结构，使用代理类检查页面是否有错误
        :param check_error: 是否检查错误，仅配置 act_config 代理时有效
        """

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
        """检查是否符合当前Activity，尽可能检测精准，避免loading或多页面重复内容"""
        pass

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        """执行当前Activity，功能操作中的流程最后步骤需要返回相关数据"""
        pass

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        """跳转到下个ActivityType，用于多个Activity间有依赖时触发
        1. 优先使用 click_exists 点击，避免页面有提示框时导致异常
        """
        pass

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        """跳转到上个ActivityType，用于多个Activity间有依赖时触发，或回退到主页"""
        ctx.d.press('back')  # default is back
        self._log('触发页面默认返回')
