import enum
from enum import auto

__all__ = ['ErrorCategory', 'BotErrorMsg', 'BotErrorBase', 'BotStopError', 'BotCategoryError', 'BotParseError',
           'BotSessionExpiredError', 'BotRunningError', 'BotLogicRetryError', 'BotErrorHelper']


@enum.unique
class ErrorCategory(enum.Enum):
    Data = auto(), '数据错误'  # 数据错误，后台信息提供错误
    BankWarning = auto(), '银行提示'  # 银行提示错误，如 银行维护提示
    ParseWrong = auto(), '解析异常'  # 解析异常，如 解析不到期望节点
    Environment = auto(), '环境异常'  # 环境异常，如 密码输入错误
    Network = auto(), '网络异常'  # 网络异常，如 加载失败

    def __init__(self, _value: str, _description: str = ''):
        self._value_ = _value
        self._description_ = _description

    def __str__(self):
        return f'{self.name}, {self.description}'

    @property
    def description(self):
        return self._description_


class BotErrorMsg:
    NotMatchedCardNo = '未找到录入卡号匹配的银行卡，请检查确认后重试'


class BotErrorBase(Exception):
    msg: str  # 错误消息
    is_stop: bool = False  # 是否停止处理，停止银行卡运行，并通知后台

    def __init__(self, msg: str, is_stop=False):
        super().__init__(msg, is_stop)
        self.msg = msg
        self.is_stop = is_stop

    def full_msg(self):
        return self.msg


class BotStopError(BotErrorBase):

    def __init__(self, msg: str):
        super().__init__(msg=msg, is_stop=True)


class BotCategoryError(BotErrorBase):

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

    def __init__(self, msg: str, is_stop=False):
        super().__init__(ErrorCategory.ParseWrong, msg, is_stop)


class BotSessionExpiredError(BotErrorBase):

    @staticmethod
    def throw_if(condition: bool, msg):
        if condition:
            raise BotSessionExpiredError(msg=msg)


class BotRunningError(BotErrorBase):
    pass


class BotLogicRetryError(BotErrorBase):
    pass


class BotErrorHelper:

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
