from typing import NoReturn, List

from server.bots.bank_util.CMBC.cmbc_activities import *
from server.bots.bank_util.CMBC.cmbc_check import CMBCActionWatcher
from server.bots.act_scheduler.bot_helpers import BotExecuteWrapper, BotSmsCode
from server.bots.common.common_func import start, stop
from server.bots.common.common_report import report_transfer_result, report_type_transactions, report_type_receipts, \
    report_type_status

from server import settings
from server.settings import log as common_log
from server.models import *

_pkg_id = 'cn.com.cmbc.newmbank'
_d: u2.Device = settings.bot.device
_account: Account = settings.bot.account

_is_stopped: bool = False  # 控制流程停止
_break_res: Optional[BreakRes] = None  # 执行过程中终止，通过全局变量设置中断流程
_continuous_interval = 30 if not settings.debug else 20  # 连续间隔，用于查流水
_continuous_last_exec_time: Optional[datetime] = None  # 连续，上次执行时间
_sms_code = BotSmsCode()
_wrapper = BotExecuteWrapper(lambda *_args, **_kwargs: break_callback(*_args, **_kwargs))

# 初始化代理类，用于检测错误，暂不使用
_d_proxy = None  # BotDeviceProxy()
_act_config = None  # BotActivityConfig(d_proxy)
_executors = [
    CMBCMainActivityExecutor('main', BotActivityType.Main, _act_config),
    CMBCLoginActivityExecutor('login', BotActivityType.Login, _act_config),
    CMBCAccountActivityExecutor('account', BotActivityType.QueryAccount, _act_config),
    CMBCTransactionActivityExecutor('transaction', BotActivityType.QueryTrans, _act_config),
    CMBCTransferIndexActivityExecutor('transfer_index', BotActivityType.TransferIndex, _act_config),
    CMBCTransferActivityExecutor('transfer', BotActivityType.Transfer, _act_config),
    CMBCReceiptIndexActivityExecutor('receipt', BotActivityType.QueryReceipt, _act_config),
    # 已识别但无使用页面，用于快速响应页面切换，避免加载中 或 加载完成未识别 的混乱
    CMBCTransferResultActivityExecutor('transfer_result', BotActivityType.TransferResult, _act_config),
    CMBCReceiptDetailActivityExecutor('receipt_detail', BotActivityType.QueryReceiptDetail, _act_config),
    CMBCReceiptDetailImgActivityExecutor('receipt_detail_img', BotActivityType.QueryReceiptDetailImage, _act_config),
]
_processes = {
    ActionType.Default: ['main'],  # default
    ActionType.Login: ['main', 'login'],
    ActionType.QueryAccount: ['main', 'account'],
    ActionType.QueryTransaction: ['main', 'account', "transaction"],
    ActionType.Transfer: ['main', 'account', "transfer_index", "transfer"],
    ActionType.QueryReceipt: ['main', 'account', "transfer_index", "receipt"],
}
_watcher = CMBCActionWatcher()
_action_config = BotConfig(_executors, _processes, _watcher, _d_proxy)
_scheduler = BotActionScheduler(_d, _action_config, _account)


def break_callback(break_res: BreakRes):
    global _break_res
    _break_res = break_res
    report_type_status(_account.alias, settings.Status.EXCEPTED, _break_res.break_reason)


def input_sms(code: str) -> NoReturn:
    """外部通知验证码"""
    if len(code) != 6:
        common_log(f'短信验证码长度必须为6位 {code}')
        return
    _sms_code.set_sms_code(code)


@_wrapper.exec_wrap(name='转账', retry_limit=0, error_stop=False)  # 转账错误后不强制停止，因转账未有重试
def transfer():
    """转账"""
    transferee: Transferee = settings.transferee
    trans_result, trans_msg = False, '转账失败'
    try:
        trans_result, trans_msg = _scheduler.execute(ActionType.Transfer, transferee=transferee,
                                                     sms_code_func=_sms_code.get_sms_code)
    except Exception as err:
        trans_result = False
        if isinstance(err, BotErrorBase):
            trans_msg = err.full_msg()
        else:
            trans_msg = f'转账处理异常: {repr(err)}'
        raise  # 再继续抛异常，由外层继续处理
    finally:
        common_log(f'转账结果: 单号-{transferee.order_id}, 结果-{trans_result}, 消息-{trans_msg}')
        report_transfer_result(_account.alias, transferee.order_id, trans_result, trans_msg)


