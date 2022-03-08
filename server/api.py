from server import misc
from server.settings import api


def start(account_alias, devices_id=''):
    return post(api['start'], {'accountAlias': account_alias, 'devicesId': devices_id})


def status(account_alias, state, msg=''):
    return post(api['status'], {'accountAlias': account_alias, 'status': state.value, 'msg': msg})


def last_transaction(account_alias):
    return post(api['last_transaction'], {'accountAlias': account_alias})


def transfer(account_alias):
    return post(api['transfer'], {'accountAlias': account_alias})


def transaction(account_alias, balance, transactions):
    return post(api['transaction'], {'accountAlias': account_alias, 'balance': balance, 'transactions': transactions})


def transfer_result(account_alias, order_id, order_status, msg=''):
    return post(api['transfer_result'],
                {'accountAlias': account_alias, 'orderId': order_id, 'status': order_status, 'msg': msg})


def receipt(account_alias, receipts):
    return post(api['receipt'], {'accountAlias': account_alias, "receipts": receipts})


def post(url, payload):
    url = api['base'] + url
    print('-------------------> %s' % url)
    return misc.post(url, payload, False)


if __name__ == '__main__':
    print(start('RR8M90JGAXR', '农业银行-WQ(韦强)-0873'))
    pass
