from typing import Callable


class Account:
    def __init__(self, alias: str = '', login_name: str = '', login_pwd: str = '', payment_pwd: str = '',
                 key_pwd: str = '', currency: str = '', account: str = ''):
        self.alias = alias
        self.login_name = login_name
        self.login_pwd = login_pwd
        self.payment_pwd = payment_pwd
        self.key_pwd = key_pwd
        self.currency = currency
        self.account = account


class Transferee:
    def __init__(self, order_id: str = '', amount: str = '', account: str = '', holder: str = '', bank_name: str = '',
                 branch: str = ''):
        self.order_id = order_id
        self.amount = amount
        self.account = account
        self.holder = holder
        self.bank_name = bank_name
        self.branch = branch

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return self.__str__()




class Transaction:
    def __init__(self, trans_time: str = '', trans_type: int = 0, name: str = '', amount: str = '', balance: str = '',
                 postscript: str = '', account: str = '', summary: str = ''):
        self.trans_time = trans_time
        self.trans_type = trans_type
        self.name = name
        self.amount = amount
        self.balance = balance
        self.postscript = postscript
        self.account = account
        self.summary = summary

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return self.__str__()


class BotUtil:
    def __init__(self, cast_transfer: Callable = None, cast_transaction: Callable = None, cast_status: Callable = None,
                 cast_start: Callable = None, cast_last_transaction: Callable = None, cast_work: Callable = None,
                 cast_sms: Callable = None, make_bot: Callable = None):
        self.cast_transfer = cast_transfer
        self.cast_transaction = cast_transaction
        self.cast_status = cast_status
        self.cast_last_transaction = cast_last_transaction
        self.cast_transaction = cast_transaction
        self.cast_work = cast_work
        self.cast_start = cast_start
        self.cast_sms = cast_sms
        self.make_bot = make_bot


class Receipt:
    def __init__(self, time: str = '', amount: str = '', name: str = '', postscript: str = '',
                 customer_account: str = '', inner: str = '', flow_no: str = '', sequence: str = '',
                 need_format: str = 'json', need_img_format: bool = False, bill_no: str = '', content: str = ''):
        self.time = time
        self.amount = amount
        self.name = name
        self.postscript = postscript
        self.customer_account = customer_account
        self.inner = inner
        self.flow_no = flow_no
        self.sequence = sequence
        self.format = need_format
        self.need_img_format = need_img_format
        self.bill_no = bill_no
        self.content = content


class Bot:
    def __init__(self, serial_no: str = '', device: any = None, bank: any = None, account: Account = Account(),
                 last_trans: str = ''):
        self.serial_no = serial_no
        self.device = device
        self.bank = bank
        self.account = account  # Account
        self.last_trans = last_trans
        self.payment = False  # mode[receiving, payment]
        self.running = True
        self.pid = 0
        self.device_info = None

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return self.__str__()


class BreakRes:
    def __init__(self, is_break: bool = False, break_reason: str = ''):
        self.is_break = is_break
        self.break_reason = break_reason


class WorkFlowParams:
    def __init__(self, last_transaction: str = '', filter_msg: str = ''):
        self.last_transaction = last_transaction
        self.filter_msg = filter_msg
