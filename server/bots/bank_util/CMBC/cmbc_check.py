from typing import Callable

import uiautomator2 as u2

from server import settings
from server.common_helpers import StrHelper
from server.bots.act_scheduler.bot_activity_abstracts import ActivityCheckContext
from server.bots.act_scheduler.bot_scheduler import BotActionWatcher
from server.bots.act_scheduler.bot_exceptions import *


class CMBCActionWatcher(BotActionWatcher):
    """执行全局监听检查，跳转页面过程中处理"""

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = CMBCErrorChecker.check(ctx.d, ctx.source)
        return result


class CMBCErrorChecker:
    """CMBC 运行错误检查"""

    @staticmethod
    def check(d: u2.Device, source=None, prior_func: Callable[[str], bool] = None) -> (bool, str):
        """
        检查错误
        True 为有错误并已处理(外部需要重刷页面进行处理)
        False 为无错误
        Error 为自定义异常，外部拦截处理
        """
        # 更新版本
        x_update = d.xpath('//*[contains(@resource-id,"cn.com.cmbc.newmbank:id/text_tv")][contains(@text,"以后再说")]',
                           source)
        if x_update.exists:
            settings.log(f'检测到App更新提示')
            x_update.click()
            return True, '检测到App更新提示'
        # 温馨提示
        x_error_msg = d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/unify_dialog_message"]', source)
        if x_error_msg.exists:
            is_cancel = False
            try:
                error_msg = x_error_msg.get_text()
                settings.log(f'检测到银行提示: {error_msg}')

                # 如果前置函数已处理，则不做错误提示
                if prior_func is not None and prior_func(error_msg):
                    return False, error_msg

                if StrHelper.contains('网络环境不稳定', error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg)
                if StrHelper.contains('通信超时', error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg)
                if StrHelper.contains('会话超时', error_msg) or StrHelper.contains('请重新登录', error_msg):
                    raise BotSessionExpiredError(error_msg)
                if StrHelper.contains('密码不能小于6位', error_msg):
                    raise BotSessionExpiredError(error_msg)  # 有可能输入错误导致
                if StrHelper.contains('用户名或密码错误', error_msg):
                    raise BotCategoryError(ErrorCategory.Data, msg=error_msg, is_stop=True)
                if StrHelper.contains('未签约手机银行', error_msg):
                    raise BotCategoryError(ErrorCategory.Data, msg=error_msg, is_stop=True)
                if StrHelper.contains('您需要阅读《中国民生银行隐私政策》后勾选同意', error_msg):
                    raise BotLogicRetryError(error_msg)  # 登录时无法识别是否已选中，只能通过提示后再次点击
                if StrHelper.contains('确定要退出系统', error_msg):
                    is_cancel = True
                """
                密码不能小于6位，请核对后重新输入！
                您需要阅读《中国民生银行隐私政策》后勾选同意。
                登录失败，您的网络不稳定[001016]
                您未签约手机银行，请点击自助注册按钮进行签约
                用户名或密码错误，连续错误5次后锁定，已错误1次。
                会话超时，请重新登录
                通信超时,资金类交易请核对账户信息!
                网络环境不稳定，请稍候重试。
                您确定要退出系统吗?
                """
                # raise BotCategoryError(ErrorCategory.BankWarning, error_msg)
                return True, error_msg
            finally:
                # 关闭提示，取消 or 确定
                if is_cancel:
                    d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/unify_dialog_negative_btn"]', source) \
                        .click_exists(0.1)
                else:
                    d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/unify_dialog_positive_btn"]', source) \
                        .click_exists(0.1)

        return False, None
