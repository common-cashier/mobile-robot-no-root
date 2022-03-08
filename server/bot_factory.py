# coding=utf-8
import uiautomator2 as u2

from server import settings, api
from server.models import Bot, Account, Transferee, BreakRes, WorkFlowParams, Transaction
from server.misc import parse_sms
from server.settings import log, WorkFlow


# 反射生产自动机机器人

class BotFactory:

    def __init__(self):
        if settings.debug:
            # 测试代码
            self.d = u2.connect(settings.serial_no)
        else:
            # 线上代码
            self.d = u2.connect('0.0.0.0')
        self.bank = ""
        print("您的银行应用已经由脚本接管")
        self.doing = False

    # 执行工作流
    def cast_work_flow(self):
        """
        WorkFlow.BREAK 检查是否需要强制终止
        返回值：
        is_break：是否终止
        break_reason：终止理由
        """
        # 轮询执行
        try:
            while True:
                # 检查是否中断
                break_res: BreakRes = self.bank.do_work(WorkFlow.BREAK)
                if break_res and break_res.is_break:
                    log('--流程错误: %s' % break_res.break_reason, settings.Level.SYSTEM)
                    break
                # 检查是否是起始页
                if not self.bank.do_work(WorkFlow.CHECK_HOME):
                    # 如果不是起始页
                    self.bank.do_work(WorkFlow.GO_HOME)
                    continue
                # 检查是否登录
                if not self.bank.do_work(WorkFlow.CHECK_LOGIN):
                    # 如果未登录
                    self.bank.do_work(WorkFlow.DO_LOGIN)
                    self.bank.do_work(WorkFlow.GO_HOME)
                    continue
                # 判断启动种类 0：收款，1：付款
                if settings.start_kind == 1:
                    # 查询是否有订单
                    if query_order(settings.bot.account.alias):
                        # 执行付款
                        self.cast_transfer()
                    else:
                        # 执行收款
                        self.cast_transaction()
                else:
                    # 执行收款
                    self.cast_transaction()
        except Exception as err:
            api.status(settings.bot.account.alias, settings.Status.EXCEPTED, f'运行出错-{str(err)}')
            raise err

    # 执行启动
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

    # 制作机器人
    def make_bot(self):
        settings.bot.device_info = self.d.info
        settings.bot.device = self.d
        module = __import__("bots.%s" % settings.bot.bank.lower())
        self.bank = getattr(module, settings.bot.bank.lower())
        print('bot: %s' % settings.bot)

    # 执行特定工作
    def cast_work(self, params):
        # 无论有没有执行中的任务，优先执行停止
        if params['do_work'] == "stop":
            if self.bank == '':
                return {'code': 0, 'msg': '卡机停止状态已经上报！'}
            else:
                self.bank.do_work(WorkFlow.STOP)
                return {'code': 0, 'msg': '卡机停止状态已经上报！'}
        # 任务锁，防止重复执行任务
        if self.doing:
            return False
        self.doing = True
        try:
            # 如果执行启动
            if params['do_work'] == "start":
                self.make_bot()
                self.bank.do_work(WorkFlow.START)
                self.cast_work_flow()
            print("do_work:print: %s" % params)
        finally:
            self.doing = False

    # 收款方法
    def cast_transaction(self):
        # 获取最后一条流水
        convert_last_trans()
        self.bank.do_work(WorkFlow.TRANSACTION, WorkFlowParams(last_transaction=settings.bot.last_trans))
        self.bank.do_work(WorkFlow.GO_HOME)

    # 短信驱动付款完成
    def cast_sms(self, params):
        if not self.bank:
            raise Exception('请先执行 start 启动')
        # 过滤短信
        filter_msg = parse_sms(params['sms'], settings.bot.bank)
        if filter_msg != 1:
            self.bank.do_work(WorkFlow.SMS, WorkFlowParams(filter_msg=filter_msg))
        return filter_msg

    # 付款流程
    def cast_transfer(self):
        self.bank.do_work(WorkFlow.TRANSFER)
        self.bank.do_work(WorkFlow.GO_HOME)
        self.bank.do_work(WorkFlow.RECEIPT)
        self.bank.do_work(WorkFlow.GO_HOME)
        # 获取最后一条流水
        convert_last_trans()
        self.bank.do_work(WorkFlow.TRANSACTION, WorkFlowParams(last_transaction=settings.bot.last_trans))
        self.bank.do_work(WorkFlow.GO_HOME)


# 转换最后一条流水
def convert_last_trans():
    rsp = api.last_transaction(settings.bot.account.alias)
    last_trans = rsp['data']
    settings.bot.last_trans = Transaction.from_dict(last_trans)


# 实例化bot和account，储存至setting
def convert(data, bank):
    settings.bot = Bot(serial_no=settings.serial_no, bank=bank)
    settings.bot.account = Account.from_dict(data)
    print("set local account %s" % settings.bot.account)


# 查询支付订单
def query_order(alias):
    if settings.debug:
        # 测试代码
        # settings.transferee = Transferee('32422', '1.01', '6217852600028354869', '张源花')
        return False
    else:
        # 线上代码
        rsp = api.transfer(alias)
        if rsp['data'] is None:
            return False
        else:
            settings.transferee = Transferee.from_dict(rsp['data'])
            return True
