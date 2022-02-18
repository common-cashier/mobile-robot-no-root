from typing import Callable

import uiautomator2 as u2

from server import settings
from server.common_helpers import StrHelper
from server.bots.act_scheduler.bot_activity_abstracts import ActivityCheckContext
from server.bots.act_scheduler.bot_scheduler import BotActionWatcher
from server.bots.act_scheduler.bot_exceptions import *

__all__ = ['CMBCErrorChecker', 'CMBCActionWatcher']


class CMBCActionWatcher(BotActionWatcher):

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = CMBCErrorChecker.check(ctx.d, ctx.source)
        return result


class CMBCErrorChecker:

    @staticmethod
    def check(d: u2.Device, source=None, prior_func: Callable[[str], bool] = None) -> (bool, str):
        x_update = d.xpath('//*[contains(@resource-id,"cn.com.cmbc.newmbank:id/text_tv")][contains(@text,"以后再说")]',
                           source)
        if x_update.exists:
            settings.log(f'检测到App更新提示')
            x_update.click()
            return True, '检测到App更新提示'
        x_error_msg = d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/unify_dialog_message"]', source)
        if x_error_msg.exists:
            is_cancel = False
            try:
                error_msg = x_error_msg.get_text()
                settings.log(f'检测到银行提示: {error_msg}')

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
                    raise BotLogicRetryError(error_msg)
                if StrHelper.contains('确定要退出系统', error_msg):
                    is_cancel = True
                return True, error_msg
            finally:
                if is_cancel:
                    d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/unify_dialog_negative_btn"]', source) \
                        .click_exists(0.1)
                else:
                    d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/unify_dialog_positive_btn"]', source) \
                        .click_exists(0.1)

        return False, None
