import time
import re
from datetime import datetime
from typing import Callable, Optional

import uiautomator2 as u2

from server import settings
from server.models import Transaction, Transferee, Receipt

from server.common_helpers import StrHelper, DateTimeHelper
from server.bots.act_scheduler import *
from server.bots.act_scheduler.u2_helpers import DeviceHelper
from server.bots.act_scheduler.bot_helpers import BotHelper
from server.bots.common.common_models import DistinctList

from server.bots.bank_util.BCM.bcm_keyboard import *
from server.bots.bank_util.BCM.bcm_helper import *
from server.bots.bank_util.BCM.bcm_check import *

"""
开发 APP 信息
- 版本 6.0.2
"""

_package = 'com.bankcomm.Bankcomm'
_login_kb_xpath = f'//*[@resource-id="com.bankcomm.Bankcomm:id/login_keyboard_letter_layout"]'


class BCMActivityExecutorBase(BotActivityExecutor):
    def _dump_hierarchy(self, d, check_error=True):
        """
        加载结构，使用代理类检查页面是否有错误
        :param check_error: 是否检查错误
        """
        retry_limit = 5
        while True:
            source = super()._dump_hierarchy(d, check_error=check_error)
            if check_error:
                had_error, error_msg = BCMErrorChecker.check(d, source)
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

    @staticmethod
    def _is_loading(d: u2.Device, _source: str = None):
        """
        是否为请求后台加载中
        """
        loading_xpath = '//*[@resource-id="mySprite"]'
        return d.xpath(loading_xpath, _source).exists

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self._tooltip_back(ctx.d, ctx.source)

    def _tooltip_back(self, d: u2.Device, _source: str = None, wait_second: float = 0):
        """
        优先点击顶部返回，避免键盘仍处于打开状态等
        """
        is_toolbar_back = BCMHelper.go_back(d, _source)
        if is_toolbar_back:
            self._log(f'点击页面返回')
        else:
            self._log(f'点击手机返回')
        # 连续点击返回，只会生效一次
        if wait_second:
            d.sleep(wait_second)


class BCMMainActivityExecutor(BCMActivityExecutorBase):
    _main_activity = ['com.bankcomm.module.biz.home.MainActivity']

    def check(self, ctx: ActivityCheckContext):
        return BCMHelper.is_title(ctx.d, ctx.source, '首页') \
               and StrHelper.any_contains(self._main_activity, ctx.current_activity)

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        account_btn_xpath = '//*[contains(@resource-id,"com.bankcomm.Bankcomm:id/text")][@text="我的账户"]'
        if target_type == BotActivityType.Login or target_type == BotActivityType.QueryAccount:
            ctx.d.xpath(account_btn_xpath, ctx.source).click_exists(1)


class BCMLoginActivityExecutor(BCMActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return self._is_current(ctx.d, ctx.source)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入登录页')
        account = ctx.account
        d = ctx.d

        x_text = d.xpath('//android.widget.EditText')
        x_text.wait()
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))

        text_nodes = x_text.all()
        if len(text_nodes) < 2:
            raise BotParseError('未获取到登录表单')
        ele_mobile = text_nodes[0]
        ele_pwd = text_nodes[1]

        self._log('输入手机号')
        DeviceHelper.set_text(d, ele_mobile, account.login_name)

        # 输入密码最多试2次
        pwd_retry_limit, done_login = 2, False
        while not done_login and pwd_retry_limit > 0:
            pwd_retry_limit -= 1
            # 点击密码框，最多尝试10次，点击1次会清空密码显示键盘，点击2次会关闭键盘
            pwd_kb_node = None
            for _ in range(10):
                self._log('点击登录密码框')
                ele_pwd.click()
                d.sleep(0.5)
                pwd_kb_node = self._find_pwd_kb_node(d)
                if pwd_kb_node:
                    break
                self._log('登录密码键盘未找到，重试')
            if not pwd_kb_node:
                raise BotParseError('未获取到登录密码键盘')

            self._log('开始输入登录密码')
            pwd_keyboard = BCMLoginPwdKeyboard(d, pwd_kb_node.get_xpath())
            [pwd_keyboard.input(_char, 0.2) for _char in account.login_pwd]

            ele_confirm, enabled = pwd_keyboard.get_confirm_node()
            if not enabled or enabled == 'false':
                # 密码长度输入不够时，不可点击
                self._log('登录密码键盘登录不可点击，待重试')
                continue
            else:
                self._log('点击登录')
                # 因表单中登录无法识别，使用密码键盘登录
                ele_confirm.click()
                done_login = True
        if not done_login:
            raise BotParseError('点击登录失败')

        # 加快检查速度，因账号密码错误时，提示后会立即关闭
        if self._exec_retry('登录结果检查', retry_limit=100, interval_second=0.5,
                            func=lambda: self._login_result_check(ctx.d)):
            self._log('登录成功')
        else:
            # 避免多次重登锁卡，未登录成功，则强制停止
            raise BotParseError('未检查到登录结果', is_stop=True)

    @staticmethod
    def _is_current(d: u2.Device, source: str):
        return BCMHelper.is_webview_done(d, source) and \
               d.xpath(f'//*[contains(@text,"手机银行登录")]', source).exists

    @staticmethod
    def _find_pwd_kb_node(d: u2.Device, _source: str = None) -> Optional[u2.xpath.XMLElement]:
        x_kb = d.xpath(_login_kb_xpath)
        x_kb.wait(1)
        return x_kb.get() if x_kb.exists else None

    def _login_result_check(self, d: u2.Device):
        # 检查错误
        _source = self._dump_hierarchy(d)
        if d.xpath(_login_kb_xpath, _source).exists:
            # 登录点击后键盘未消失时，但无法识别为登录页
            return False
            # 跳转页面，表示成功
        return not self._is_current(d, _source)


