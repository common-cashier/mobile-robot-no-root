import uiautomator2 as u2

from server import settings, api
from server.models import Bot, Account, Transferee, BreakRes, WorkFlowParams, Transaction
from server.misc import parse_sms
from server.settings import log, WorkFlow



class BotFactory:

    def __init__(self):
        if settings.debug:
            self.d = u2.connect(settings.serial_no)
        else:
            self.d = u2.connect('0.0.0.0')
        self.bank = ""
        print("您的银行应用已经由脚本接管")
        self.doing = False

    def cast_work_flow(self):
        try:
            while True:
                break_res: BreakRes = self.bank.do_work(WorkFlow.BREAK)
                if break_res and break_res.is_break:
                    log('--流程错误: %s' % break_res.break_reason, settings.Level.SYSTEM)
                    break
                if not self.bank.do_work(WorkFlow.CHECK_HOME):
                    self.bank.do_work(WorkFlow.GO_HOME)
                    continue
                if not self.bank.do_work(WorkFlow.CHECK_LOGIN):
                    self.bank.do_work(WorkFlow.DO_LOGIN)
                    self.bank.do_work(WorkFlow.GO_HOME)
                    continue
                if settings.start_kind == 1:
                    if query_order(settings.bot.account.alias):
                        self.cast_transfer()
                    else:
                        self.cast_transaction()
                else:
                    self.cast_transaction()
        except Exception as err:
            api.status(settings.bot.account.alias, settings.Status.EXCEPTED, f'运行出错-{str(err)}')
            raise err

    def cast_start(self, params):
        if self.doing:
            return False
        self.doing = True
        try:
            if params['devices_id'] is not None and params['devices_id'] != '':
                rsp = api.start(params['account_alias'], params['devices_id'])
            else:
                rsp = api.start(params['account_alias'])
            if rsp['code'] == 0 and rsp['data'] is not None:
                convert(rsp['data'], params['bank'].lower())
                log("rsp['data']: %s" % rsp)
                return rsp
            else:
                return {'code': 1, 'msg': rsp['msg'], 'data': rsp['data']}
        finally:
            self.doing = False

    def make_bot(self):
        settings.bot.device_info = self.d.info
        settings.bot.device = self.d
        module = __import__("bots.%s" % settings.bot.bank.lower())
        self.bank = getattr(module, settings.bot.bank.lower())
        print('bot: %s' % settings.bot)

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
        try:
            if params['do_work'] == "start":
                self.make_bot()
                self.bank.do_work(WorkFlow.START)
                self.cast_work_flow()
            print("do_work:print: %s" % params)
        finally:
            self.doing = False

    def cast_transaction(self):
        convert_last_trans()
        self.bank.do_work(WorkFlow.TRANSACTION, WorkFlowParams(last_transaction=settings.bot.last_trans))
        self.bank.do_work(WorkFlow.GO_HOME)

    def cast_sms(self, params):
        if not self.bank:
            raise Exception('请先执行 start 启动')
        filter_msg = parse_sms(params['sms'], settings.bot.bank)
        if filter_msg != 1:
            self.bank.do_work(WorkFlow.SMS, WorkFlowParams(filter_msg=filter_msg))
        return filter_msg

    def cast_transfer(self):
        self.bank.do_work(WorkFlow.TRANSFER)
        self.bank.do_work(WorkFlow.GO_HOME)
        self.bank.do_work(WorkFlow.RECEIPT)
        self.bank.do_work(WorkFlow.GO_HOME)
        convert_last_trans()
        self.bank.do_work(WorkFlow.TRANSACTION, WorkFlowParams(last_transaction=settings.bot.last_trans))
        self.bank.do_work(WorkFlow.GO_HOME)


def convert_last_trans():
    rsp = api.last_transaction(settings.bot.account.alias)
    last_trans = rsp['data']
    settings.bot.last_trans = Transaction.from_dict(last_trans)


def convert(data, bank):
    settings.bot = Bot(serial_no=settings.serial_no, bank=bank)
    settings.bot.account = Account.from_dict(data)
    print("set local account %s" % settings.bot.account)


def query_order(alias):
    if settings.debug:
        return False
    else:
        rsp = api.transfer(alias)
        if rsp['data'] is None:
            return False
        else:
            settings.transferee = Transferee.from_dict(rsp['data'])
            return True
