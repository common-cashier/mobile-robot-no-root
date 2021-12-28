import sys

sys.path.append("../..")
import settings


def start(self, package):
    self.screen_on()
    settings.bot.pid = self.app_start(package)
    return self.app_wait(package)  # 等待应用运行, return pid(int)


def stop(self, package):
    self.sleep(1)
    self.app_stop(package)
    self.app_stop('com.termux')