class BCMAccountActivityExecutor(BCMActivityExecutorBase):
    # 尾号1 5 0 8
    _re_card_no_tail = re.compile(r'^尾号(.*)')
    # 活期 29.50
    _re_balance = re.compile(r'(\d+(\.?\d+)?)')

    def check(self, ctx: ActivityCheckContext):
        return BCMHelper.is_eq_title(ctx.d, ctx.source, '我的账户') and BCMHelper.is_webview_done(ctx.d, ctx.source)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入我的账户')
        d = ctx.d
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))

        _, card_xpath = self._retry_logic(30, lambda **_kwargs: self._get_card_xpath(ctx, **_kwargs))
        x_balance = DeviceHelper.get_child_selector(d, card_xpath, '/android.widget.Button[contains(@text,"活期")]')
        balance_text = self._re_balance.search(x_balance.get_text()).group(1)
        balance = BCMHelper.convert_amount(balance_text)
        self._log(f'查询余额: {balance}')
        return {'balance': BotHelper.amount_fen(balance)}

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        if target_type not in [BotActivityType.QueryTrans, BotActivityType.Transfer, BotActivityType.TransferIndex]:
            return

        _, card_xpath = self._retry_logic(30, lambda **_kwargs: self._get_card_xpath(ctx, **_kwargs))
        _source = self._dump_hierarchy(ctx.d)

        if target_type == BotActivityType.QueryTrans:
            x_trans_detail = DeviceHelper.get_child_selector(ctx.d, card_xpath, '//android.widget.Button[@text="交易明细"]',
                                                             _source)
            self._log(f'点击交易明细按钮')
            x_trans_detail.click_exists(1)
        elif target_type == BotActivityType.Transfer or target_type == BotActivityType.TransferIndex:
            x_transfer = DeviceHelper.get_child_selector(ctx.d, card_xpath, '//android.widget.Button[@text="转账"]',
                                                         _source)
            self._log(f'点击转账按钮')
            x_transfer.click_exists(1)

    def _get_card_xpath(self, ctx: ActivityExecuteContext, **_) -> [str, str]:
        """获取匹配账户详情"""
        d = ctx.d
        d.sleep(1)  # 页面加载完成

        # 通过银行卡内容项逆推上级
        x_card_list = d.xpath('//android.webkit.WebView//*[contains(@text,"尾号")]/../../..')
        if not x_card_list.wait(60):
            raise BotParseError('未获取到银行卡列表')

        # 通过银行卡内容项逆推上级
        acct_list = x_card_list.all()
        if len(acct_list) > 1:
            self._log(f'账户列表数量: {len(acct_list)}')
        _source = self._dump_hierarchy(d)
        for item in acct_list:
            item_xpath = item.get_xpath()
            item_child = d.xpath(item_xpath, _source).child('/*').all(_source)
            item_child_count = len(item_child)
            if item_child_count < 1:
                continue
            # 匹配卡号
            card_node = item_child[0]
            card_xpath = card_node.get_xpath()
            card_no_child = d.xpath(card_xpath, _source).child('//*[contains(@text,"尾号")]').all(_source)
            if len(card_no_child) < 1:
                self._log('未找到尾号节点')
                continue
            card_no_node = card_no_child[0]
            card_no_text = self._re_card_no_tail.search(card_no_node.text).group(1)
            card_no_tail = BCMHelper.get_card_no(card_no_text)
            if not card_no_tail:
                raise BotLogicRetryError('加载卡号为空，需重试')
            # 加*表示，只匹配尾号
            if not BotHelper.is_match_card_num_tail(card_no_tail, ctx.account.account):
                self._log(f'过滤不匹配卡号:{card_no_tail}')
                continue
            # 银行卡未展开时
            if item_child_count == 1:
                card_no_node.click()
                d.sleep(0.3)
            self._log(f'匹配到银行卡尾号: {card_no_tail}')
            return item_xpath
        # 不强制停止，可做重试后是否仍然报错
        raise BotCategoryError(ErrorCategory.Data, BotErrorMsg.NotMatchedCardNo)


