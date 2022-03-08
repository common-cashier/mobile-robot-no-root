import os
from datetime import datetime
import unittest

import uiautomator2 as u2

os.chdir('../../')

from server.bots.act_scheduler.bot_exceptions import BotErrorBase, BotCategoryError
from server.bots.bank_util.BCM.bcm_helper import BCMHelper
from server.bots.bank_util.BCM.bcm_check import BCMErrorChecker
from server.bots.bank_util.BCM.bcm_keyboard import BCMTransferPwdKeyboard

_d = u2.Device()


def get_moq_path(file):
    return f'banks/bcm/response/{file}'


class BCMHelperTestCase(unittest.TestCase):

    def test_cn_to_datetime(self):
        cn_to_datetime = BCMHelper.cn_to_datetime

        self.assertEqual(datetime(2022, 1, 10, 18, 55, 37), cn_to_datetime('二零二二年一月十日十八时五十五分三十七秒'))
        self.assertEqual(datetime(2021, 8, 13, 19, 58, 46), cn_to_datetime('二零二一年八月十三日十九时五十八分四十六秒'))
        self.assertEqual(datetime(2021, 12, 23, 15, 48, 32), cn_to_datetime('二零二一年十二月二十三日十五时四十八分三十二秒'))
        self.assertEqual(datetime(2021, 12, 23, 23, 48, 32), cn_to_datetime('二零二一年十二月二十三日二十三时四十八分三十二秒'))
        self.assertEqual(datetime(2022, 1, 2, 3, 4, 5), cn_to_datetime('二零二二年一月二日三时四分五秒'))
        self.assertEqual(datetime(2022, 10, 20, 13, 40, 50), cn_to_datetime('二零二二年十月二十日十三时四十分五十秒'))

    def test_cn_to_number(self):
        cn_to_number = BCMHelper.cn_to_number

        self.assertEqual('9912900000153300', cn_to_number('九九一二九零零零零零一五三三零零'))
        self.assertEqual('6226226404801234', cn_to_number('六二二六二二六四零四八零一二三四'))
        self.assertEqual('0123456789', cn_to_number('零一二三四五六七八九'))


class BCMErrorCheckTestCase(unittest.TestCase):

    def test_pay_pwd_error(self):
        with self.assertRaises(BotCategoryError) as cm:
            with open(get_moq_path('04. transfer/transfer_input_pay_pwd_error.xml'), encoding='utf-8') as f:
                _source = f.read()
                BCMErrorChecker.check(_d, _source)
        error = cm.exception
        self.assertTrue(error.is_stop)
        self.assertIn('安全控件创建失败', error.msg)

    def test_login_error(self):
        with self.assertRaises(BotErrorBase) as cm:
            with open(get_moq_path('error/提示-用户名密码错误.xml'), encoding='utf-8') as f:
                _source = f.read()
                BCMErrorChecker.check(_d, _source)
        error = cm.exception
        self.assertTrue(error.is_stop)
        self.assertIn('用户名或密码错误', error.msg)


class BCMPwdKeyboardTestCase(unittest.TestCase):

    def test_kb_find(self):
        kb = BCMTransferPwdKeyboard(_d, '//*[@resource-id="com.bankcomm.Bankcomm:id/digitkeypadlayout"]')
        pwd = '70469'
        [kb.input(_s, 0.1) for _s in pwd]
        _d.sleep(5)
        [kb.input_delete() for _ in pwd]
