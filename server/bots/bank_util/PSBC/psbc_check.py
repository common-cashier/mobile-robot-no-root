from typing import Callable

import uiautomator2 as u2

from server.bots.act_scheduler import *
from server.bots.act_scheduler.u2_helpers import DeviceHelper
from server.common_helpers import StrHelper
from server.settings import log as common_log

__all__ = ['PSBCActionWatcher', 'PSBCErrorChecker']


class PSBCActionWatcher(BotActionWatcher):

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = PSBCErrorChecker.check(ctx.d, ctx.source)
        return result


class PSBCErrorChecker:

    @staticmethod
    def check(d: u2.Device, source=None, prior_func: Callable[[str], bool] = None) -> (bool, str):

        x_ignore_risk = d.xpath('//*[@resource-id="android:id/button2"][contains(@text,"Ignore risks")]',
                                source)
        if x_ignore_risk.exists:
            common_log(f'watcher: {x_ignore_risk.get_text()}')
            d.sleep(0.5)  # 避免获取的是未渲染全的结构
            d.xpath(x_ignore_risk.get().get_xpath()).click()
            return True, None

        ui_cancel = d.xpath('//*[@text="暂不更新"]', source)
        if ui_cancel.exists:
            if DeviceHelper.is_activity_contains(d, '.android.activity.SplashActivity'):
                ui_cancel.click_exists(timeout=1)
                common_log(f'提示更新: 暂不更新')
                return True, None

        ad_close = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/iv_cross_marketing_close"]', source)
        if ad_close.exists:
            ad_close.click()
            common_log(f'提示广告: 关闭')
            return True, None

        x_safe_dialog = d.xpath('//*[@resource-id="_safeDialog"]', source)
        if x_safe_dialog.exists:
            safe_dialog_xpath = x_safe_dialog.get().get_xpath()
            try:
                x_tips = d.xpath(safe_dialog_xpath, source).child('//*[@resource-id="_form_risk0"]/*[1]/*[1]')
                error_msg = x_tips.get_text()
                common_log(f'检测到银行安全提示: {error_msg}')
                if StrHelper.contains('进行人脸识别', error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, error_msg, is_stop=True)
                return True, error_msg
            finally:
                d.xpath(safe_dialog_xpath, source).child('//*[@resource-id="dialogButton"]').click_exists(0.2)

        tips_continue_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/dialog_sure_cancel_ll"]//*[@text="继续转账"]'
        x_tips_continue = d.xpath(tips_continue_xpath, source)
        if x_tips_continue.exists:
            try:
                x_error_msg = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/sc_dialog_msg_txt"]', source)
                error_msg = x_error_msg.get_text() if x_error_msg.exists else ''
                common_log(f'检测到转账提示: {error_msg}')

                return True, error_msg
            finally:
                x_tips_continue.click_exists(0.1)

        x_error_msg = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/sc_dialog_msg_txt"]', source)
        if x_error_msg.exists:
            try:
                error_msg = x_error_msg.get_text()
                common_log(f'检测到银行提示: {error_msg}')

                if prior_func is not None and prior_func(error_msg):
                    return False, error_msg
                elif StrHelper.contains('没有符合条件的记录', error_msg):
                    return False, error_msg

                if StrHelper.contains('请阅读《电子银行隐私政策》后勾选同意', error_msg):
                    raise BotLogicRetryError(error_msg)
                if StrHelper.any_contains(['网络异常', '网络连接失败', '服务请求异常',
                                           '服务开小差', '与后台业务系统通讯异常', '查询系统时间错误'], error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg)
                if StrHelper.any_contains(['登录信息已经超时', '请重新登录'], error_msg):
                    raise BotSessionExpiredError(error_msg)
                if StrHelper.contains('登录密码输入的长度不能小于', error_msg):
                    raise BotSessionExpiredError(error_msg)
                if StrHelper.any_contains(['用户名或密码错误', '未注册过手机银行'], error_msg):
                    raise BotCategoryError(ErrorCategory.Data, msg=error_msg, is_stop=True)
                if StrHelper.any_contains(['未查询对应客户信息'], error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, msg=error_msg, is_stop=True)
                if StrHelper.any_contains(['查询首次登录信息错误'], error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, msg=error_msg, is_stop=True)
                if StrHelper.any_contains(['转账金额大于当前可用余额', '短信验证码不一致'], error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, msg=error_msg)

                return True, error_msg
            finally:
                d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/tvDialogConfirm"]', source).click_exists(0.1)

        return False, None
