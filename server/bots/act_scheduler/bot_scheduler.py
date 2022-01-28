import threading
from typing import Dict, List

import uiautomator2 as u2

from server.models import Account
from server.settings import log as common_log
from server.common_helpers import RetryHelper
from server.bots.act_scheduler.bot_activity_abstracts import BotActivityType, ActivityCheckContext, \
    ActivityExecuteContext, BotActivityExecutor
from server.bots.act_scheduler.bot_action_abstracts import ActionType
from server.bots.act_scheduler.bot_exceptions import *
from server.bots.act_scheduler.bot_filter import BotDeviceProxy
from server.bots.act_scheduler.u2_helpers import DeviceHelper


class BotActionWatcher:
    def __init__(self):
        pass

    def check(self, ctx: ActivityCheckContext) -> bool:
        """
        监听检查
        :return: 是否检查到错误，需要外层重新检查
        """
        pass


class BotConfig:
    """执行配置，Action 和 Activity 流程"""

    def __init__(self, activity_executors: List[BotActivityExecutor], action_processes: Dict[ActionType, List[str]],
                 watcher: BotActionWatcher = None, proxy: BotDeviceProxy = None):
        self.activity_executors = activity_executors
        self.action_processes = action_processes
        self.watcher = watcher
        self.d_proxy = proxy


class _ActionTargetResult:
    """调度执行目标结果"""

    def __init__(self, executed=False, need_login=False, activity_executor: BotActivityExecutor = None,
                 ctx_execute: ActivityExecuteContext = None):
        self.ctx_execute = ctx_execute
        self.activity_executor = activity_executor
        self.need_login = need_login
        self.executed = executed


