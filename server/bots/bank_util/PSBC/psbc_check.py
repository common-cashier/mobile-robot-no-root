from typing import Callable

import uiautomator2 as u2

from server.bots.act_scheduler import *
from server.bots.act_scheduler.u2_helpers import DeviceHelper
from server.common_helpers import StrHelper
from server.settings import log as common_log

__all__ = ['PSBCActionWatcher', 'PSBCErrorChecker']


class PSBCActionWatcher(BotActionWatcher):
    """执行全局监听检查，跳转页面过程中处理"""

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = PSBCErrorChecker.check(ctx.d, ctx.source)
        return result


class PSBCErrorChecker:
    """PSBC 运行错误检查"""

    @staticmethod
    def check(d: u2.Device, source=None, prior_func: Callable[[str], bool] = None) -> (bool, str):
        """检查错误，True 为有错误并已处理(外部需要重刷页面进行处理)，False 为无错误， Error 为自动机异常"""

        # ViVo Payment Risk
        x_ignore_risk = d.xpath('//*[@resource-id="android:id/button2"][contains(@text,"Ignore risks")]',
                                source)
        if x_ignore_risk.exists:
            common_log(f'watcher: {x_ignore_risk.get_text()}')
            d.sleep(0.5)  # 避免获取的是未渲染全的结构
            d.xpath(x_ignore_risk.get().get_xpath()).click()
            # 此处会关闭 usb 调试，可能识别有误差
            # x_ignore_risk.click()
            return True, None

        # 启动时更新提示，后判断 activity ，加载较慢
        ui_cancel = d.xpath('//*[@text="暂不更新"]', source)
        if ui_cancel.exists:
            # com.yitong.mbank.psbc.android.activity.SplashActivity
            if DeviceHelper.is_activity_contains(d, '.android.activity.SplashActivity'):
                ui_cancel.click_exists(timeout=1)
                common_log(f'提示更新: 暂不更新')
                return True, None

        # 首页提示广告弹窗
        ad_close = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/iv_cross_marketing_close"]', source)
        if ad_close.exists:
            ad_close.click()
            common_log(f'提示广告: 关闭')
            return True, None

        # 转账确认后需二次验证
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

        # 温馨提示 - 继续转账
        tips_continue_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/dialog_sure_cancel_ll"]//*[@text="继续转账"]'
        x_tips_continue = d.xpath(tips_continue_xpath, source)
        if x_tips_continue.exists:
            try:
                x_error_msg = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/sc_dialog_msg_txt"]', source)
                error_msg = x_error_msg.get_text() if x_error_msg.exists else ''
                common_log(f'检测到转账提示: {error_msg}')

                # 您今日已提交过向该账户同等金额的转账，您可先查询上一笔转账情况，避免重复转账。请确认是否继续该笔转账。
                return True, error_msg
            finally:
                # 关闭提示
                x_tips_continue.click_exists(0.1)

        # 温馨提示
        x_error_msg = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/sc_dialog_msg_txt"]', source)
        if x_error_msg.exists:
            try:
                error_msg = x_error_msg.get_text()
                common_log(f'检测到银行提示: {error_msg}')

                # 如果前置函数已处理，则不做错误提示
                if prior_func is not None and prior_func(error_msg):
                    return False, error_msg
                elif StrHelper.contains('没有符合条件的记录', error_msg):
                    return False, error_msg

                if StrHelper.contains('请阅读《电子银行隐私政策》后勾选同意', error_msg):
                    # 登录时无法识别是否已选中，只能通过提示后再次点击
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
                # 重新登录后可解决
                if StrHelper.any_contains(['未查询对应客户信息'], error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, msg=error_msg, is_stop=True)
                # 登录后需要设备绑定，一直加载中，然后出错
                if StrHelper.any_contains(['查询首次登录信息错误'], error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, msg=error_msg, is_stop=True)
                if StrHelper.any_contains(['转账金额大于当前可用余额', '短信验证码不一致'], error_msg):
                    raise BotCategoryError(ErrorCategory.BankWarning, msg=error_msg)

                """
                没有符合条件的记录，请切换查询条件试试[204015]

                请阅读《电子银行隐私政策》后勾选同意
                登录密码不能为空
                验证码不能为空
                登录密码输入的长度不能小于6位，请重新输入
                您的手机号或登录密码输入错误，请认真核对后重新输入。如您未注册过手机银行，请先注册。
                查询首次登录信息错误
                
                服务开小差，若您正在进行动账交易，请查询交易明细或余额确认交易是否成功[-900]
                您当前处于网络代理环境，请确保在安全的网络环境下使用手机银行。
                网络异常，请检查网络连接
                网络连接失败，请稍后重试
                服务请求异常，请稍候重试！
                与后台业务系统通讯异常[CODE:QD001000]
                查询系统时间错误,请返回重试!

                您的登录信息已经超时，请重新登录！
                
                转账金额大于当前可用余额！
                短信验证码不一致[CODE:QD000031]
                您今日已提交过向该账户同等金额的转账，您可先查询上一笔转账情况，避免重复转账。请确认是否继续该笔转账。
                未查询对应客户信息[CODE:QD000024]
                """
                # raise BotCategoryError(ErrorCategory.BankWarning, error_msg)
                return True, error_msg
            finally:
                # 关闭提示
                d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/tvDialogConfirm"]', source).click_exists(0.1)

        return False, None
