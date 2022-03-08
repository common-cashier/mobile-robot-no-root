import time
import re
from datetime import datetime
from typing import Callable, Optional, Union, List

import uiautomator2 as u2

from server import settings
from server.models import Transaction, Transferee, Receipt

from server.common_helpers import StrHelper, DateTimeHelper
from server.bots.act_scheduler import *
from server.bots.act_scheduler.u2_helpers import DeviceHelper, XPathHelper
from server.bots.act_scheduler.bot_helpers import BotHelper
from server.bots.common.common_models import DistinctList

from server.bots.bank_util.HARBINBANK.hrb_keyboard import *
from server.bots.bank_util.HARBINBANK.hrb_helper import *
from server.bots.bank_util.HARBINBANK.hrb_check import *


_package = 'com.yitong.hrb.people.android'


class HRBActivityExecutorBase(BotActivityExecutor):
    def _dump_hierarchy(self, d, check_error=True):
        retry_limit = 5
        while True:
            source = super()._dump_hierarchy(d, check_error=check_error)
            if check_error:
                had_error, error_msg = HRBErrorChecker.check(d, source)
                if had_error:
                    retry_limit -= 1
                    if retry_limit < 0:
                        raise BotRunningError(f'加载图层一直检测到错误: {error_msg}')
                    self._log(f'检测到错误，重新加载图层: {error_msg}')
                    d.sleep(1)
                    continue
            break
        return source

    def _retry_logic(self, times: int, func: Callable):
        error_msg = None
        while times > 0:
            times -= 1
            try:
                result = func(error_msg=error_msg)
                return True, result
            except BotLogicRetryError as error:
                error_msg = error.msg
                self._log(f'检测到重试错误: {error.msg}')
                time.sleep(1)
        return False, None

    def _wait_loading(self, d: u2.Device):
        _r = self._exec_retry('等待加载完成', retry_limit=60, interval_second=1,
                              func=lambda: not self._is_loading(d))
        if not _r:
            raise BotParseError('加载页面失败，一直提示加载中')

    def _is_loading(self, d: u2.Device, source: str = None):
        source = source or self._dump_hierarchy(d)
        x_load = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/tvProgress"]', source)
        return x_load.exists and StrHelper.contains('加载', x_load.get_text())

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self._tooltip_back(ctx.d, ctx.source)

    def _tooltip_back(self, d: u2.Device, _source: str = None, wait_second: float = 0):
        _source = _source or self._dump_hierarchy(d)
        is_toolbar_back = HRBHelper.go_back(d, _source)
        if is_toolbar_back:
            self._log(f'点击页面返回')
        else:
            self._log(f'点击手机返回')
        if wait_second:
            d.sleep(wait_second)


class HRBMainActivityExecutor(HRBActivityExecutorBase):
    _main_activity = ['com.yitong.hrb.people.android.activity.MainActivity']

    def check(self, ctx: ActivityCheckContext):
        return StrHelper.any_contains(self._main_activity, ctx.current_activity)

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        account_xpath = '//*[@resource-id="com.yitong.hrb.people.android:id/tv_menu"][@text="我的账户"]'
        x_account = ctx.d.xpath(account_xpath, ctx.source)
        if not x_account.exists:
            ctx.d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/tv_home"][@text="首页"]').click_exists(1)
            ctx.d.sleep(1)
            ctx.reset()

        if target_type == BotActivityType.Login or target_type == BotActivityType.QueryAccount:
            ctx.d.xpath(account_xpath, ctx.source).click_exists(1)
        elif target_type == BotActivityType.TransferIndex:
            ctx.d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/llSmartTransfer"][@text="智能转账"]').click_exists(1)


