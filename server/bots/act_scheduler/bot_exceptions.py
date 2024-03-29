import enum
from enum import auto

__all__ = ['ErrorCategory', 'BotErrorMsg', 'BotErrorBase', 'BotStopError', 'BotCategoryError', 'BotParseError',
           'BotSessionExpiredError', 'BotRunningError', 'BotTransferFailedError', 'BotLogicRetryError',
           'BotErrorHelper']


@enum.unique
class ErrorCategory(enum.Enum):
    """错误分类"""
    # Unknown = auto(), '未知异常'  # 未知异常，避免使用
    # Server = auto(), '服务端异常'  # 服务端交互异常，服务端返回数据中带有异常信息，解密消息出错
    Data = auto(), '数据错误'  # 数据错误，后台信息提供错误
    BankWarning = auto(), '银行提示'  # 银行提示错误，如 银行维护提示
    ParseWrong = auto(), '解析异常'  # 解析异常，如 解析不到期望节点
    Environment = auto(), '环境异常'  # 环境异常，如 密码输入错误
    Network = auto(), '网络异常'  # 网络异常，如 加载失败

    def __init__(self, _value: str, _description: str = ''):
        # print(f'__init__ {_value} {self.name}')
        self._value_ = _value
        self._description_ = _description

    def __str__(self):
        return f'{self.name}, {self.description}'

    @property
    def description(self):
        return self._description_


class BotErrorMsg:
    """卡机错误信息"""
    NotMatchedCardNo = '未找到录入卡号匹配的银行卡，请检查确认后重试'


class BotErrorBase(Exception):
    """自动机异常基类"""
    msg: str  # 错误消息
    is_stop: bool = False  # 是否停止处理，停止银行卡运行，并通知后台

    def __init__(self, msg: str, is_stop=False):
        super().__init__(msg, is_stop)
        self.msg = msg
        self.is_stop = is_stop

    def full_msg(self):
        return self.msg


class BotStopError(BotErrorBase):
    """自动机停止异常"""

    def __init__(self, msg: str):
        super().__init__(msg=msg, is_stop=True)


class BotCategoryError(BotErrorBase):
    """自动机分类异常"""

    @staticmethod
    def throw_if(condition: bool, category: ErrorCategory, msg):
        if condition:
            raise BotCategoryError(category, msg)

    def __init__(self, category: ErrorCategory, msg: str, is_stop=False):
        super().__init__(msg, is_stop)
        self.category = category

    def full_msg(self):
        return f'{self.category.description}-{self.msg}'


class BotParseError(BotCategoryError):
    """自动机解析异常"""

    def __init__(self, msg: str, is_stop=False):
        super().__init__(ErrorCategory.ParseWrong, msg, is_stop)


class BotSessionExpiredError(BotErrorBase):
    """会话超时异常"""

    @staticmethod
    def throw_if(condition: bool, msg):
        if condition:
            raise BotSessionExpiredError(msg=msg)


class BotRunningError(BotErrorBase):
    """自动机运行异常
    1. 配置错误导致异常
    """
    pass


class BotTransferFailedError(BotErrorBase):
    """转账失败异常，仅限已识别失败的情况"""


class BotLogicRetryError(BotErrorBase):
    """自动机重逻辑重试异常"""
    pass


class BotErrorHelper:
    """自动机异常帮助类"""

    @staticmethod
    def bot_throw_when(condition: bool, category: ErrorCategory, msg):
        if condition:
            raise BotCategoryError(category, msg)

    @staticmethod
    def is_session_expired(error: Exception):
        return isinstance(error, BotSessionExpiredError)

    @staticmethod
    def is_retryable(error: Exception):
        if isinstance(error, BotErrorBase) and error.is_stop:
            return False
        if isinstance(error, BotCategoryError):
            return error.category in [ErrorCategory.Network]
        if BotErrorHelper.is_logic_retry(error):
            return True
        return False

    @staticmethod
    def is_logic_retry(error: Exception):
        if isinstance(error, BotLogicRetryError):
            return True
        return False


if __name__ == '__main__':
    print(ErrorCategory.ParseWrong)
    print(ErrorCategory.ParseWrong.name)
    print(ErrorCategory.ParseWrong.value)
    print(ErrorCategory.ParseWrong.description)
    print(ErrorCategory.Network.description)
    print(ErrorCategory.Data.description)
    print(ErrorCategory.Environment.description)
