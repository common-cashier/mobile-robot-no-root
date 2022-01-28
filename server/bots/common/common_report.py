from typing import List

from server import settings, api
from server.settings import log
from server.models import Receipt, Transaction


def report_transfer_result(account_alias: str, order_id: int, order_status: bool, msg=''):
    api.transfer_result(account_alias, order_id, order_status, msg)


def report_transaction(params):
    balance = int(float(params['balance']) * 100)
    report_type_transactions(params['account_alias'], balance, params['transactions'], is_fen_amount=False)


def report_type_transactions(account_alias: str, balance: int, transactions: List[Transaction], is_fen_amount=False):
    if transactions is None:
        return
    filter_list = []
    for trans in transactions:
        dict_trans = trans.to_dict(is_fen_amount=is_fen_amount)
        filter_list.append(dict_trans)
    if filter_list:
        api.transaction(account_alias, balance, filter_list)
        api.status(account_alias, settings.Status.RUNNING)


def report_receipt(params):
    report_type_receipt(params['account_alias'], params['receipt'], is_fen_amount=False)


def report_type_receipt(account_alias: str, receipt: Receipt, is_fen_amount=False):
    report_type_receipts(account_alias, [receipt], is_fen_amount)


def report_type_receipts(account_alias: str, receipts: List[Receipt], is_fen_amount=False):
    try:
        filter_list = []
        for receipt in receipts:
            if receipt.name is None:
                continue
            filter_list.append(receipt.to_dict(is_fen_amount=is_fen_amount))
        if filter_list:
            api.receipt(account_alias, filter_list)
    except Exception as ext:
        log(ext, settings.Level.SYSTEM)


def report_status(params):
    msg = getattr(params, 'msg', '')
    return report_type_status(params['account_alias'], params['status'], msg)


def report_type_status(account_alias: str, status: settings.Status, msg=''):
    api.status(account_alias, status, msg)
