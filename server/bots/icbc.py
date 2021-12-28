import sys
from typing import NoReturn, List

from common.common_func import start, stop
from common.common_models import GoToPath

sys.path.append("..")
import api
import settings
from models import BreakRes, WorkFlowParams

package = 'com.chinamworld.main'
main_activity = 'com.ccb.start.MainActivity'
self = settings.bot.device
from_path: List = []
to_path: List = []
middle_way: bool = False
middle_way_current: str = ''


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
    global self, middle_way
    if middle_way:
        print('from middle way start to %s' % middle_way_current)
        middle_way = False
    else:
        print('from home page')
    print('transfer')


def transaction(params: WorkFlowParams) -> NoReturn:
    global self, middle_way
    if middle_way:
        print('from middle way start to %s' % middle_way_current)
        middle_way = False
    else:
        print('from home page')
    print('transaction')


def receipt() -> NoReturn:
    global self, middle_way
    if middle_way:
        print('from middle way start to %s' % middle_way_current)
        middle_way = False
    else:
        print('from home page')
    print('receipt')


def go_home() -> NoReturn:
    global self, middle_way
    print('go home')
    global from_path, to_path
    from_path = ['A', 'B', 'C', 'D', 'E']
    to_path = ['A', 'B', 'G', 'H', 'I']

    def go_to_step():
        global self
        self.press("back")
        print('going')

    go_to_path = GoToPath(from_path, to_path, go_to_step)
    idx = go_to_path.to_go()
    if idx != 0:
        middle_way = True
    else:
        middle_way = False


def break_workflow() -> BreakRes:
    global self
    print('break workflow')
    return BreakRes()


def input_sms(params: WorkFlowParams) -> NoReturn:
    global self
    print('break workflow')


def do_work(workflow: settings.WorkFlow, params=WorkFlowParams()):
    if workflow == settings.WorkFlow.START:
        start(self, package)
    elif workflow == settings.WorkFlow.STOP:
        stop(self, package)
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
