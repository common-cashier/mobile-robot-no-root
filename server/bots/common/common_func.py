from typing import NoReturn
import uiautomator2 as u2
from server.obj_factory import bot_util
from server import settings


def start(d: u2.Device, package):
    d.screen_on()
    settings.bot.pid = d.app_start(package)
    return d.app_wait(package)  # 等待应用运行, return pid(int)


def stop(d: u2.Device, package, callback=None):
    if callback:
        callback()
    d.sleep(1)
    d.app_stop(package)
    try:
        d.set_fastinput_ime(enable=False)
    finally:
        d.app_stop('com.termux')


def reset_workflow() -> NoReturn:
    bot_util.cast_work_flow()
