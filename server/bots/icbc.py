import time
from typing import NoReturn, List

from server.bots.common.common_func import start, stop
from server.bots.common.common_models import GoToPath, GoToPathRes
from server.bots.common.common_report import report_status

from server import settings
from server.models import BreakRes, WorkFlowParams

package: str = 'com.chinamworld.main'
main_activity: str = 'com.ccb.start.MainActivity'
self: object = settings.bot.device
transfer_path: List = ['A', 'B', 'C', 'D', 'E']
transaction_path: List = ['A', 'B', 'G', 'H', 'I']
receipt_path: List = ['A', 'B', 'X', 'Y', 'Z']
from_path: List = []
to_path: List = []
middle_way: bool = False
middle_way_current: str = ''
default_home_path: bool = False


def check_home() -> bool:
    global self
    print('check home')
    return False


def check_login() -> bool:
    global self
    print('check login')
    return False


def do_login() -> NoReturn:
    global self
    print('do login')


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
    settings.need_sms = True
    while settings.need_sms:
        time.sleep(8)


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


def go_home() -> NoReturn:
    global self, middle_way, from_path, to_path, default_home_path, middle_way_current
    print('go home')

    def go_to_step():
        global self
        self.press("back")
        print('going')

    go_to_path = GoToPath(from_path, to_path, go_to_step)
    if default_home_path:
        res = go_to_path.default_way()
    else:
        res = go_to_path.to_go()
    middle_way_current = res.current
    if res.idx != 0:
        middle_way = True
    else:
        middle_way = False


def break_workflow() -> BreakRes:
    global self
    print('break workflow')
    return BreakRes()


def input_sms(params: WorkFlowParams) -> NoReturn:
    global self
    print('input sms')
    settings.need_sms = False


def stop_callback():
    print('stop callback function')
    params = {
        "account_alias": settings.bot.account.alias,
        "status": settings.Status.IDLE
    }
    report_status(params)


def do_work(workflow: settings.WorkFlow, params: WorkFlowParams()):
    if workflow == settings.WorkFlow.START:
        start(self, package)
    elif workflow == settings.WorkFlow.STOP:
        stop(self, package, stop_callback)
    elif workflow == settings.WorkFlow.CHECK_HOME:
        return check_home()
    elif workflow == settings.WorkFlow.CHECK_LOGIN:
        return check_login()
    elif workflow == settings.WorkFlow.DO_LOGIN:
        do_login()
    elif workflow == settings.WorkFlow.TRANSFER:
        transfer()
    elif workflow == settings.WorkFlow.TRANSACTION:
        transaction(params)
    elif workflow == settings.WorkFlow.RECEIPT:
        receipt()
    elif workflow == settings.WorkFlow.GO_HOME:
        go_home()
    elif workflow == settings.WorkFlow.BREAK:
        break_workflow()
    elif workflow == settings.WorkFlow.SMS:
        return input_sms(params)
    else:
        return False
