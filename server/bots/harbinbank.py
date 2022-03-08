from server.bots.bank_util.HARBINBANK.hrb_activities import *
from server.bots.bank_util.HARBINBANK.hrb_check import HRBActionWatcher
from server.bots.act_scheduler.bot_host import BotBankHost
from server.bots.common.common_func import start, stop
from server.bots.common.common_report import report_type_receipt

from server import settings
from server.models import Account, WorkFlowParams

_pkg_id = 'com.yitong.hrb.people.android'
_d: u2.Device = settings.bot.device
_account: Account = settings.bot.account

_d_proxy = None  # BotDeviceProxy()
_act_config = None  # BotActivityConfig(d_proxy)
_executors = [
    HRBMainActivityExecutor('main', BotActivityType.Main, _act_config),
    HRBLoginActivityExecutor('login', BotActivityType.Login, _act_config),
    HRBAccountActivityExecutor('account', BotActivityType.QueryAccount, _act_config),
    HRBTransactionActivityExecutor('transaction', BotActivityType.QueryTrans, _act_config),
    HRBTransferActivityExecutor('transfer', BotActivityType.Transfer, _act_config),
    HRBTransactionDetailActivityExecutor('transaction_detail', BotActivityType.QueryTransDetail, _act_config),
    HRBTransferVerifyActivityExecutor('transfer_verify', BotActivityType.TransferVerify, _act_config),
    HRBTransferResultLoadActivityExecutor('transfer_result_1', BotActivityType.TransferResultTransition, _act_config),
    HRBTransferResultActivityExecutor('transfer_result', BotActivityType.TransferResult, _act_config),
]
_processes = {
    ActionType.Default: ['main'],
    ActionType.Login: ['main', 'login'],
    ActionType.QueryAccount: ['main', 'account'],
    ActionType.QueryTransaction: ['main', 'account', 'transaction'],
    ActionType.Transfer: ['main', 'account', 'transfer'],
}
_watcher = HRBActionWatcher()
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
        receipt = HRBReceiptDetailActivityExecutor.last_receipt
        if receipt is not None:
            report_type_receipt(_account.alias, receipt, is_fen_amount=True)
            HRBReceiptDetailActivityExecutor.last_receipt = None
    elif workflow == settings.WorkFlow.SMS:
        _bot_bank.input_sms(sms_msg=params.filter_msg)
    elif workflow == settings.WorkFlow.BREAK:
        return _bot_bank.break_workflow()
    else:
        return False
