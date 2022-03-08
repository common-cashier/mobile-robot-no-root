from typing import Callable

import uiautomator2 as u2

from server.bots.act_scheduler import *
from server.common_helpers import StrHelper
from server.settings import log as common_log

__all__ = ['HRBActionWatcher', 'HRBErrorChecker']


class HRBActionWatcher(BotActionWatcher):
    """执行全局监听检查，跳转页面过程中处理"""

    def check(self, ctx: ActivityCheckContext) -> bool:
        result, _ = HRBErrorChecker.check(ctx.d, ctx.source)
        return result


class HRBErrorChecker:
    """运行错误检查"""

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

        # 温馨提示
        x_error_msg = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/message"]', source)
        if x_error_msg.exists:
            try:
                error_msg = x_error_msg.get_text()
                common_log(f'检测到银行提示: {error_msg}')

                # 如果前置函数已处理，则不做错误提示
                if prior_func is not None and prior_func(error_msg):
                    return False, error_msg

                if StrHelper.any_contains(['网络连接失败'], error_msg):
                    raise BotCategoryError(ErrorCategory.Network, error_msg)
                if StrHelper.any_contains(['用户会话超时', '请重新登录'], error_msg):
                    raise BotSessionExpiredError(error_msg)
                if StrHelper.any_contains(['登录密码错误'], error_msg):
                    raise BotCategoryError(ErrorCategory.Data, msg=error_msg, is_stop=True)

                """
                登录密码错误，您当日已错误1次,当日还剩4次机会!如您为老网银移植客户，请尝试使用证件号码登录
                
                网络连接失败，请稍后重试

                当前用户会话超时，请重新登录
                """
                # raise BotCategoryError(ErrorCategory.BankWarning, error_msg)
                return True, error_msg
            finally:
                # 关闭提示，重试、确定
                x_retry = d.xpath('//*[@text="重试"][@resource-id="com.yitong.hrb.people.android:id/no"]', source)
                x_ok = d.xpath('//*[@text="确定"][@resource-id="com.yitong.hrb.people.android:id/yes"]', source)
                if x_retry.exists:
                    x_retry.click()
                elif x_ok.exists:
                    x_ok.click()

        return False, None