class HRBLoginActivityExecutor(HRBActivityExecutorBase):
    _login_activity = ['com.yitong.hrb.people.android.activity.LoginActivity']

    def check(self, ctx: ActivityCheckContext):
        return StrHelper.any_contains(self._login_activity, ctx.current_activity)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入登录页')
        account = ctx.account
        d = ctx.d

        _r = self._exec_retry('检查登录账号', retry_limit=60, func=lambda: self._check_exist_name(d))
        if not _r:
            raise BotParseError('未检测到已登录账号，请先手动登录成功')
        elif _r == 'exist':
            self._log('检测到之前登录成功过')

        self._log('输入登录密码')
        _r = self._exec_retry('输入登录密码', retry_limit=3, func=lambda: self._input_pwd(d, account.login_pwd))
        if not _r:
            raise BotParseError('输入登录密码错误', is_stop=True)

        self._log('点击登录')
        d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/login_btn_to_login"]').click()
        if self._exec_retry('登录结果检查', retry_limit=60, func=lambda: self._login_result_check(d)):
            self._log('登录成功')
        else:
            raise BotParseError('未检查到登录结果', is_stop=True)

    def _input_pwd(self, d: u2.Device, login_pwd: str) -> bool:
        pwd_xpath = '//*[@resource-id="com.yitong.hrb.people.android:id/login_safe_edit"]'
        self._log('点击密码框')
        d.xpath(pwd_xpath).click()
        d.sleep(0.5)
        d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/iv_clear_pwd"]').click_exists(0.1)
        kb = HRBLoginPwdKeyboard(d)
        [kb.input(_t, 0.2) for _t in login_pwd]
        kb.close()
        input_text = d.xpath(pwd_xpath).get_text()
        return len(input_text) == len(login_pwd)

    def _login_result_check(self, d: u2.Device):
        if not DeviceHelper.is_in_activity(d, self._login_activity):
            return True
        self._dump_hierarchy(d)
        return False

    def _check_exist_name(self, d: u2.Device) -> Union[str, bool]:
        _source = self._dump_hierarchy(d)
        x_exist_name = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/tv_username"]', _source)
        if x_exist_name.exists and x_exist_name.get_text():
            return 'exist'
        return False


class HRBAccountActivityExecutor(HRBActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return HRBHelper.is_eq_title(ctx.d, ctx.source, '我的账户') \
               and ctx.d.xpath('//*[@resource-id="saving-account"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入我的账户')
        d = ctx.d
        self._wait_loading(d)

        _r, card_info = self._retry_logic(30, lambda **_kwargs: self._get_card_info(ctx, **_kwargs))
        if not _r:
            raise BotParseError('未找到银行卡节点')
        balance = card_info.get('balance', 0)
        return {'balance': BotHelper.amount_fen(balance)}

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):

        _r, card_info = self._retry_logic(30, lambda **_kwargs: self._get_card_info(ctx, **_kwargs))
        if not _r:
            raise BotParseError('未找到银行卡节点')
        _source = self._dump_hierarchy(ctx.d)

        if target_type == BotActivityType.QueryTrans:
            self._log(f'点击明细按钮')
            x_trans_detail = ctx.d.xpath(card_info['transaction_xpath'], _source)
            x_trans_detail.click_exists(1)
        elif target_type == BotActivityType.Transfer or target_type == BotActivityType.TransferIndex:
            self._log(f'点击转账按钮')
            x_transfer = ctx.d.xpath(card_info['transfer_xpath'], _source)
            x_transfer.click_exists(1)

    def _get_card_info(self, ctx: ActivityExecuteContext, **_) -> dict:
        d = ctx.d

        x_card_list = d.xpath('//*[@resource-id="acctList"]//*[starts-with(@resource-id, "accountTpl")]')
        x_card_list.wait(20)
        _source = self._dump_hierarchy(d)
        card_list = x_card_list.all(_source)
        self._log(f'银行卡列表数量: {len(card_list)}')
        for item in card_list:
            item_xpath = item.get_xpath()
            card_info = self._parse_account(d, item_xpath, _source)
            card_mask = card_info['card_mask']
            if not BotHelper.is_match_card_num(card_mask, ctx.account.account):
                self._log(f'过滤不匹配卡号: {card_mask}')
                continue
            return card_info
        raise BotCategoryError(ErrorCategory.Data, BotErrorMsg.NotMatchedCardNo)

    @staticmethod
    def _parse_account(d: u2.Device, item_xpath: str, source: str = None):
        res = {'item_xpath': item_xpath, }
        child_texts = XPathHelper.get_all_texts(d, item_xpath, source)
        child_len = len(child_texts)
        for i in range(child_len):
            curr_text, curr_xpath = child_texts[i]
            next_text, next_xpath = None, None
            if i + 1 < child_len:
                next_text, next_xpath = child_texts[i + 1]

            if next_text and StrHelper.contains('余额', next_text):
                res['card_mask'] = HRBHelper.get_card_no(curr_text)
            elif StrHelper.contains('余额', curr_text) and next_text:
                balance_text = next_text
                if balance_text == '—.——':
                    raise BotLogicRetryError('未获取到余额，需等待重试')
                res['balance'] = HRBHelper.convert_amount(next_text)
            elif StrHelper.contains('转账', curr_text):
                res['transfer_xpath'] = curr_xpath
            elif StrHelper.contains('明细', curr_text):
                res['transaction_xpath'] = curr_xpath
        return res


