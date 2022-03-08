# coding: utf-8
from server import misc
from server.settings import api


# 水滴启动接口
def start(account_alias, devices_id=''):
    return post(api['start'], {'accountAlias': account_alias, 'devicesId': devices_id})


# 水滴状态接口
def status(account_alias, state, msg=''):
    return post(api['status'], {'accountAlias': account_alias, 'status': state.value, 'msg': msg})


# 水滴获取最后一条流水
def last_transaction(account_alias):
    return post(api['last_transaction'], {'accountAlias': account_alias})


# 水滴获取订单接口
def transfer(account_alias):
    return post(api['transfer'], {'accountAlias': account_alias})


# 水滴上报流水
def transaction(account_alias, balance, transactions):
    return post(api['transaction'], {'accountAlias': account_alias, 'balance': balance, 'transactions': transactions})


# 水滴上报转账状态
def transfer_result(account_alias, order_id, order_status, msg=''):
    return post(api['transfer_result'],
                {'accountAlias': account_alias, 'orderId': order_id, 'status': order_status, 'msg': msg})


# 水滴上报回单
def receipt(account_alias, receipts):
    return post(api['receipt'], {'accountAlias': account_alias, "receipts": receipts})


# 水滴post公共方法
def post(url, payload):
    url = api['base'] + url
    print('-------------------> %s' % url)
    return misc.post(url, payload, False)


if __name__ == '__main__':
    # data = {'serialNo': 'xxxx', 'accountAlias': 'dddd'}
    # data.update(common_data())
    # print(data)
    # print(register("1ad2838c0107", "农业银行-LYF(刘亦菲)-8888"))
    print(start('RR8M90JGAXR', '农业银行-WQ(韦强)-0873'))
    # print(status('RR8M90JGAXR', Status.RUNNING.value))
    # print(transfer_status(94, 0)
    pass
