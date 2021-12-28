import sys

sys.path.append("../..")
from settings import log, WorkFlow
import settings
import api
from models import Receipt


def report_transaction(params):
    filter_transaction = []
    params['balance'] = "%.2f" % (float(params['balance']) * 100)
    for transaction in params['transactions']:
        transaction['amount'] = "%.2f" % (float(transaction['amount']) * 100)
        transaction['balance'] = "%.2f" % (float(transaction['balance']) * 100)
        filter_transaction.append(transaction)
    if len(filter_transaction) > 0:
        log('transaction_report: ' + str(filter_transaction), settings.Level.RECEIPT_OF_RECEIVE)
        api.transaction(params['account_alias'], params['balance'], filter_transaction)
        api.status(params['account_alias'], settings.Status.RUNNING)


def report_receipt(params):
    if settings.receipt.name is not None:
        try:
            api.receipt(params['account_alias'], [
                {'time': settings.receipt.time, 'amount': "%.2f" % (float(settings.receipt.amount) * 100),
                 'name': settings.receipt.name,
                 'postscript': settings.receipt.postscript, 'customerAccount': settings.receipt.customer_account,
                 'inner': settings.receipt.inner, 'flowNo': settings.receipt.flow_no,
                 'sequence': settings.receipt.sequence, 'format': settings.receipt.format,
                 'billNo': settings.receipt.bill_no, 'imageFormat': settings.receipt.image_format,
                 'content': settings.receipt.content}])
        except Exception as ext:
            log(ext, settings.Level.SYSTEM)
        settings.receipt = Receipt()
    settings.need_receipt = False


def report_status(params):
    rsp = api.status(params['account_alias'], params['status'])
    return rsp