class HRBTransactionActivityExecutor(HRBActivityExecutorBase):
    _distinct_list = DistinctList()
    _last_trans: Transaction
    _max_query_count: int
    _start_time: datetime
    _last_item_height: int = 0
    _list_swipe_height: int = 0
    _item_height: int = 0

    def check(self, ctx: ActivityCheckContext):
        return HRBHelper.is_eq_title(ctx.d, ctx.source, '交易明细') \
               and ctx.d.xpath('//*[@resource-id="form"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入流水页面')
        self._reset_data()  # 每次重置当前流水列表
        self._last_trans, self._max_query_count, self._start_time, _ = BotActionParameter.get_query_trans(**kwargs)

        d = ctx.d
        self._wait_loading(d)

        had_next = True
        while had_next:
            had_next, need_swipe = self._curr_list(ctx)
            self._log(f'当前流水条数: {self._distinct_list.count()}')
            if need_swipe:
                move = self._list_swipe_height - self._last_item_height
                self._log(f'分页滑动高度: {move} = {self._list_swipe_height} - {self._last_item_height}')
                DeviceHelper.swipe_up_until(ctx.d, ctx.win_size_height, move)

        trans_list = self._distinct_list.data_list()
        return BotHelper.sort_trans_list(trans_list)

    def _reset_data(self):
        self._distinct_list.reset()
        self._list_swipe_height = 0
        self._item_height = 0
        self._last_item_height = 0

    def _curr_list(self, ctx: ActivityExecuteContext) -> (bool, bool):
        d = ctx.d
        self._wait_loading(d)

        x_list = d.xpath('//*[@resource-id="form"]/*').wait(30)
        if not x_list:
            raise BotParseError('未获取到流水列表')
        d.sleep(0.5)

        if self._list_swipe_height == 0:
            _, _, _, l_height = d.xpath('//*[@resource-id="form"]').get().rect
            self._list_swipe_height = l_height

        _source = self._dump_hierarchy(d)
        item_list = d.xpath('//*[@resource-id="form"]/android.widget.ListView/*', _source).all()
        self._log(f'流水列表内容长度: {len(item_list)}')
        for item in item_list:
            item_values = d.xpath(item.get_xpath(), _source).child('/*').all()
            if len(item_values) == 0:
                continue
            _, _, _, item_height = item.rect
            self._last_item_height = item_height
            if not self._item_height:
                self._item_height = item_height
            if (item_height + 20) < self._item_height:
                continue
            item_key = self._get_item_key(item_values)
            if self._distinct_list.contains_key(item_key):
                continue

            item_detail = self._get_detail(d, item)
            self._log(f'流水明细: {item_detail}')
            if item_detail is not None:
                if BotHelper.is_last_trans(item_detail, self._last_trans):
                    self._log(f'查询到最后一条流水，终止查询，流水 ({item_detail.time}, {item_detail.amount})')
                    return False, False
                contains_detail = self._distinct_list.contains_key_val(item_key, item_detail)
                if contains_detail:
                    self._log(f'流水明细数据已存在数据，忽略: {item_detail.name}')
                else:
                    self._distinct_list.append(item_key, item_detail)

                if self._distinct_list.count() >= self._max_query_count:
                    self._log(f'符合查询流水条数限制，终止查询，条数: {self._distinct_list.count()}')
                    return False, False
                d.sleep(0.5)

        if d.xpath('//*[@text="暂无结果"]', _source).exists:
            self._log('[查询流水] 暂无结果')
            return False, False

        x_load = d.xpath('//*[@resource-id="loadEnd"]', _source)
        if x_load.exists and StrHelper.contains('暂无更多', x_load.get_text()):
            self._log('[查询流水] 没有更多数据')
            return False, False

        had_next = len(item_list) > 0
        return had_next, had_next

    @staticmethod
    def _get_item_key(elements: List[u2.xpath.XMLElement]):
        if not elements:
            return ''
        return ''.join([(_s.text.replace('可退款', '') + '_') for _s in elements])

    def _get_detail(self, d: u2.Device, item_parent: u2.xpath.XMLElement) -> Optional[Transaction]:
        item_parent.click()
        try:
            _r = self._exec_retry('等待交易明细详情', 60, lambda **_kwargs: self._wait_trans_detail(d))
            if not _r:
                raise BotParseError('未获取到交易明细详情')
            return self._parse_detail(d)
        finally:
            DeviceHelper.press_back(d)

    def _parse_detail(self, d: u2.Device) -> Optional[Transaction]:

        _source = self._dump_hierarchy(d)
        item_nodes = d.xpath('//*[@resource-id="detail"]/android.widget.ListView/*', _source).all()
        nodes_len = len(item_nodes)
        if nodes_len < 3:
            self._log('流水详情内容数量过小，忽略')
            return None

        amount_texts = XPathHelper.get_all_texts(d, item_nodes[0].get_xpath(), _source)
        amount = BotHelper.amount_fen(HRBHelper.convert_amount(amount_texts[0][0]))
        direction = 1 if amount > 0 else 0
        trans = Transaction(amount=abs(amount), direction=direction, extension={})

        for item in item_nodes:
            item_texts = XPathHelper.get_all_texts(d, item.get_xpath(), _source)
            if len(item_texts) < 2:
                continue

            _key = item_texts[0][0]
            _key_val = item_texts[1][0]
            if StrHelper.any_contains(['交易时间', '交易日期'], _key):
                trans.time = DateTimeHelper.to_datetime(_key_val)
            elif StrHelper.contains('余额', _key):
                trans.balance = BotHelper.amount_fen(HRBHelper.convert_amount(_key_val))
            elif StrHelper.contains('交易渠道', _key):
                trans.extension['交易渠道'] = _key_val
            elif StrHelper.contains('交易摘要', _key):
                trans.extension['交易摘要'] = _key_val
            elif StrHelper.any_contains(['对方账号名称'], _key):
                trans.name = _key_val
            elif StrHelper.any_contains(['对方账号'], _key):
                trans.customerAccount = HRBHelper.get_card_no(_key_val)
            elif StrHelper.any_contains(['备注'], _key):
                trans.postscript = _key_val
            elif StrHelper.any_contains(['对方银行名称'], _key):
                trans.extension['对方行名'] = _key_val
            elif StrHelper.contains('交易机构', _key) or StrHelper.contains('交易金额', _key_val):
                pass
            else:
                self._log(f'[流水详情] 未知项 {_key} -> {_key_val}')

        return trans

    def _wait_trans_detail(self, d: u2.Device):
        return HRBTransactionDetailActivityExecutor.is_current(d, self._dump_hierarchy(d))


