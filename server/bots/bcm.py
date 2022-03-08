from server.bots.bank_util.BCM.bcm_activities import *
from server.bots.bank_util.BCM.bcm_check import BCMActionWatcher
from server.bots.act_scheduler.bot_host import BotBankHost
from server.bots.common.common_func import start, stop

from server import settings
from server.models import Account, WorkFlowParams

_pkg_id = 'com.bankcomm.Bankcomm'
_d: u2.Device = settings.bot.device
_account: Account = settings.bot.account

# 初始化代理类，用于检测错误，暂不使用
_d_proxy = None  # BotDeviceProxy()
_act_config = None  # BotActivityConfig(d_proxy)
_executors = [
    BCMMainActivityExecutor('main', BotActivityType.Main, _act_config),
    BCMLoginActivityExecutor('login', BotActivityType.Login, _act_config),
    BCMAccountActivityExecutor('account', BotActivityType.QueryAccount, _act_config),
    BCMTransactionActivityExecutor('transaction', BotActivityType.QueryTrans, _act_config),
    BCMTransferIndexActivityExecutor('transfer_index', BotActivityType.TransferIndex, _act_config),
    BCMTransferActivityExecutor('transfer', BotActivityType.Transfer, _act_config),
    BCMReceiptIndexActivityExecutor('receipt', BotActivityType.QueryReceipt, _act_config),
    # 已识别但无使用页面，用于快速响应页面切换，避免加载中 或 加载完成未识别 的混乱
    BCMLoginVerifyActivityExecutor('login_verify', BotActivityType.TransferResult, _act_config),
    BCMTransactionDetailActivityExecutor('transaction_detail', BotActivityType.QueryTransDetail, _act_config),
    BCMTransferVerifyActivityExecutor('transfer_verify', BotActivityType.TransferVerify, _act_config),
    BCMTransferResultActivityExecutor('transfer_result', BotActivityType.TransferResult, _act_config),
    BCMReceiptDetailActivityExecutor('receipt_detail', BotActivityType.QueryReceiptDetail, _act_config),
    BCMReceiptDetailImgActivityExecutor('receipt_detail_img', BotActivityType.QueryReceiptDetailImage, _act_config),
]
_processes = {
    ActionType.Default: ['main'],
    ActionType.Login: ['main', 'login'],
    ActionType.QueryAccount: ['main', 'account'],
    ActionType.QueryTransaction: ['main', 'account', "transaction"],
    ActionType.Transfer: ['main', 'account', "transfer_index", "transfer"],
    ActionType.QueryReceipt: ['main', 'account', "transfer_index", "receipt"],
}
_watcher = BCMActionWatcher()
_action_config = BotConfig(_executors, _processes, _watcher, _d_proxy)
_scheduler = BotActionScheduler(_d, _action_config, _account)

_bot_bank = BotBankHost(d=_d, package_name=_pkg_id, account=_account, scheduler=_scheduler)


def _reset():
    """重置数据，避免银行卡停止后再次启动，全局变量缓存问题"""
    global _d, _account, _bot_bank
    _d = settings.bot.device
    _account = settings.bot.account
    _bot_bank = BotBankHost(d=_d, package_name=_pkg_id, account=_account, scheduler=_scheduler)


# 执行具体工作流
def do_work(workflow: settings.WorkFlow, params: WorkFlowParams = None):
    # 可以运行工作流
    if not _bot_bank.can_run(workflow):
        return

    # 启动
    if workflow == settings.WorkFlow.START:
        _d.implicitly_wait(60)  # 60秒默认超时
        _reset()
        start(_d, _pkg_id)
    # 停止
    elif workflow == settings.WorkFlow.STOP:
        _bot_bank.stop()
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
        _bot_bank.transfer()
    # 执行查询流水
    elif workflow == settings.WorkFlow.TRANSACTION:
        _bot_bank.transaction(last_trans=params.last_transaction)
    # 执行抓取回单
    elif workflow == settings.WorkFlow.RECEIPT:
        _bot_bank.receipt()
    # sms短信支付
    elif workflow == settings.WorkFlow.SMS:
        _bot_bank.input_sms(sms_msg=params.filter_msg)
    # 检查中断函数
    elif workflow == settings.WorkFlow.BREAK:
        return _bot_bank.break_workflow()
    else:
        return False