class BotActionScheduler:
    """执行调度，根据配置 Action 流程跳转，支持刷新、自动重登处理"""

    def __init__(self, d: u2.Device, bot_config: BotConfig, account: Account):
        self.d = d
        self.bot_config = bot_config
        self.account = account
        self._lock = threading.Lock()

    def execute(self, action_type: ActionType, *args, **kwargs):
        """
        执行目标 ActionType
        根据当前运行 Activity 、目标 ActionType 的执行流程，识别需要回退或前进处理，如果不在已识别页面中，则调用`app返回`后再查找
        :param action_type: 目标 Action
        :param args: 动态参数，页面 execute 自解析
        :param kwargs: 动态参数，页面 execute 自解析
        :return: True 或 execute 结果值 表示执行成功, 否则执行失败
        """

        # self._log(f'准备执行 ActionType :{action_type}')
        self._lock.acquire(True)
        try:
            self._log(f'开始执行 {action_type}')

            executed, need_login = False, False
            execute_action_type = action_type  # 默认为需要执行 ActionType
            # 执行 Action 重试次数，防止网络问题，导致页面无变化，一直重试
            retry_action_type, retry_limit, retry_count = None, 3, 0
            login_retry_limit = 2  # 登录重试次数
            force_refresh = True  # 执行流程时强制刷新页面

            while not executed:
                process: List[str] = self.bot_config.action_processes.get(execute_action_type)
                if not process:
                    raise BotStopError(f'未找到 Action [{execute_action_type}] 的执行流程')

                if retry_action_type == execute_action_type:
                    retry_count += 1
                    if retry_count >= retry_limit:
                        raise BotParseError(f'执行多次，仍停留在页面 {retry_action_type}')
                else:
                    retry_count = 0
                    retry_action_type = execute_action_type

                try:
                    action_result = self._exec_action_process(execute_action_type, process, refresh=force_refresh)
                    force_refresh = True  # 使用后设置为 True，避免多 Action 切换执行
                    ctx_execute = action_result.ctx_execute
                    executor = action_result.activity_executor
                    need_login = action_result.need_login  # 执行页面过程中，检测到跳转到登录页时
                    executed = action_result.executed  # 已经执行过页面，例如已登录后，仍执行登录 Action 时

                    if not need_login and not executed:
                        if execute_action_type == action_type:
                            # 等于原目标 Action 时，使用参数
                            return executor.execute(ctx=ctx_execute, *args, **kwargs)
                        elif execute_action_type == ActionType.Login:
                            # 目前仅有登录会阻碍原操作执行，登录不依赖动态参数
                            executor.execute(ctx=ctx_execute)
                            execute_action_type = action_type  # 执行过后，恢复原操作执行
                            self._log(f'登录后，还原目标操作继续执行: {action_type}')
                            continue
                        else:
                            self._log(f'未知处理情况 {execute_action_type}， {action_type}')
                            raise BotStopError('未知处理情况，需检查是否有 bug')

                except BotSessionExpiredError as err:
                    self._log(f'会话超时，待重新登录 {err.msg}')
                    need_login = True
                except BotErrorBase as err:
                    # 转账类不做重试
                    if BotErrorHelper.is_retryable(err) and execute_action_type != ActionType.Transfer:
                        continue  # 重试当前操作
                    else:
                        raise

                if need_login:
                    login_retry_limit -= 1
                    if login_retry_limit < 0:
                        raise BotStopError('登录多次后仍会话超时')
                    self._log('检测到需要重新登录')
                    execute_action_type = ActionType.Login
                    force_refresh = False  # 如果已经跳转到登录页，则无需刷新页面
        finally:
            self._log(f'执行完成 {action_type}')
            self._lock.release()

    def _exec_action_process(self, action_type: ActionType, process: List[str], refresh: bool = True):
        full_process = process.copy()

        had_change_activity = False  # 流程是否触发过，保证页面不会使用缓存页
        loop_limit = 60  # 循环检查次数限制，避免流程过于复杂或递归调用，包含错误检查，页面回退、页面进入等

        # 未检测到当前页面类型 返回再找直到限制，处于中间过渡页面时
        none_activity_limit, none_activity_counter = 5, 0
        # 上次页面停留重试
        last_activity_type = None
        last_activity_counter_retry, last_activity_counter = 5, 0

        ctx_check = ActivityCheckContext(self.d)
        ctx_execute = ActivityExecuteContext(self.d, self.account)
        target_executor = None
        executed = False
        need_login = False  # 执行非登录操作时，检查到登录，表明需要登录，由外层处理

        while True:
            loop_limit -= 1
            if loop_limit < 0:
                raise BotParseError('检查当前页面次数达到限制，疑似页面执行有互相依赖')

            # 保证页面最新
            self._reset_ctx(ctx_check, ctx_execute)

            current_executor: BotActivityExecutor
            _retry_t, current_executor = RetryHelper \
                .retry_with_time('获取当前运行页面', lambda **kwargs: self._find_curr_executor(ctx_check, **kwargs))
            if current_executor is None:
                if none_activity_counter >= none_activity_limit:
                    raise BotParseError('未识别到当前运行页面')
                none_activity_counter += 1
                self._log(f'未识别到当前运行页面，触发默认返回')
                self._back_default()
                self.d.sleep(1)  # 等待后继续
                continue
            else:
                none_activity_counter = 0
                if _retry_t > 0:  # 有多次重试时，表示页面发生变化
                    self._reset_ctx(ctx_check, ctx_execute)

            # 符合主页时，直接返回
            if action_type == ActionType.Default and current_executor.activity_type == BotActivityType.Main:
                self._log('已回到首页')
                target_executor = current_executor
                break
            # 登录操作时，有触发变更流程后，不是登录或主页时，表明已经登录，则免登录操作
            if action_type == ActionType.Login and had_change_activity \
                    and self._is_activity_non_login(current_executor.activity_type):
                executed = True
                break
            # 非登录操作时，有触发变更流程后，仍在登录页，表明需要登录
            if action_type != ActionType.Login and had_change_activity \
                    and self._is_activity_login(current_executor.activity_type):
                need_login = True
                break

            # 如果仍停留在当前页，则判断是否要重试
            if last_activity_type == current_executor.activity_type:
                self._log(f'仍停留在页面: {last_activity_type}')
                if last_activity_counter < last_activity_counter_retry:
                    last_activity_counter += 1
                    self.d.sleep(1)  # 等待后继续
                    continue
            else:
                last_activity_counter = 0
                last_activity_type = current_executor.activity_type

            curr_exec_name = current_executor.name
            self._log(f'当前页面执行类: {curr_exec_name}, {current_executor.__class__.__name__}')
            # 不在流程内，则触发当前 Activity 返回，一直到符合执行流程的页面时 或 起始主页
            if curr_exec_name not in full_process:
                current_executor.go_back(ctx=ctx_execute, target_type=BotActivityType.Default)
                self._go_interval()
                continue

            # 在流程内，计算需要触发
            had_go_next = self._go_next(full_process, current_executor, ctx_execute)
            if had_go_next:
                had_change_activity = True
                self._go_interval()
            elif not had_change_activity and refresh:
                # 如果无剩余流程时，未触发过一次Activity，则返回后再次触发(即刷新，避免页面缓存)
                current_executor.go_back(ctx=ctx_execute, target_type=BotActivityType.Default)
                # 触发返回时不认为已变更流程页面，可能页面有提示框或键盘时，触发返回仍停留当前页，需要多次触发返回才可以
                # had_change_activity = True
                self._go_interval()
            else:
                # 如果无剩余流程时，已触发过一次Activity，则终止处理
                target_executor = current_executor
                break

        if need_login:
            self._log(f'执行 {action_type} 过程中，检测到需要登录')
        elif executed:
            self._log(f'检测到已执行 {action_type}')
        elif target_executor is not None:
            self._log(f'已完成流程流转: {action_type}，目标页面 ({target_executor.name},{target_executor.activity_type})')
        elif not executed and target_executor is None:
            raise BotStopError('未找到目标页面，内部识别出错')

        return _ActionTargetResult(executed=executed, need_login=need_login, activity_executor=target_executor,
                                   ctx_execute=ctx_execute)

    def _reset_ctx(self, ctx_check: ActivityCheckContext = None, ctx_execute: ActivityExecuteContext = None):
        dump_source = self.d.dump_hierarchy()
        curr_activity = DeviceHelper.current_activity(self.d)
        if ctx_check is not None:
            ctx_check.reset(dump_source, curr_activity)
        if ctx_execute is not None:
            ctx_execute.reset(dump_source, curr_activity)

    def _go_next(self, full_process: List[str], curr_executor: BotActivityExecutor, ctx_execute):
        curr_process_index = full_process.index(curr_executor.name)
        remain_process = full_process[curr_process_index:]
        if len(remain_process) > 1:
            next_executor = self._find_activity_executor(remain_process[1])
            next_activity_type = next_executor.activity_type
            self._log(f'跳转到下一页面: {next_executor.name}，{next_activity_type}')
            curr_executor.go_next(ctx=ctx_execute, target_type=next_activity_type)
            return True

        return False

    def _find_curr_executor(self, ctx_check: ActivityCheckContext = None, **kwargs):
        """查找当前页面执行类"""
        retry_time = kwargs.get('retry_time', 0)
        ctx_check = ctx_check if ctx_check is not None else ActivityCheckContext(self.d)
        if retry_time > 0:
            ctx_check.reset()  # 有重试时，需要重置上下文内容

        # 监听检查，判断是否错误并处理
        if self.bot_config.watcher and self.bot_config.watcher.check(ctx_check):
            self.d.sleep(1)
            return False
        # 轮询检查当前页面
        for executor in self.bot_config.activity_executors:
            if executor.check(ctx=ctx_check):
                return executor
        return None

    def _find_activity_executor(self, act_name: str):
        do_executors = [_e for _e in self.bot_config.activity_executors if _e.name == act_name]
        do_executor = do_executors[0] if do_executors else None
        if not do_executor:
            raise BotStopError(f'未找到页面执行类 {act_name}')
        return do_executor

    @staticmethod
    def _is_activity_login(activity_type: BotActivityType):
        """是否为登录页"""
        return activity_type in [BotActivityType.Login]

    def _is_activity_non_login(self, activity_type: BotActivityType, not_main: bool = True):
        """是否为非登录页，不包含主页"""
        if not_main and activity_type == BotActivityType.Main:
            return False
        return not self._is_activity_login(activity_type)

    def _go_interval(self):
        # self.d.sleep(1)
        # self._log('间隔不停止')
        pass

    def _back_default(self):
        DeviceHelper.press_back(self.d)

    def _log(self, msg: str):
        common_log(f'[{self.__class__.__name__}] - {msg}')
