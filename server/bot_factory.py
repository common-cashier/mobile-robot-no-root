import uiautomator2 as u2
import settings
from models import Bot, Account, Transferee, BreakRes, WorkFlowParams
from misc import parse_sms
from settings import log, WorkFlow
import api


class BotFactory:

    def __init__(self):
        if settings.debug:
            self.d = u2.connect('7d19caab')
        else:
            self.d = u2.connect('0.0.0.0')
        print('bot: %s' % settings.bot)
        self.bank = ""
        print("您的银行应用已经由脚本接管")
        self.doing = False

    def cast_work_flow(self):
        break_res: BreakRes = self.bank.do_work(WorkFlow.BREAK)
        if break_res.is_break:
            log('--流程错误: %s' % break_res.break_reason, settings.Level.SYSTEM)
        else:
            if self.bank.do_work(WorkFlow.CHECK_HOME):
                if self.bank.do_work(WorkFlow.CHECK_LOGIN):
                    if query_order(settings.bot.account.alias):
                        self.cast_transfer()
                    else:
                        settings.bot.last_trans = api.last_transaction(settings.bot.account.alias)
                        self.bank.do_work(WorkFlow.TRANSACTION, WorkFlowParams(last_transaction=settings.bot.last_trans))
                        self.bank.do_work(WorkFlow.GO_HOME)
                        self.cast_work_flow()
                else:
                    self.bank.do_work(WorkFlow.DO_LOGIN)
                    self.bank.do_work(WorkFlow.GO_HOME)
                    self.cast_work_flow()
            else:
                self.bank.do_work(WorkFlow.GO_HOME)
                self.cast_work_flow()

    def cast_start(self, params):
        if self.doing:
            return False
        self.doing = True
        if params['devices_id'] is not None and params['devices_id'] != '':
            rsp = api.start(params['account_alias'], params['devices_id'])
        else:
            rsp = api.start(params['account_alias'])
        if rsp['code'] == 0 and rsp['data'] is not None:
            convert(rsp['data'], params['bank'].lower())
            log("rsp['data']: %s" % rsp)
            self.doing = False
            return rsp
        else:
            self.doing = False
            return {'code': 1, 'msg': rsp['msg'], 'data': rsp['data']}

    def make_bot(self):
        settings.bot.device_info = self.d.info
        settings.bot.device = self.d
        module = __import__("bots.%s" % settings.bot.bank.lower())
        self.bank = getattr(module, settings.bot.bank.lower())

    def cast_work(self, params):
        if params['do_work'] == "stop":
            if self.bank == '':
                return {'code': 0, 'msg': '卡机停止状态已经上报！'}
            else:
                self.bank.do_work(WorkFlow.STOP)
                return {'code': 0, 'msg': '卡机停止状态已经上报！'}
        if self.doing:
            return False
        self.doing = True
        if params['do_work'] == "start":
            self.make_bot()
            self.bank.do_work(WorkFlow.START)
            self.cast_work_flow()
        else:
            api.status(params['account_alias'], settings.Status.RUNNING)
        print("do_work:print: %s" % params)
        self.bank.do_work(params['do_work'])
        self.doing = False

    def cast_sms(self, params):
        if self.doing:
            return False
        self.doing = True
        try:
            filter_msg = parse_sms(params['sms'], settings.bot.bank)
            if filter_msg != 1:
                self.doing = self.bank.do_work(WorkFlow.SMS, WorkFlowParams(filter_msg=filter_msg))
            return filter_msg
        except Exception as ext:
            return ext

    def cast_transfer(self):
        self.bank.do_work(WorkFlow.TRANSFER)
        self.bank.do_work(WorkFlow.RECEIPT)
        self.bank.do_work(WorkFlow.TRANSACTION)
        self.bank.do_work(WorkFlow.GO_HOME)
        self.cast_work_flow()


def convert(data, bank):
    settings.bot = Bot(serial_no=settings.serial_no, bank=bank, account=data['account'])
    settings.bot.account = Account(alias=data['accountAlias'], login_name=data['loginName'],
                                   login_pwd=data['loginPassword'],
                                   payment_pwd=data['payPassword'], key_pwd=data['keyPassword'],
                                   account=data['account'])

    print("set local account %s" % settings.bot.account)


def query_order(alias):
    if settings.debug:
        return False
    else:
        rsp = api.transfer(alias)
        if rsp['data'] is None:
            return False
        else:
            settings.transferee = Transferee(rsp['data']['orderId'], "%.2f" % (float(rsp['data']['amount']) / 100),
                                             rsp['data']['account'], rsp['data']['holder'])
            return True