@_wrapper.exec_wrap(name='查询流水', retry_limit=5)
def transaction(last_trans: Transaction):
    """抓流水"""
    # 缓存余额比较
    trans_list: List[Transaction] = _scheduler.execute(ActionType.QueryTransaction,
                                                       last_trans=last_trans,
                                                       max_query_count=30)
    common_log(f'流水列表: {trans_list}')
    account_result = _scheduler.execute(ActionType.QueryAccount)
    balance = account_result.get('balance', 0)
    common_log(f'余额: {balance}')
    # 上报数据，金额已经转换为分
    report_type_transactions(_account.alias, balance, trans_list, is_fen_amount=True)


@_wrapper.exec_wrap(name='查询回单', retry_limit=5)
def receipt():
    """抓回单"""
    last_transferee: Transferee = settings.transferee if settings.transferee else None
    # 查询回单，查找上次转账匹配项，默认最多查2条
    receipt_list: List[Receipt] = _scheduler.execute(ActionType.QueryReceipt,
                                                     last_transferee=last_transferee,
                                                     max_query_count=2)
    common_log(f'回单列表: {receipt_list}')
    # 上报数据，金额已经转换为分
    report_type_receipts(_account.alias, receipt_list, is_fen_amount=True)


def break_workflow() -> BreakRes:
    """检查是否强制中断"""
    global _break_res, _is_stopped
    if _break_res and _break_res.is_break:
        return _break_res
    if _is_stopped:
        return BreakRes(is_break=True, break_reason='程序已停止')
    return BreakRes()


def _wait_moment(workflow: settings.WorkFlow):
    """等待处理，避免连续性查询过快，目前仅限制查流水"""
    global _is_stopped, _continuous_interval, _continuous_last_exec_time

    if workflow not in [settings.WorkFlow.TRANSACTION]:
        return
    if _continuous_last_exec_time is None:
        return

    diff = datetime.now() - _continuous_last_exec_time
    remains = _continuous_interval - diff.seconds
    if remains > 0:
        common_log(f'暂停 {remains} 秒继续: {workflow}')
        _d.sleep(remains)


def _reset():
    """重置数据，避免银行卡停止后再次启动，全局变量缓存问题"""
    global _account, _d, _is_stopped, _break_res, _continuous_last_exec_time
    _account = settings.bot.account
    _d = settings.bot.device
    _scheduler.account = _account
    _is_stopped = False
    _break_res = None
    _continuous_last_exec_time = None


# 执行具体工作流
def do_work(workflow: settings.WorkFlow, params: WorkFlowParams = None):
    global _is_stopped, _continuous_last_exec_time, _break_res
    # 启动可恢复运行，此处不检查终止操作
    if workflow != settings.WorkFlow.START:
        # 如果有终止，无需继续处理。避免流程继续运行，直到检测 Break 彻底停止
        if _break_res is not None and _break_res.is_break and workflow != settings.WorkFlow.BREAK:
            common_log(f'执行 {workflow} ，检测到已终止 {_break_res.break_reason}')
            return
        # 等待后再判断是否有停止操作
        _wait_moment(workflow)
        if _is_stopped:
            return

    # 启动
    if workflow == settings.WorkFlow.START:
        _is_stopped = False
        _d.implicitly_wait(60)  # 60秒默认超时
        _reset()
        start(_d, _pkg_id)
    # 停止
    elif workflow == settings.WorkFlow.STOP:
        _is_stopped = True
        stop(_d, _pkg_id)
    # 检测起始页
    elif workflow == settings.WorkFlow.CHECK_HOME:
        return True
    # 回到起始页
    elif workflow == settings.WorkFlow.GO_HOME:
        # go_home()
        pass
    # 检测登录态
    elif workflow == settings.WorkFlow.CHECK_LOGIN:
        return True
    # 执行登录
    elif workflow == settings.WorkFlow.DO_LOGIN:
        # do_login()
        pass
    # 执行转账
    elif workflow == settings.WorkFlow.TRANSFER:
        transfer()
    # 执行查询流水
    elif workflow == settings.WorkFlow.TRANSACTION:
        transaction(last_trans=params.last_transaction)
        _continuous_last_exec_time = datetime.now()
    # 执行抓取回单
    elif workflow == settings.WorkFlow.RECEIPT:
        receipt()
    # sms短信支付
    elif workflow == settings.WorkFlow.SMS:
        input_sms(code=params.filter_msg)
    # 检查中断函数
    elif workflow == settings.WorkFlow.BREAK:
        return break_workflow()
    else:
        return False
