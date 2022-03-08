import time
from typing import NoReturn, List

from server.bots.common.common_func import start, stop
from server.bots.common.common_models import GoToPath, GoToPathRes
from server.bots.common.common_report import report_status

from server import settings
from server.models import BreakRes, WorkFlowParams

# 包名
package: str = 'com.chinamworld.main'
# 主页
main_activity: str = 'com.ccb.start.MainActivity'
# u2设备对象
self: object = settings.bot.device
# 支付路径
transfer_path: List = ['A', 'B', 'C', 'D', 'E']
# 抓流水路径
transaction_path: List = ['A', 'B', 'G', 'H', 'I']
# 回单路径
receipt_path: List = ['A', 'B', 'X', 'Y', 'Z']
# 来的路径
from_path: List = []
# 去的路径
to_path: List = []
# 是否为中转路径
middle_way: bool = False
# 中转地址
middle_way_current: str = ''
# 是否默认来的路径回退
default_home_path: bool = False


# 检查起始页
def check_home() -> bool:
    global self
    print('check home')
    return False


# 检查登录态
def check_login() -> bool:
    global self
    print('check login')
    return False


# 执行登录
def do_login() -> NoReturn:
    global self
    print('do login')


# 执行转账
def transfer() -> NoReturn:
    global self, middle_way, from_path, to_path
    if middle_way:
        print('from middle way start to %s' % middle_way_current)
        middle_way = False
    else:
        print('from home page')
    print('transfer')
    from_path = transfer_path
    to_path = receipt_path
    # 支付完成等待sms
    settings.need_sms = True
    # 等待检测是否完成sms
    while settings.need_sms:
        time.sleep(8)
    # 以下执行完成支付后上报等操作


# 抓流水
def transaction(params: WorkFlowParams) -> NoReturn:
    global self, middle_way, from_path, to_path
    if middle_way:
        print('from middle way start to %s' % middle_way_current)
        middle_way = False
    else:
        print('from home page')
    print('transaction')
    from_path = transaction_path
    to_path = transfer_path


# 抓回单
def receipt() -> NoReturn:
    global self, middle_way, from_path, to_path
    if middle_way:
        print('from middle way start to %s' % middle_way_current)
        middle_way = False
    else:
        print('from home page')
    print('receipt')
    from_path = receipt_path
    to_path = transaction_path


# 回起始页
def go_home() -> NoReturn:
    global self, middle_way, from_path, to_path, default_home_path, middle_way_current
    print('go home')

    # 执行返回的回调方法
    def go_to_step():
        global self
        self.press("back")
        print('going')

    # 执行返回公共类
    go_to_path = GoToPath(from_path, to_path, go_to_step)
    # 如果默认原路返回
    if default_home_path:
        res = go_to_path.default_way()
    else:
        res = go_to_path.to_go()
    # 获取中转路径地址
    middle_way_current = res.current
    # 如果中转路径索引不是第一个，则是中路返回
    if res.idx != 0:
        middle_way = True
    else:
        middle_way = False


# 检查是否强制中断方法
def break_workflow() -> BreakRes:
    global self
    print('break workflow')
    return BreakRes()


# 输入sms验证码
def input_sms(params: WorkFlowParams) -> NoReturn:
    global self
    print('input sms')
    # 完成sms支付后需要关闭检测开关，通知支付脚本继续
    settings.need_sms = False


# 停止的回调方法
def stop_callback():
    print('stop callback function')
    params = {
        "account_alias": settings.bot.account.alias,
        "status": settings.Status.IDLE
    }
    report_status(params)


# 执行具体工作流
def do_work(workflow: settings.WorkFlow, params: WorkFlowParams()):
    # 启动
    if workflow == settings.WorkFlow.START:
        start(self, package)
    # 停止
    elif workflow == settings.WorkFlow.STOP:
        stop(self, package, stop_callback)
    # 检测起始页
    elif workflow == settings.WorkFlow.CHECK_HOME:
        return check_home()
    # 检测登录态
    elif workflow == settings.WorkFlow.CHECK_LOGIN:
        return check_login()
    # 执行登录
    elif workflow == settings.WorkFlow.DO_LOGIN:
        do_login()
    # 执行转账
    elif workflow == settings.WorkFlow.TRANSFER:
        transfer()
    # 执行查询流水
    elif workflow == settings.WorkFlow.TRANSACTION:
        transaction(params)
    # 执行抓取回单
    elif workflow == settings.WorkFlow.RECEIPT:
        receipt()
    # 回到起始页
    elif workflow == settings.WorkFlow.GO_HOME:
        go_home()
    # 检查中断函数
    elif workflow == settings.WorkFlow.BREAK:
        break_workflow()
    # sms短信支付
    elif workflow == settings.WorkFlow.SMS:
        return input_sms(params)
    else:
        return False
