<<<<<<< HEAD
from typing import Callable

import uiautomator2 as u2

from server import settings
from server.common_helpers import StrHelper
from server.bots.act_scheduler.bot_activity_abstracts import ActivityCheckContext
from server.bots.act_scheduler.bot_scheduler import BotActionWatcher
from server.bots.act_scheduler.bot_exceptions import *

__all__ = ['BCMActionWatcher', 'BCMErrorChecker']


class BCMActionWatcher(BotActionWatcher):

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = BCMErrorChecker.check(ctx.d, ctx.source)
        return result


class BCMErrorChecker:

    @staticmethod
    def check(d: u2.Device, source=None, prior_func: Callable[[str], bool] = None) -> (bool, str):
        x_popup_close = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/popup_close"]', source)
        if x_popup_close.exists:
            settings.log(f'检测到活动提示')
            x_popup_close.click()
            return True, '检测到活动提示'

        x_alert_title = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/tvCommonAlertTitle"]', source)
        if x_alert_title.exists and x_alert_title.get_text():
            try:
                error_msg = x_alert_title.get_text()
                x_alert_attach = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/tvCommonAlertAttach"]', source)
                error_detail = x_alert_attach.get_text() if x_alert_attach.exists else ''
                settings.log(f'检测到转账失败提示：{error_msg}，详情：{error_detail}')
                raise BotCategoryError(ErrorCategory.ParseWrong, msg=error_msg, is_stop=True)
            finally:
                d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/lbtCommonAlertOK"]', source).click_exists(0.1)

        x_toast_tips = d.xpath('//android.webkit.WebView/*[last()][string-length(@text)>0]', source)
        if x_toast_tips.exists:
            error_msg = x_toast_tips.get_text()
            if StrHelper.contains('用户名或密码错误', error_msg):
                raise BotCategoryError(ErrorCategory.Data, msg=error_msg, is_stop=True)

        tips_continue_xpath = '//android.app.Dialog//android.widget.Button[@text="继续转账"]'
        x_tips_continue = d.xpath(tips_continue_xpath, source)
        if x_tips_continue.exists:
            try:
                x_tips_text = d.xpath(f'{tips_continue_xpath}/../preceding-sibling::*[1]/android.view.View[1]', source)
                error_msg = x_tips_text.get_text() if x_tips_text.exists else ''
                settings.log(f'检测到转账提示: {error_msg}')

                return True, error_msg
            finally:
                x_tips_continue.click_exists(0.1)

        tips_close_xpath = '//android.app.Dialog//android.widget.Button[@text="关闭"]'
        x_tips_close = d.xpath(tips_close_xpath, source)
        if x_tips_close.exists:
            try:
                x_tips_text = d.xpath(f'{tips_close_xpath}/../following-sibling::*[1]/android.view.View[1]', source)
                error_msg = x_tips_text.get_text() if x_tips_text.exists else ''
                settings.log(f'检测到银行提示: {error_msg}')

                if prior_func is not None and prior_func(error_msg):
                    return False, error_msg

                if StrHelper.contains('服务器在忙', error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg)
                if StrHelper.contains('网络环境不佳', error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg, is_stop=True)
                return True, error_msg
            finally:
                x_tips_close.click_exists(0.1)

        return False, None
=======
from typing import Callable

import uiautomator2 as u2

from server import settings
from server.common_helpers import StrHelper
from server.bots.act_scheduler.bot_activity_abstracts import ActivityCheckContext
from server.bots.act_scheduler.bot_scheduler import BotActionWatcher
from server.bots.act_scheduler.bot_exceptions import *

__all__ = ['BCMActionWatcher', 'BCMErrorChecker']


class BCMActionWatcher(BotActionWatcher):

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = BCMErrorChecker.check(ctx.d, ctx.source)
        return result


class BCMErrorChecker:

    @staticmethod
    def check(d: u2.Device, source=None, prior_func: Callable[[str], bool] = None) -> (bool, str):
        x_popup_close = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/popup_close"]', source)
        if x_popup_close.exists:
            settings.log(f'检测到活动提示')
            x_popup_close.click()
            return True, '检测到活动提示'

        x_alert_title = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/tvCommonAlertTitle"]', source)
        if x_alert_title.exists and x_alert_title.get_text():
            try:
                error_msg = x_alert_title.get_text()
                x_alert_attach = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/tvCommonAlertAttach"]', source)
                error_detail = x_alert_attach.get_text() if x_alert_attach.exists else ''
                settings.log(f'检测到转账失败提示：{error_msg}，详情：{error_detail}')
                raise BotCategoryError(ErrorCategory.ParseWrong, msg=error_msg, is_stop=True)
            finally:
                d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/lbtCommonAlertOK"]', source).click_exists(0.1)

        x_toast_tips = d.xpath('//android.webkit.WebView/*[last()][string-length(@text)>0]', source)
        if x_toast_tips.exists:
            error_msg = x_toast_tips.get_text()
            if StrHelper.contains('用户名或密码错误', error_msg):
                raise BotCategoryError(ErrorCategory.Data, msg=error_msg, is_stop=True)

        tips_continue_xpath = '//android.app.Dialog//android.widget.Button[@text="继续转账"]'
        x_tips_continue = d.xpath(tips_continue_xpath, source)
        if x_tips_continue.exists:
            try:
                x_tips_text = d.xpath(f'{tips_continue_xpath}/../preceding-sibling::*[1]/android.view.View[1]', source)
                error_msg = x_tips_text.get_text() if x_tips_text.exists else ''
                settings.log(f'检测到转账提示: {error_msg}')

                return True, error_msg
            finally:
                x_tips_continue.click_exists(0.1)

        tips_close_xpath = '//android.app.Dialog//android.widget.Button[@text="关闭"]'
        x_tips_close = d.xpath(tips_close_xpath, source)
        if x_tips_close.exists:
            try:
                x_tips_text = d.xpath(f'{tips_close_xpath}/../following-sibling::*[1]/android.view.View[1]', source)
                error_msg = x_tips_text.get_text() if x_tips_text.exists else ''
                settings.log(f'检测到银行提示: {error_msg}')

                if prior_func is not None and prior_func(error_msg):
                    return False, error_msg

                if StrHelper.contains('服务器在忙', error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg)
                if StrHelper.contains('网络环境不佳', error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg, is_stop=True)
                return True, error_msg
            finally:
                x_tips_close.click_exists(0.1)

        return False, None
>>>>>>> 9106ec0777a2e9e0e3255c47bc883216c62945f8
