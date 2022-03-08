from server.bots.bank_util.BCM.bcm_activities import *
from server.bots.bank_util.BCM.bcm_check import BCMActionWatcher
from server.bots.act_scheduler.bot_host import BotBankHost
from server.bots.common.common_func import start, stop

from server import settings
from server.models import Account, WorkFlowParams

_pkg_id = 'com.bankcomm.Bankcomm'
_d: u2.Device = settings.bot.device
_account: Account = settings.bot.account

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