class BCMTransactionActivityExecutor(BCMActivityExecutorBase):
    # 去重列表
    _distinct_list = DistinctList()
    # 查询流水终止条件
    _last_trans: Transaction
    _max_query_count: int
    _start_time: datetime
    # 最后一项流水项高度，避免滑过导致流水丢失
    _last_item_height: int = 0

    def check(self, ctx: ActivityCheckContext):
        return BCMHelper.is_eq_title(ctx.d, ctx.source, '交易明细') and BCMHelper.is_webview_done(ctx.d, ctx.source)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        """
        流水须知：
        1. 默认展示1个月内交易，可以一直滑动分页到近3月数据
        2. 列表显示格式，年月标题、流水项 或 无数据
        3. 已处理情况：分页流水、无记录
        3.1 分页最后一屏(仅1屏时)后5条查不到，需要展开才能读取到子节点，暂不处理
        """
        self._log('进入流水页面')
        self._reset_data()  # 每次重置当前流水列表
        self._last_trans, self._max_query_count, self._start_time, _ = BotActionParameter.get_query_trans(**kwargs)

        d = ctx.d
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))
        # 首次渲染慢
        d.sleep(1)

        had_next = True
        while had_next:
            had_next = self._curr_list(ctx)
            self._log(f'当前流水条数: {self._distinct_list.count()}')
            if had_next:
                # 每次滑动3个流水项，尽可能多抓流水，避免列表内容节点找不到
                move = self._last_item_height * 3
                self._log(f'分页滑动高度: {move}')
                # 滑动需计算真实高度
                DeviceHelper.swipe_up_until(ctx.d, ctx.win_size_height, move)

        trans_list = self._distinct_list.data_list()
        return BotHelper.sort_trans_list(trans_list)

    def _reset_data(self):
        self._distinct_list.reset()
        self._last_item_height = 0

    def _curr_list(self, ctx: ActivityExecuteContext) -> bool:
        d = ctx.d

        list_xpath = '//android.webkit.WebView/android.view.View[3]/*'
        x_list = ctx.d.xpath(list_xpath)
        x_list.wait(30)
        if not x_list.exists:
            raise BotParseError('未获取到流水列表')

        _, _list_y, _, _ = x_list.get().rect
        _source = self._dump_hierarchy(d)

        """
        流水列表节点集合
        1. 仅包含 流水项 android.widget.Button
        2. 不包含 暂无数据、加载完成
        """
        had_new_trans = False
        item_list = x_list.child('//android.widget.ListView/*').all(_source)
        self._log(f'流水列表内容长度: {len(item_list)}')
        for _item in item_list:
            _, _item_y, _, _item_height = _item.rect
            self._last_item_height = max(self._last_item_height, _item_height)
            # 高度太小，滑动后处理
            if _item_height < 20:
                # self._log(f'流水项高度太小，忽略')
                continue
            # 滑动后，元素会被顶上去，可以获取到，但不可见
            if _item_y < _list_y:
                # self._log(f'流水项不在列表显示范围内，忽略')
                continue
            # 列表项过滤
            # 跨行汇款张三110.00网上银行余额10.00时间2022年01月03日14时52分30秒
            item_key = _item.text
            if self._distinct_list.contains_key(item_key):
                self._log(f'流水明细数据已存在数据，忽略: {item_key}')
                continue
            item_detail = self._get_detail(d, _item)
            self._log(f'流水明细: {item_detail}')
            if item_detail is not None:
                if BotHelper.is_last_trans(item_detail, self._last_trans):
                    self._log(f'查询到最后一条流水，终止查询，流水 ({item_detail.time}, {item_detail.amount})')
                    return False
                # 详情过滤
                if self._distinct_list.contains_key_val(item_key, item_detail):
                    self._log(f'流水明细数据已存在数据，忽略: {item_detail.name}')
                else:
                    had_new_trans = True
                    self._distinct_list.append(item_key, item_detail)

                if self._distinct_list.count() >= self._max_query_count:
                    self._log(f'符合查询流水条数限制，终止查询，条数: {self._distinct_list.count()}')
                    return False
                # 避免点击过快
                d.sleep(0.5)

        # 无新数据时，提示无明细记录
        if not had_new_trans and d.xpath(list_xpath, _source).child('//*[contains(@text,"无交易明细记录")]').exists:
            self._log(f'检测到无交易明细记录，终止查询')
            return False
        # 当前列表有流水数据
        return len(item_list) > 0

    def _get_detail(self, d: u2.Device, item_parent: u2.xpath.XMLElement) -> Optional[Transaction]:
        item_parent.click()
        try:
            exec_result = self._exec_retry('等待交易明细详情', 60, lambda **_kwargs: self._wait_trans_detail(d))
            if not exec_result:
                raise BotParseError('未获取到交易明细详情')
            return self._parse_detail(d)
        finally:
            self._tooltip_back(d)

    def _parse_detail(self, d: u2.Device) -> Optional[Transaction]:
        """解析详情，兼容 收入、支出、批处理"""

        source = self._dump_hierarchy(d)
        item_nodes = d.xpath('//android.webkit.WebView/android.view.View', source).all()
        if len(item_nodes) < 8:
            self._log('流水详情内容项数量不符，忽略')
            return None

        trans = Transaction(extension={})
        title = ''
        # 仅读取前8项值，避免底部
        for _item in item_nodes:
            """
            跨行汇款 +2,060.00 余额:2,060.00
            交易卡号 六二二二六二四颗星一五零八
            交易时间 二零二二年一月十日十八时五十五分三十七秒
            交易地点 网上银行
            对方户名 张三
            对方账户 六二一七零零七一零零零七一零六五一三零
            对方开户行 中国建设银行股份有限公司总行
            摘要 手机转账一六四三三五七二三六一七零
            """
            item_text = _item.text or ''
            # 余额和金额特殊处理
            if StrHelper.contains('余额', item_text):
                # 跨行汇款 +2,060.00 余额:2,060.00
                text_list = item_text.split(' ', 2)
                # 跨行代发、借记卡工本费、跨行汇款
                title = text_list[0]
                amount = BCMHelper.convert_amount(text_list[1])
                balance = BCMHelper.convert_amount(text_list[2].replace('余额', '').replace(':', '').replace('：', ''))
                trans.amount = abs(BotHelper.amount_fen(amount))
                trans.direction = 1 if amount > 0 else 0
                trans.balance = BotHelper.amount_fen(balance)
                continue
            # 默认项处理
            text_list = item_text.split(' ', 1)
            item_key = text_list[0] if len(text_list) >= 1 else ''
            item_val = text_list[1] if len(text_list) >= 2 else ''
            if not item_val:
                # self._log(f'忽略，流水项找不到值: {item_key}')
                continue
            if StrHelper.contains('交易时间', item_key):
                _trans_time = BCMHelper.cn_to_datetime(item_val)
                trans.time = BotHelper.format_time(_trans_time)
            elif StrHelper.contains('对方户名', item_key):
                trans.name = item_val
            elif StrHelper.any_contains(['对方账户', '对方账号'], item_key):
                trans.customerAccount = BCMHelper.cn_to_number(item_val)
            elif StrHelper.contains('摘要', item_key):
                trans.postscript = BCMHelper.cn_to_number(item_val)
            elif StrHelper.contains('交易地点', item_key):
                trans.extension['交易地点'] = item_val
            elif StrHelper.contains('对方开户行', item_key):
                trans.extension['对方开户行'] = item_val

        # 银行批处理时，信息不全，需要标题填充
        if not trans.postscript and not trans.name:
            trans.postscript = title
        return trans

    def _wait_trans_detail(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        return BCMTransactionDetailActivityExecutor.is_current(d, _source)


class BCMTransferIndexActivityExecutor(BCMActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return BCMHelper.is_eq_title(ctx.d, ctx.source, '转账') and BCMHelper.is_webview_done(ctx.d, ctx.source) \
               and ctx.d.xpath('//android.widget.Button[@text="账号转账"]', ctx.source).exists

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        ctx.d.sleep(0.5)
        if target_type == BotActivityType.Transfer:
            ctx.d.xpath(f'//android.widget.Button[@text="账号转账"]').click_exists(1)
        if target_type == BotActivityType.QueryReceipt:
            ctx.d.xpath(f'//android.widget.Button[@text="转账记录"]').click_exists(1)


class BCMTransferActivityExecutor(BCMActivityExecutorBase):
    _transferee: Transferee
    _sms_code_func: Callable
    _re_payer_card_amount = re.compile(r'尾号为?([\d\b\s]*)可用余额([\d\b\s.+,]*)元')

    def check(self, ctx: ActivityCheckContext):
        return BCMHelper.is_eq_title(ctx.d, ctx.source, '银行账号转账') and BCMHelper.is_webview_done(ctx.d, ctx.source) \
               and ctx.d.xpath('//*[contains(@text,"可用余额") or contains(@text,"转账金额")]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入转账页面')
        self._transferee, self._sms_code_func = BotActionParameter.get_transfer(**kwargs)
        d = ctx.d
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))

        # 交通银行 尾号为 1 5 0 8 可用余额29.50元  选择入口
        payer_card_xpath = '//*[contains(@text,"付款卡")]/following-sibling::*[1]/*[1]/*[1]'
        name_xpath = '//*[contains(@text,"户名")]/following-sibling::*[1]//android.widget.EditText'
        card_xpath = '//*[contains(@text,"账号")]/following-sibling::*[1]//android.widget.EditText'
        # 卡号输入前和输入后的节点变化
        # //*[contains(@text,"银行")]/following-sibling::*[1]//android.widget.EditText
        # //*[contains(@text,"银行")]/following-sibling::*[1]/android.view.View[1]/android.view.View[1]
        bank_xpath = '//*[contains(@text,"银行")]/following-sibling::*[1]/*[1]/*[1]'

        self._log(f'输入收款人姓名')
        DeviceHelper.input_correct(d, name_xpath, self._transferee.holder,
                                   hierarchy_func=lambda **_kwargs: self._dump_hierarchy(d))
        self._log(f'输入收款人卡号')
        DeviceHelper.input_correct(d, card_xpath, self._transferee.account,
                                   hierarchy_func=lambda **_kwargs: self._dump_hierarchy(d))
        # 检查收款银行，自动带出、手动选择
        self._log(f'等待自动选择银行')
        payee_bank = self._exec_retry('等待自动选择银行', 30, lambda: self._get_choose_bank(d, bank_xpath))
        payee_bank = payee_bank or ''
        # 如果收款银行非必须字段，需要判断是否有自动选择即可
        check_bank_name = True  # 收款信息中无收款银行时，不做校验银行名称
        if self._transferee.bank_name:
            bank_name = self._transferee.bank_name
            check_bank_name = StrHelper.contains(bank_name, payee_bank) or StrHelper.contains(payee_bank, bank_name)
        if payee_bank and check_bank_name:
            self._log(f'已自动选择收款银行: {payee_bank}')
        else:
            raise BotErrorBase(f'未自动选择收款银行 {payee_bank}')

        # 检查付款账号、可用余额
        payer_text = d.xpath(payer_card_xpath).get_text()
        payer_data = self._re_payer_card_amount.findall(payer_text)
        if not payer_data and len(payer_data[0]) < 2:
            raise BotParseError('未获取到付款卡号信息')
        # 匹配的所有信息
        payer_data = payer_data[0]
        card_no_tail = BCMHelper.get_card_no(payer_data[0])
        if not BotHelper.is_match_card_num_tail(card_no_tail, ctx.account.account):
            msg = f'未匹配付款卡号 {card_no_tail}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.Data, msg, is_stop=True)

        usable_amt = BCMHelper.convert_amount(payer_data[1])
        trans_amount = self._transferee.amount_yuan()
        if usable_amt < trans_amount:
            msg = f'可用余额 {usable_amt} 小于转账余额 {trans_amount}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.BankWarning, msg)

        # 向上滑动，显示提交转账按钮
        d.swipe_ext(direction='up', scale=0.7)
        d.sleep(1)

        amount_input_xpath = '//*[contains(@text,"转账金额")]/following-sibling::*//android.widget.EditText'
        input_texts = d.xpath(amount_input_xpath).all()
        amount_xpath = input_texts[0].get_xpath()
        postscript_xpath = input_texts[1].get_xpath()

        # 输入转账金额
        self._log(f'输入转账金额')
        while True:
            # 点击转账金额重试处理
            d.xpath(amount_xpath).set_text(self._transferee.amount_yuan_str())
            # 获取输入金额可能为空，等待彻底输入完成
            d.sleep(0.5)
            x_payee_amt = d.xpath(amount_xpath, self._dump_hierarchy(d)).get_text()
            payee_amt = BCMHelper.convert_amount(x_payee_amt)
            if payee_amt == trans_amount:
                self._log(f'转账金额输入正确: {payee_amt}')
                break
            else:
                self._log(f'转账金额输入不正确: {payee_amt}')

        if self._transferee.postscript:
            self._log(f'输入附言: {self._transferee.postscript}')
            d.xpath(postscript_xpath).set_text(self._transferee.postscript)

        self._log(f'点击转账')
        d.xpath(f'//android.widget.Button[contains(@text,"下一步")]').click()

        # 此处可能有提示【卡号无误确认】，但无法识别到节点
        self._log(f'检查是否发送短信验证码')
        sms_code_node: u2.xpath.XMLElement
        sms_code_node = self._exec_retry('获取短信验证码节点', 30, lambda: self._get_sms_code_node(d))
        if sms_code_node is None:
            self._save_screenshot_transfer(d, '转账失败_未获取到短信验证码节点')
            self._tooltip_back(d)
            raise BotErrorBase('未识别到输入短信验证码操作，疑似转账过程提示错误')

        self._log(f'等待短信验证码')
        sms_code = BotHelper.get_sms_code(sms_code_func=self._sms_code_func)
        # 短信验证码，等待顶部短信通知关闭
        d.sleep(6)
        self._log(f'输入短信验证码')
        # d.xpath(sms_code_node.get_xpath()).set_text(sms_code)
        # 输入使用先点击，后输入，不做清空处理
        sms_code_node.click()
        d.send_keys(text=sms_code, clear=False)
        d.sleep(3)
        self._log(f'输入交易密码')
        self._input_pay_pwd(d, ctx.account.payment_pwd)

        try:
            self._log(f'检查转账结果')
            self._exec_retry('检查转账结果', 60, lambda: self._transfer_result_check(d))
        except BotTransferFailedError as err:
            # 识别到的转账失败异常
            self._log(f'检查转账结果失败: {err.msg}')
            return False, f'转账失败，{err.msg}'
        except Exception as ex:
            # 未识别异常，乐观处理
            self._log(f'检查转账结果未知异常: {repr(ex)}')
            # 回退，避免恶意操作
            self._tooltip_back(d)
            if settings.debug:
                self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功_待确认')
            return True, '转账成功，需确认'
        # 未检测到失败，则认为成功
        return True, '转账成功'

    def _get_choose_bank(self, d: u2.Device, item_xpath: str):
        # 检查错误
        _source = self._dump_hierarchy(d)
        x_item = d.xpath(item_xpath, _source)
        # 未选择时为空
        bank_text = x_item.get_text() if x_item.exists else None
        if bank_text and not StrHelper.contains('请选择', bank_text):
            return bank_text
        return False

    def _get_sms_code_node(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        # com.bankcomm.Bankcomm:id/verify_code_view
        # 输入文本框
        kb_node = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/edit_text_view"]', _source)
        return kb_node.get() if kb_node.exists else None

    def _get_pay_pwd_node(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        kb_node = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/digitkeypadlayout"]', _source)
        return kb_node.get() if kb_node.exists else None

    def _input_pay_pwd(self, d: u2.Device, pwd: str):
        if not pwd:
            raise BotCategoryError(ErrorCategory.Data, '交易密码 不能为空')

        pay_pwd_node: u2.xpath.XMLElement
        pay_pwd_node = self._exec_retry('获取交易密码键盘', 20, lambda: self._get_pay_pwd_node(d))
        if not pay_pwd_node:
            raise BotParseError(f'未识别到交易密码键盘信息')
        # 键盘出来后再等2秒，因渲染键盘乱序会耗费时间
        d.sleep(2)
        self._log('开始输入 交易密码')
        pwd_kb = BCMTransferPwdKeyboard(d, pay_pwd_node.get_xpath())
        [pwd_kb.input(_char, 0.3) for _char in pwd]
        self._log('结束输入 交易密码')

    def _transfer_result_check(self, d: u2.Device):
        """转账后返回上页处理"""
        # 检查错误和成功结果
        _source = self._dump_hierarchy(d)
        if BCMTransferResultActivityExecutor.is_current(d, _source):
            try:
                if BCMTransferResultActivityExecutor.is_trans_failed(d, _source):
                    error_detail = BCMTransferResultActivityExecutor.get_error_detail(d, _source)
                    raise BotTransferFailedError(error_detail)
                if BCMTransferResultActivityExecutor.is_trans_success(d, _source):
                    return True
            finally:
                if settings.debug:
                    self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功')
                # 点击完成，返回到App首页
                BCMTransferResultActivityExecutor.go_back_core(d, _source)
        # 未检查到结果，重试
        return False


class BCMReceiptIndexActivityExecutor(BCMActivityExecutorBase):
    _distinct_list = DistinctList()  # 去重列表
    _max_query_count: int
    _last_transferee: Transferee

    def check(self, ctx: ActivityCheckContext):
        return BCMHelper.is_eq_title(ctx.d, ctx.source, '转账记录') and BCMHelper.is_webview_done(ctx.d, ctx.source) \
               and ctx.d.xpath('//*[@resource-id="searchBar"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        """
        回单须知：
        1. 默认展示1个月内交易
        2. 已处理情况：首屏回单，无记录
        3. 因目前只抓取转账的那一条回单，固理解为只获取最新一条即可
        """
        self._log('进入回单页面')
        self._reset_data()  # 每次重置当前列表
        self._last_transferee, self._max_query_count = BotActionParameter.get_query_receipt(**kwargs)

        d = ctx.d
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))

        # 只读取首屏回单，因目前只抓取转账的那一条回单
        self._curr_list(ctx)

        receipt_list = self._distinct_list.data_list()
        return BotHelper.sort_receipt_list(receipt_list)

    def _reset_data(self):
        self._distinct_list.reset()

    def _curr_list(self, ctx: ActivityExecuteContext):
        d = ctx.d

        list_xpath = '//android.webkit.WebView/android.view.View[3]/*'
        x_list = ctx.d.xpath(list_xpath)
        x_list.wait(30)
        if not x_list.exists:
            raise BotParseError('未获取到回单列表')

        _, _list_y, _, _ = x_list.get().rect
        _source = self._dump_hierarchy(d)
        # 无记录
        if d.xpath('//android.webkit.WebView/android.view.View[3]//*[contains(@text,"没有转账记录")]', _source).exists:
            return False

        """
        流水列表节点集合
        1. 仅包含 流水项 android.widget.Button
        2. 不包含 暂无数据、加载完成
        """
        item_list = x_list.child('//android.widget.ListView/*').all(_source)
        # self._log(f'回单列表内容长度: {len(item_list)}')
        for _item in item_list:
            _, _item_y, _, self._last_item_height = _item.rect
            # 滑动后，元素会被顶上去，可以获取到，但不可见
            if _item_y < _list_y:
                # self._log(f'回单项不在列表显示范围内，忽略')
                continue
            item_detail = self._get_detail(d, _item)
            self._log(f'回单明细: {item_detail}')
            if item_detail is not None:
                item_key = f'{item_detail.billNo}{item_detail.name}{item_detail.time}{item_detail.amount}'
                if self._distinct_list.contains_key_val(item_key, item_detail):
                    self._log(f'回单明细数据已存在数据，忽略: {item_detail.name}')
                else:
                    self._distinct_list.append(item_key, item_detail)

                if BotHelper.is_transfer_receipt(item_detail, self._last_transferee):
                    self._log(f'查询到最后一条回单，终止查询，回单 ({item_detail.time}, {item_detail.amount})')
                    return False
                if self._distinct_list.count() >= self._max_query_count:
                    self._log(f'符合查询回单条数限制，终止查询，条数: {self._distinct_list.count()}')
                    return False
            d.sleep(0.5)  # 避免过快
        return len(item_list) > 0

    def _get_detail(self, d: u2.Device, item_parent: u2.xpath.XMLElement):
        """获取详情"""
        item_parent.click()
        try:
            return self._parse_detail(d)
        finally:
            self._tooltip_back(d, wait_second=0.5)

    def _parse_detail(self, d: u2.Device):
        """解析详情，兼容 卡号转账"""

        exec_result = self._exec_retry('等待回单明细详情', 60, lambda **_kwargs: self._wait_receipt_detail(d))
        if not exec_result:
            raise BotParseError('未获取到回单明细详情')
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))
        d.sleep(0.5)  # 避免过快

        source = self._dump_hierarchy(d)
        items = d.xpath('//android.webkit.WebView/*[1]/*[1]/*', source).all(source)
        if len(items) < 5:
            self._log(f'回单详情内容项过小，忽略')
            return None
        # 转账失败，不能查看回单
        trans_result = items[1].text
        if trans_result == '转账失败':
            self._log(f'回单详情，转账失败，忽略')
            return None
        return self._parse_receipt_image(d)

    def _parse_receipt_image(self, d: u2.Device):
        d.xpath('//android.widget.Button[@text="查看回执"]').click()

        exec_result = self._exec_retry('等待回单图片', 60, lambda **_kwargs: self._wait_receipt_img(d))
        if not exec_result:
            raise BotParseError('未获取到回单凭证图片')
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))
        d.sleep(0.5)  # 避免过快
        source = self._dump_hierarchy(d)

        try:
            # 2022年1月25日10时59分41秒
            x_time = d.xpath(f'//*[contains(@text,"交易时间")]/following-sibling::*[1]', source)
            # 2 0 0 5 0 0 0 4 2 0 2 2 0 1 2 5 0 5 0 0 0 9 1 3 7 2 3 1
            x_bill_no = d.xpath(f'//*[contains(@text,"流水号")]/following-sibling::*[1]', source)
            # 张三 中国民生银行
            x_payee_name_bank = d.xpath(f'//*[contains(@text,"收")]/following-sibling::*[1]', source)
            # 6 2 2 6 2 2 尾 号 1 2 3 7
            x_payee_card = d.xpath(f'//*[contains(@text,"收")]/following-sibling::*[2]', source)
            # # 李四 交通银行
            # x_payer_name_bank = d.xpath(f'//*[contains(@text,"付")]/following-sibling::*[1]', source)
            # # 6 2 2 6 2 2 尾 号 1 2 3 7
            # x_payer_card = d.xpath(f'//*[contains(@text,"付")]/following-sibling::*[2]', source)
            # 8.00元
            x_amount = d.xpath(f'//*[contains(@text,"转账金额")]/following-sibling::*[1]', source)
            # 转账
            x_postscript = d.xpath(f'//*[contains(@text,"附言") or contains(@text,"言:")]/following-sibling::*[1]', source)

            receipt = Receipt()
            receipt.billNo = x_bill_no.get_text().replace(' ', '')
            receipt.postscript = x_postscript.get_text()
            receipt.amount = BotHelper.amount_fen(BCMHelper.convert_amount(x_amount.get_text()))
            receipt.time = BotHelper.format_time(DateTimeHelper.to_datetime(x_time.get_text(), '%Y年%m月%d日%H时%M分%S秒'))

            payee_name_banks = x_payee_name_bank.get_text().split(' ', 1)
            receipt.name = payee_name_banks[0]
            receipt.inner = StrHelper.contains('交通', payee_name_banks[1])

            # 还原转账的对方卡号
            trans_account = self._last_transferee.account
            card_no = BCMHelper.get_card_no(x_payee_card.get_text())
            is_transferee_receipt = BotHelper.is_match_card_num(card_no, trans_account)
            receipt.customerAccount = trans_account if is_transferee_receipt else card_no

            receipt.content = DeviceHelper.screenshot_base64(d)
            receipt.need_image_format()

            if settings.debug:
                self._save_screenshot_receipt(d, receipt.time, receipt.name)
            return receipt
        finally:
            self._tooltip_back(d, source, wait_second=1)

    def _wait_receipt_detail(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        return BCMReceiptDetailActivityExecutor.is_current(d, _source)

    def _wait_receipt_img(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        return BCMReceiptDetailImgActivityExecutor.is_current(d, _source)


class BCMLoginVerifyActivityExecutor(BCMActivityExecutorBase):
    """登录安全验证公共处理，页面流转过程中关闭元素或提示异常"""

    def check(self, ctx: ActivityCheckContext):
        d, _source = ctx.d, ctx.source
        # 登录安全认证
        if BCMHelper.is_title(d, _source, '登录安全认证'):
            raise BotCategoryError(ErrorCategory.Environment, '登录后需要安全验证，请先在手机完成认证', is_stop=True)
        # 登录密码键盘打开时，返回关闭
        x_login_kb = d.xpath(_login_kb_xpath, _source)
        if x_login_kb.exists:
            self._log('关闭登录键盘')
            DeviceHelper.press_back(d)
        return False


class BCMTransactionDetailActivityExecutor(BCMActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return BCMHelper.is_eq_title(d, source, '明细详情') and BCMHelper.is_webview_done(d, source) and \
               d.xpath('//*[contains(@text,"交易卡号")]', source).exists


class BCMTransferVerifyActivityExecutor(BCMActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_sms_code(ctx.d, ctx.source) or self.is_pay_pwd(ctx.d, ctx.source)

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self.go_back_core(ctx.d, ctx.source)

    @staticmethod
    def _is_current(d: u2.Device, source=None, title: str = None):
        x_title = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/textAuthDialogTitle"]', source)
        return x_title.exists and StrHelper.contains(title, x_title.get_text())

    @staticmethod
    def is_sms_code(d: u2.Device, source=None):
        # 验证短信密码
        return BCMTransferVerifyActivityExecutor._is_current(d, source, '短信密码')

    @staticmethod
    def is_pay_pwd(d: u2.Device, source=None):
        # 验证交易密码
        return BCMTransferVerifyActivityExecutor._is_current(d, source, '交易密码')

    @staticmethod
    def go_back_core(d: u2.Device, source=None):
        # 关闭
        x_btn_back = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/btnAuthTopTitleBack"]', source)
        if x_btn_back.exists:
            x_btn_back.click()
        else:
            DeviceHelper.press_back(d)


class BCMTransferResultActivityExecutor(BCMActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self.go_back_core(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return (BCMHelper.is_eq_title(d, source, '账号转账') and BCMHelper.is_webview_done(d, source)
                and (BCMTransferResultActivityExecutor.is_trans_success(d, source)
                     or BCMTransferResultActivityExecutor.is_trans_failed(d, source)))

    @staticmethod
    def is_trans_success(d: u2.Device, source=None):
        return d.xpath('//*[contains(@text,"转账成功")]', source).exists

    @staticmethod
    def is_trans_failed(d: u2.Device, source=None):
        detail_msg = BCMTransferResultActivityExecutor.get_error_detail(d, source)
        # 交易密码错误，直接停止运行，避免锁卡
        if StrHelper.any_contains(['您密码错误', '续输入错误次数达到', '卡将被锁定', '交易密码已连续输错', '当日连续3次密码输错'], detail_msg):
            raise BotTransferFailedError(detail_msg, is_stop=True)
        return (d.xpath('//*[contains(@text,"转账失败")]', source).exists
                or StrHelper.contains('短信动态密码有误', detail_msg))

    @staticmethod
    def get_error_detail(d: u2.Device, source=None):
        x_detail = d.xpath('//android.webkit.WebView/android.view.View[2]/*[1]', source)
        # 您输入的短信动态密码有误。
        # 您密码错误。若当日连续3次密码输错，该卡将被锁定。
        # 您的交易密码已连续输错2次，若连续输入错误次数达到3次，该银行账号将被锁定。
        return x_detail.get_text() if x_detail.exists else ''

    @staticmethod
    def go_back_core(d: u2.Device, source=None):
        # 完成
        x_done = d.xpath('//*[@resource-id="com.bankcomm.Bankcomm:id/web_text_right1"]', source)
        if x_done.exists:
            x_done.click()
        else:
            BCMHelper.go_back(d, source)


class BCMReceiptDetailActivityExecutor(BCMActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return BCMHelper.is_eq_title(d, source, '转账记录详情') and BCMHelper.is_webview_done(d, source)


class BCMReceiptDetailImgActivityExecutor(BCMActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return BCMHelper.is_eq_title(d, source, '转账回执') and BCMHelper.is_webview_done(d, source)
