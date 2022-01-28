from typing import NoReturn
import uiautomator2 as u2
from server.obj_factory import bot_util
from server import settings


# 公共启动方法
def start(d: u2.Device, package):
    d.screen_on()
    settings.bot.pid = d.app_start(package)
    return d.app_wait(package)  # 等待应用运行, return pid(int)


# 公共停止方法
def stop(d: u2.Device, package, callback=None):
    if callback:
        callback()
    d.sleep(1)
    d.app_stop(package)
    try:
        d.set_fastinput_ime(enable=False)
    finally:
        d.app_stop('com.termux')


# 公共重置工作流
def reset_workflow() -> NoReturn:
    bot_util.cast_work_flow()