class HRBTransferActivityExecutor(HRBActivityExecutorBase):
    _transferee: Transferee
    _sms_code_func: Callable
    _re_payer_card = re.compile(r'([\d\\*]+)')
    _re_payer_amount = re.compile(r'可用余额[：:￥]*([\d\\.,]+)')

    def check(self, ctx: ActivityCheckContext):
        return HRBHelper.is_eq_title(ctx.d, ctx.source, '智能转账') \
               and ctx.d.xpath('//*[@resource-id="PAY_AMT" or @resource-id="next"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入转账页面')
        self._transferee, self._sms_code_func = BotActionParameter.get_transfer(**kwargs)
        d = ctx.d
        self._wait_loading(d)

        name_xpath = '//*[@resource-id="PAYEE_NAME"]'
        card_xpath = '//*[@resource-id="PAYEE_NO"]'
        bank_xpath = '//*[@resource-id="PAYEE_BANKNAME"]'
        postscript_xpath = '//*[@resource-id="REMARK"]'

        self._log(f'输入收款人姓名')
        DeviceHelper.input_correct(d, name_xpath, self._transferee.holder,
                                   hierarchy_func=lambda **_kwargs: self._dump_hierarchy(d))
        self._log(f'输入收款人卡号')
        d.xpath(card_xpath).click()
        kb = HRBNumberKeyboard(d)
        [kb.input(_s, interval=0.1) for _s in self._transferee.account]
        kb.check(self._transferee.account)
        kb.close()

        self._log(f'等待自动选择银行')
        payee_bank = self._exec_retry('等待自动选择银行', 30, lambda: self._get_choose_bank(d, bank_xpath))
        payee_bank = payee_bank or ''
        check_bank_name = True  # 收款信息中无收款银行时，不做校验银行名称
        if self._transferee.bank_name:
            bank_name = self._transferee.bank_name
            check_bank_name = StrHelper.contains(bank_name, payee_bank) or StrHelper.contains(payee_bank, bank_name)
        if payee_bank and check_bank_name:
            self._log(f'已自动选择收款银行: {payee_bank}')
        else:
            raise BotErrorBase(f'未自动选择收款银行 {payee_bank}')

        self._log(f'输入转账金额')
        self._input_amount(ctx)
        self._wait_loading(d)

        if self._transferee.postscript:
            self._log(f'输入附言: {self._transferee.postscript}')
            DeviceHelper.set_text(d, postscript_xpath, self._transferee.postscript, swipe_up=0.5, close_kb=True)

        self._log(f'点击转账')
        d.xpath(f'//*[@resource-id="next"]').click()
        self._wait_loading(d)

        self._log(f'检查转账认证方式和获取短信验证码')
        sms_code_node: u2.xpath.XMLElement
        sms_code_node = self._exec_retry('获取输入短信验证码节点', 30, lambda: self._get_sms_code_node(d))
        if sms_code_node is None:
            self._save_screenshot_transfer(d, '转账失败_未找到 [输入短信验证码]')
            self._tooltip_back(d)
            raise BotErrorBase('未识别到输入短信验证码操作，疑似转账过程提示错误')

        self._log(f'等待短信验证码')
        sms_code = BotHelper.get_sms_code(sms_code_func=self._sms_code_func)
        d.sleep(6)
        self._log(f'输入短信验证码')
        DeviceHelper.set_text(d, sms_code_node, sms_code, single_input=True)
        self._wait_loading(d)
        d.sleep(2)

        self._log(f'输入交易密码')
        self._input_pay_pwd(d, ctx.account.payment_pwd)

        self._log(f'点击确认转账')
        d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/btn_sure"]').click()

        try:
            self._log(f'检查转账结果')
            self._exec_retry('检查转账结果', 60, lambda: self._transfer_result_check(d))
        except BotTransferFailedError as err:
            self._log(f'检查转账结果失败: {err.msg}')
            return False, f'转账失败，{err.msg}'
        except Exception as ex:
            self._log(f'检查转账结果未知异常: {repr(ex)}')
            self._tooltip_back(d)
            if settings.debug:
                self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功_待确认')
            return True, '转账成功，需确认'
        return True, '转账成功'

    def _input_amount(self, ctx: ActivityExecuteContext):
        d = ctx.d
        payer_card_xpath = '//*[@resource-id="payAccount"]'
        usable_xpath = '//*[contains(@text,"可用余额")]'
        amount_xpath = '//*[@resource-id="PAY_AMT"]'

        payer_text = d.xpath(payer_card_xpath).get_text()
        payer_card_match = self._re_payer_card.search(payer_text)
        if not payer_card_match:
            raise BotParseError('未解析到付款卡号')
        payer_card_no = HRBHelper.get_card_no(payer_card_match.group(1))
        if not BotHelper.is_match_card_num(payer_card_no, ctx.account.account):
            msg = f'未匹配付款卡号 {payer_card_no}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.Data, msg, is_stop=True)

        payer_amt_text = d.xpath(usable_xpath).get_text()
        payer_amt_match = self._re_payer_amount.search(payer_amt_text)
        if not payer_amt_match:
            raise BotParseError('未解析到可用余额')
        usable_amt = HRBHelper.convert_amount(payer_amt_match.group(1))
        trans_amount = self._transferee.amount_yuan()
        if usable_amt < trans_amount:
            msg = f'可用余额 {usable_amt} 小于转账余额 {trans_amount}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.BankWarning, msg)

        self._log(f'输入转账金额')
        while True:
            d.xpath(amount_xpath).click()
            d.sleep(0.5)
            kb = HRBNumberKeyboard(d)
            [kb.input(_s, interval=0.2, has_point=True) for _s in self._transferee.amount_yuan_str()]
            kb.close()
            self._wait_loading(d)
            x_payee_amt = d.xpath(amount_xpath).get_text()
            payee_amt = HRBHelper.convert_amount(x_payee_amt)
            if payee_amt == trans_amount:
                self._log(f'转账金额输入正确: {payee_amt}')
                break
            else:
                self._log(f'转账金额输入不正确: {payee_amt}，重新输入')

    def _get_choose_bank(self, d: u2.Device, item_xpath: str):
        _source = self._dump_hierarchy(d)
        x_item = d.xpath(item_xpath, _source)
        bank_text = x_item.get_text() if x_item.exists else None
        if bank_text and not StrHelper.contains('请选择', bank_text):
            return bank_text
        return False

    def _get_sms_code_node(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        get_sms_node = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/verificationcodeview"]'
                               '//android.widget.EditText[1]', _source)
        return get_sms_node.get() if get_sms_node.exists else None

    def _get_pay_pwd_node(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        kb_node = d.xpath('//*[@text="完成"]/../..', _source)
        return kb_node.get() if kb_node.exists else None

    def _input_pay_pwd(self, d: u2.Device, pwd: str):
        if not pwd:
            raise BotCategoryError(ErrorCategory.Data, '交易密码 不能为空')

        pay_pwd_node: u2.xpath.XMLElement
        pay_pwd_node = self._exec_retry('获取交易密码键盘', 20, lambda: self._get_pay_pwd_node(d))
        if not pay_pwd_node:
            raise BotParseError(f'未识别到交易密码键盘信息')
        self._log('开始输入 交易密码')
        pwd_kb = HRBTransferPwdKeyboard(d, pay_pwd_node.get_xpath())
        [pwd_kb.input(_char, 0.2) for _char in pwd]
        self._log('结束输入 交易密码')

    def _transfer_result_check(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        if HRBTransferResultActivityExecutor.is_current(d, _source):
            try:
                if HRBTransferResultActivityExecutor.is_trans_failed(d, _source):
                    _, error_detail = HRBTransferResultActivityExecutor.get_error_detail(d, _source)
                    raise BotTransferFailedError(error_detail)
                if HRBTransferResultActivityExecutor.is_trans_processing(d, _source):
                    return True
                if HRBTransferResultActivityExecutor.is_trans_success(d, _source):
                    HRBReceiptDetailActivityExecutor.last_receipt = self._get_receipt(d)
                    return True
            finally:
                if settings.debug:
                    self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功')
                HRBTransferResultActivityExecutor.go_back_core(d, _source)
        return False

    def _get_receipt(self, d: u2.Device):
        receipt = Receipt(time=DateTimeHelper.now_str(), name=self._transferee.holder
                          , customer_account=self._transferee.account
                          , amount=self._transferee.amount, postscript=self._transferee.postscript)
        receipt.need_image_format()
        receipt.content = DeviceHelper.screenshot_base64(d)
        return receipt


class HRBTransactionDetailActivityExecutor(HRBActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return HRBHelper.is_eq_title(d, source, '交易详情') \
               and d.xpath('//*[@resource-id="detail"]/*', source).exists


class HRBTransferVerifyActivityExecutor(HRBActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return self.is_sms_code(ctx.d, ctx.source) or self.is_pay_pwd(ctx.d, ctx.source)

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        x_close = ctx.d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/img_close"]', ctx.source)
        if x_close.exists:
            x_close.click()
        else:
            self.go_back_core(ctx.d, ctx.source)

    @staticmethod
    def _is_current(d: u2.Device, source=None, title: str = None):
        x_title = d.xpath('//*[@resource-id="com.yitong.hrb.people.android:id/tv_title"]', source)
        return x_title.exists and StrHelper.contains(title, x_title.get_text())

    @staticmethod
    def is_sms_code(d: u2.Device, source=None):
        return HRBTransferVerifyActivityExecutor._is_current(d, source, '输入短信验证码')

    @staticmethod
    def is_pay_pwd(d: u2.Device, source=None):
        return HRBTransferVerifyActivityExecutor._is_current(d, source, '输入交易密码')

    @staticmethod
    def go_back_core(d: u2.Device, source=None):
        x_btn_back = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/btnAuthTopTitleBack"]', source)
        if x_btn_back.exists:
            x_btn_back.click()
        else:
            DeviceHelper.press_back(d)


class HRBTransferResultLoadActivityExecutor(HRBActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return (HRBHelper.is_eq_title(ctx.d, ctx.source, '智能转账')
                and ctx.d.xpath('//*[@resource-id="count-second"]', ctx.source).exists)


class HRBTransferResultActivityExecutor(HRBActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self.go_back_core(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return (HRBHelper.any_title(d, source, ['转账失败', '转账成功', '智能转账'])
                and (HRBTransferResultActivityExecutor.is_trans_success(d, source)
                     or HRBTransferResultActivityExecutor.is_trans_failed(d, source)
                     or HRBTransferResultActivityExecutor.is_trans_processing(d, source)))

    @staticmethod
    def is_trans_success(d: u2.Device, source=None):
        result_msg, detail_msg = HRBTransferResultActivityExecutor.get_error_detail(d, source)
        return (StrHelper.any_contains(['转账成功'], result_msg)
                or d.xpath('//*[contains(@text,"转账成功")]', source).exists)

    @staticmethod
    def is_trans_processing(d: u2.Device, source=None):
        result_msg, detail_msg = HRBTransferResultActivityExecutor.get_error_detail(d, source)
        return (StrHelper.any_contains(['等待处理'], result_msg)
                or d.xpath('//*[contains(@text,"查询结果出现异常")]', source).exists)

    @staticmethod
    def is_trans_failed(d: u2.Device, source=None):
        result_msg, detail_msg = HRBTransferResultActivityExecutor.get_error_detail(d, source)
        if StrHelper.any_contains(['短信口令错误', '密码错误'], detail_msg):
            raise BotTransferFailedError(detail_msg, is_stop=True)
        return d.xpath('//*[contains(@text,"转账失败")]', source).exists

    @staticmethod
    def get_error_detail(d: u2.Device, source=None):
        x_result_msg = d.xpath('//*[@resource-id="resultMsg"]', source)
        x_detail = d.xpath('//*[@resource-id="errorMsg"]', source)
        result_msg = x_result_msg.get_text() if x_result_msg.exists else ''
        error_detail = x_detail.get_text() if x_detail.exists else ''
        return result_msg, error_detail

    @staticmethod
    def go_back_core(d: u2.Device, source=None):
        x_done = d.xpath('//*[@resource-id="finish"]', source)
        if x_done.exists:
            x_done.click()
        else:
            HRBHelper.go_back(d, source)


class HRBReceiptDetailActivityExecutor:
    last_receipt: Receipt = None
