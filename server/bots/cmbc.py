from server.bots.bank_util.CMBC.cmbc_activities import *
from server.bots.bank_util.CMBC.cmbc_check import CMBCActionWatcher
from server.bots.act_scheduler.bot_host import BotBankHost
from server.bots.common.common_func import start, stop

from server import settings
from server.models import Account, WorkFlowParams

_pkg_id = 'cn.com.cmbc.newmbank'
_d: u2.Device = settings.bot.device
_account: Account = settings.bot.account

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

_bot_bank = BotBankHost(d=_d, package_name=_pkg_id, account=_account, scheduler=_scheduler)


def _reset():
    global _d, _account, _bot_bank
    _d = settings.bot.device
    _account = settings.bot.account
    _bot_bank = BotBankHost(d=_d, package_name=_pkg_id, account=_account, scheduler=_scheduler)


def do_work(workflow: settings.WorkFlow, params: WorkFlowParams = None):
    if not _bot_bank.can_run(workflow):
        return

    if workflow == settings.WorkFlow.START:
        _d.implicitly_wait(60)  # 60秒默认超时
        _reset()
        start(_d, _pkg_id)
    elif workflow == settings.WorkFlow.STOP:
        _bot_bank.stop()
        stop(_d, _pkg_id)
    elif workflow == settings.WorkFlow.CHECK_HOME:
        return True
    elif workflow == settings.WorkFlow.GO_HOME:
        pass
    elif workflow == settings.WorkFlow.CHECK_LOGIN:
        return True
    elif workflow == settings.WorkFlow.DO_LOGIN:
        pass
    elif workflow == settings.WorkFlow.TRANSFER:
        _bot_bank.transfer()
    elif workflow == settings.WorkFlow.TRANSACTION:
        _bot_bank.transaction(last_trans=params.last_transaction)
    elif workflow == settings.WorkFlow.RECEIPT:
        _bot_bank.receipt()
    elif workflow == settings.WorkFlow.SMS:
        _bot_bank.input_sms(sms_msg=params.filter_msg)
    elif workflow == settings.WorkFlow.BREAK:
        return _bot_bank.break_workflow()
    else:
        return False
