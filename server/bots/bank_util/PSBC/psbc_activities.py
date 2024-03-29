import time
import re
from datetime import datetime
from typing import Callable, Optional, Union, List

import uiautomator2 as u2

from server import settings
from server.models import Transaction, Transferee, Receipt

from server.common_helpers import StrHelper, DateTimeHelper
from server.bots.act_scheduler import *
from server.bots.act_scheduler.u2_helpers import DeviceHelper
from server.bots.act_scheduler.bot_helpers import BotHelper
from server.bots.common.common_models import DistinctList

from server.bots.bank_util.PSBC.psbc_keyboard import *
from server.bots.bank_util.PSBC.psbc_helper import *
from server.bots.bank_util.PSBC.psbc_check import *

"""
开发 APP 信息
- 版本 7.0.6
"""

_package = 'com.yitong.mbank.psbc'


class PSBCActivityExecutorBase(BotActivityExecutor):
    def _dump_hierarchy(self, d, check_error=True):
        """
        加载结构，使用代理类检查页面是否有错误

        :param check_error: 是否检查错误
        """
        retry_limit = 5
        while True:
            source = super()._dump_hierarchy(d, check_error=check_error)
            if check_error:
                had_error, error_msg = PSBCErrorChecker.check(d, source)
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
        """等待加载完成 或 抛出异常"""
        _r = self._exec_retry('等待加载完成', retry_limit=60, interval_second=1,
                              func=lambda: not self._is_loading(d))
        if not _r:
            raise BotParseError('加载页面失败，一直提示加载中')

    def _is_loading(self, d: u2.Device, source: str = None):
        """是否为请求后台加载中"""
        source = source or self._dump_hierarchy(d)
        x_load = d.xpath('//*[@resource-id="time-list-loadmore-text"]', source)
        # 正在加载...
        if x_load.exists and StrHelper.contains('正在加载', x_load.get_text()):
            return True
        loading_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/progress_dialog_tv"]'
        x_loading = d.xpath(loading_xpath, source)
        # 交易正在处理，请耐心等待
        return x_loading.exists and StrHelper.contains('交易正在处理', x_loading.get_text())

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        # 因 App 返回会出现不准确情况，固每次都返回到主页
        # 例如账户页面，有银行卡详情时，需要返回2次才到主页，进入明细后需要返回3次才到主页
        # 部分OPPO手机，触发返回后，页面节点会获取不到，需要返回到主页再次进入即可
        x_home = ctx.d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/btnTopRight"]', ctx.source)
        if x_home.exists:
            self._log('点击回到主页')
            x_home.click_exists(1)
        else:
            self._tooltip_back(ctx.d, ctx.source)

    def _tooltip_back(self, d: u2.Device, _source: str = None, wait_second: float = 0):
        """
        优先点击顶部返回，避免键盘仍处于打开状态等
        """
        is_toolbar_back = PSBCHelper.go_back(d, _source)
        if is_toolbar_back:
            self._log(f'点击页面返回')
        else:
            self._log(f'点击手机返回')
        # 连续点击返回，只会生效一次
        if wait_second:
            d.sleep(wait_second)


class PSBCMainActivityExecutor(PSBCActivityExecutorBase):
    _main_activity = ['com.yitong.mbank.psbc.android.activity.MainActivity', '.android.activity.MainActivity']

    def check(self, ctx: ActivityCheckContext):
        return StrHelper.any_contains(self._main_activity, ctx.current_activity)

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        account_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/llAccountInquiry"]'
        x_account = ctx.d.xpath(account_xpath, ctx.source)
        if not x_account.exists:
            # 先进入 首页 Tab
            ctx.d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/rbTabHome"]').click_exists(1)
            ctx.d.sleep(1)
            # 下次使用时，重新加载页面结构
            ctx.reset()

        if target_type == BotActivityType.Login or target_type == BotActivityType.QueryAccount:
            ctx.d.xpath(account_xpath, ctx.source).click_exists(1)
        elif target_type == BotActivityType.TransferIndex:
            ctx.d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/llSmartTransfer"]').click_exists(1)


class PSBCLoginActivityExecutor(PSBCActivityExecutorBase):
    _login_activity = ['com.yitong.mbank.psbc.android.activity.LoginActivity', '.android.activity.LoginActivity']
    _re_exist_name = re.compile(r'(\d+\**\d+)')

    def check(self, ctx: ActivityCheckContext):
        return StrHelper.any_contains(self._login_activity, ctx.current_activity)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        """执行登录
        1. 已登录成功时，不显示`登录账号`文本框，仅支持与录入登录账号匹配时
        2. 未登录过，支持输入账号和密码
        """
        self._log('进入登录页')
        account = ctx.account
        d = ctx.d

        # 已登录账号时，显示账号可能会很慢
        _r = self._exec_retry('检查登录账号', retry_limit=60, func=lambda: self._check_login_name(d, account.login_name))
        if not _r:
            raise BotParseError('检查登录账号错误')
        elif _r == 'exist':
            self._log('检测到之前登录成功过')
        elif _r == 'new':
            self._log('输入登录账号')
            _r = self._exec_retry('输入登录账号', retry_limit=3, func=lambda: self._input_login_name(d, account.login_name))
            if not _r:
                raise BotParseError('输入登录账号错误', is_stop=True)

        self._log('输入登录密码')
        _r = self._exec_retry('输入登录密码', retry_limit=3, func=lambda: self._input_pwd(d, account.login_pwd))
        if not _r:
            raise BotParseError('输入登录密码错误', is_stop=True)

        if d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/etCode"]').exists:
            self._log('检测到需要输入验证码，目前不支持')
            # com.yitong.mbank.psbc:id/ivGetCode

        self._log('点击登录')
        self._retry_logic(3, lambda **_kwargs: self._login_submit(d=d, **_kwargs))

    def _login_submit(self, d: u2.Device, **kwargs):
        # 重试时错误消息
        error_msg = kwargs.get('error_msg')
        # 已阅读并同意以下协议：默认不点击，通过提示消息确定点击
        if error_msg and StrHelper.any_contains(['勾选同意', '电子银行隐私政策'], error_msg):
            d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/cb_privacy1"]').click_exists(0.2)
        # 登录，并对 提示 就行重试
        d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/btnLogin"]').click()
        if self._exec_retry('登录结果检查', retry_limit=60, func=lambda: self._login_result_check(d)):
            self._log('登录成功')
        else:
            # 避免多次重登锁卡，未登录成功，则强制停止
            raise BotParseError('未检查到登录结果', is_stop=True)

    @staticmethod
    def _input_login_name(d: u2.Device, login_name: str) -> bool:
        mobile_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/etAccount"]'
        d.xpath(mobile_xpath).click()
        d.sleep(0.3)
        # 先清空已输入账号 再输入
        kb = PSBCNumberKeyboard(d)
        # d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/ivClearPhone"]').click_exists(0.1)
        kb.clear()
        [kb.input(_t, 0.1) for _t in login_name]
        kb.close()
        input_text = d.xpath(mobile_xpath).get_text()
        return input_text == login_name

    def _input_pwd(self, d: u2.Device, login_pwd: str) -> bool:
        kb_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/llayout_keyboard_panel"]'
        pwd_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/etPasswd"]'
        # 已登录账号时，银行会自动打开密码键盘
        if not d.xpath(kb_xpath).exists:
            self._log('点击密码框')
            d.xpath(pwd_xpath).click()
            d.sleep(0.3)
        # 先清空已输入账号 再输入
        d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/ivClearPwd"]').click_exists(0.1)
        kb = PSBCFullPwdKeyboard(d, kb_xpath)
        [kb.input(_t, 0.1) for _t in login_pwd]
        kb.close()
        input_text = d.xpath(pwd_xpath).get_text()
        return len(input_text) == len(login_pwd)

    def _login_result_check(self, d: u2.Device):
        # 跳转页面，表示成功
        if not DeviceHelper.is_in_activity(d, self._login_activity):
            return True
        # 检查错误
        self._dump_hierarchy(d)
        return False

    def _check_login_name(self, d: u2.Device, login_name: str) -> Union[str, bool]:
        _source = self._dump_hierarchy(d)
        x_exist_name = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/tv_hello"]', _source)
        if d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/etAccount"]', _source).exists:
            return 'new'
        elif x_exist_name.exists and x_exist_name.get_text():
            exist_name = x_exist_name.get_text()
            matched_name = self._re_exist_name.search(exist_name)
            if not matched_name:
                raise BotParseError('未找到已登录账号信息', is_stop=True)
            if not BotHelper.is_match_num_mask(matched_name.group(1), login_name):
                raise BotCategoryError(ErrorCategory.Environment,
                                       '已登录账号和后台录入账号不匹配，重新登录手机银行或检查后台录入账号', is_stop=True)
            return 'exist'
        return False


class PSBCAccountActivityExecutor(PSBCActivityExecutorBase):
    # card0
    _re_card_index = re.compile(r'card(\d+)$')
    # 连续未识别账户余额次数
    _un_recognize_count = 0

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source: str):
        # 部分手机，不固定加载不到页面节点
        # and d.xpath('//*[@resource-id="list"]', source).exists
        return PSBCHelper.is_eq_title(d, source, '我的账户')

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入我的账户')
        d = ctx.d
        self._wait_loading(d)

        x_list = d.xpath('//*[@resource-id="list"]')
        x_list.wait(20)
        # 进入页面后多等2秒，保证异步加载完成
        d.sleep(2)

        card_index, card_xpath = self._expand_card(ctx)
        balance = self._get_card_balance(d, card_xpath, card_index)
        if not balance:
            raise BotParseError('未获取到银行卡余额')
        return {'balance': BotHelper.amount_fen(balance)}

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        is_query_trans = target_type == BotActivityType.QueryTrans
        is_transfer = target_type == BotActivityType.Transfer

        if is_query_trans or is_transfer:
            card_index, card_xpath = self._expand_card(ctx)
            _source = self._dump_hierarchy(ctx.d)
            x_trans = ctx.d.xpath(
                f'//*[@resource-id="cardBelowOption{card_index}"]//*[contains(@text,"明细") or contains(@text,"转账")]',
                _source)
            trans_btn = x_trans.get()
            # 明细查询转账汇款 两者在一个节点上，需要通过计算偏移，点击按钮
            if is_query_trans and StrHelper.contains('明细查询', trans_btn.text):
                self._log(f'点击明细查询')
                DeviceHelper.click_ele_position(ctx.d, trans_btn, 2, 1)
            elif is_transfer and StrHelper.contains('转账汇款', trans_btn.text):
                self._log(f'点击转账汇款')
                DeviceHelper.click_ele_position(ctx.d, trans_btn, 2, 2)
            else:
                self._log(f'未找到下一步按钮 {target_type}')

    @staticmethod
    def _is_detail(d: u2.Device, source):
        x_card_detail = d.xpath('//*[@resource-id="detail"]', source)
        return x_card_detail.exists

    def _expand_card(self, ctx: ActivityExecuteContext, **_) -> [str, str]:
        """展开账户详情"""
        d = ctx.d

        _source = self._dump_hierarchy(d)
        # 兼容部分机型，加载不到节点情况
        if d.xpath('//android.webkit.WebView[not(*)]', _source).exists:
            self._un_recognize_count += 1
            if self._un_recognize_count > 5:
                raise BotParseError(f'重试 {self._un_recognize_count} 次仍未找到余额', is_stop=True)
            self.go_back(ctx, BotActivityType.Default)
            raise BotLogicRetryError('加载余额节点失败，等待重新进入')
        # 重置未识别次数
        self._un_recognize_count = 0

        # card0
        x_card_list = d.xpath('//*[@resource-id="list"]', _source).child('//*[starts-with(@resource-id, "card")]')
        card_list = x_card_list.all()
        self._log(f'银行卡列表数量: {len(card_list)}')
        for item in card_list:
            card_res_id = item.attrib.get('resource-id')
            card_index_match = self._re_card_index.search(card_res_id)
            if card_index_match is None:
                raise BotParseError('未找到银行卡信息')
            card_index = card_index_match.group(1)
            card_xpath = item.get_xpath()
            x_card_no = d.xpath(card_xpath, _source).child(f'/*[@resource-id="acctNo{card_index}"]')
            card_mask = PSBCHelper.get_card_no(x_card_no.get_text())
            if not BotHelper.is_match_card_num(card_mask, ctx.account.account):
                self._log(f'过滤不匹配卡号: {card_mask} ，银行卡索引 {card_index}')
                continue
            # 保证余额已显示，再点击详情。部分手机获取不到文本内容
            amt_exists = self._exec_retry('获取银行卡可用余额', 30,
                                          func=lambda: self._wait_card_amt(d, card_index, card_xpath))
            if not amt_exists:
                raise BotLogicRetryError(f'未获取到银行卡 {card_mask} 可用余额')

            if not self._is_detail(d, _source):
                self._log(f'银行卡 {card_mask} 展开详情')
                x_card_no.click()
                d.sleep(0.5)
            return card_index, card_xpath
        raise BotCategoryError(ErrorCategory.Data, BotErrorMsg.NotMatchedCardNo)

    def _wait_card_amt(self, d: u2.Device, card_index, card_xpath, **_):
        # 有重试时，不使用缓存图层
        source = self._dump_hierarchy(d)
        x_card_amt = d.xpath(card_xpath, source).child(
            f'/*[@resource-id="kyye{card_index}"]/*[@resource-id="amt-{card_index}"]')
        card_amount = x_card_amt.get_text() if x_card_amt.exists else None
        # 加载中 或 加载失败时
        if card_amount and StrHelper.not_empty(card_amount) and card_amount != '——':
            # self._log(f'银行卡可用余额显示正常')
            return True
        return False

    @staticmethod
    def _get_card_balance(d: u2.Device, card_xpath: str, card_index: str):
        # x_item_content = d.xpath('//*[@resource-id="detail"]')
        # x_item_content.wait(timeout=10)
        # if not x_item_content.exists:
        #     raise BotCategoryError(ErrorCategory.ParseWrong, '未找到银行卡详情信息')
        x_usable = d.xpath(card_xpath).child(
            '/*[@resource-id="kyye{0}"]/*[@resource-id="amt-{0}"]'.format(card_index))
        return PSBCHelper.convert_amount(x_usable.get_text())


class PSBCTransactionActivityExecutor(PSBCActivityExecutorBase):
    # 去重列表
    _distinct_list = DistinctList()
    # 查询流水终止条件
    _last_trans: Transaction
    _max_query_count: int
    _start_time: datetime
    # 最后一项流水项高度，避免滑过导致流水丢失
    _last_item_height: int = 0
    # 列表滑动高度，读取流水列表滑动时需要
    _list_swipe_height: int = 0
    # 列表项高度，用于分页滑动累加、避免显示不全，导致列表 key 不准确，多次进入详情
    _item_height: int = 0
    # 日期标题
    _item_date: Optional[str] = None

    def check(self, ctx: ActivityCheckContext):
        return PSBCHelper.is_eq_title(ctx.d, ctx.source, '明细查询') \
               and ctx.d.xpath('//*[@resource-id="time-list"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        """
        流水须知：
        1. 默认展示7天内交易
        2. 进入交易详情后，再返回交易列表，会重新刷新列表
        3. 账户列表包含需要数据，无对方账号
        4. 已处理情况：无流水时，默认一页流水，多页流水时
        """
        self._log('进入流水页面')
        self._reset_data()  # 每次重置当前流水列表
        self._last_trans, self._max_query_count, self._start_time, _ = BotActionParameter.get_query_trans(**kwargs)

        d = ctx.d
        self._wait_loading(d)

        had_next = True
        while had_next:
            # 进入详情后，返回列表会重置到首页列表内容
            had_next, need_swipe = self._curr_list(ctx)
            self._log(f'当前流水条数: {self._distinct_list.count()}')
            if need_swipe:
                move = self._list_swipe_height - self._last_item_height
                self._log(f'分页滑动高度: {move} = {self._list_swipe_height} - {self._last_item_height}')
                # 滑动需计算真实高度
                DeviceHelper.swipe_up_until(ctx.d, ctx.win_size_height, move)

        trans_list = self._distinct_list.data_list()
        return BotHelper.sort_trans_list(trans_list)

    def _reset_data(self):
        self._distinct_list.reset()
        self._list_swipe_height = 0
        self._item_height = 0
        self._last_item_height = 0
        self._item_date = None

    def _curr_list(self, ctx: ActivityExecuteContext) -> (bool, bool):
        d = ctx.d
        # 滑动后 显示 加载中
        self._wait_loading(d)

        # 等30秒保证加载完成
        ctx.d.xpath('//*[@resource-id="time-list"]').wait(30)
        # 等会儿，滑动后不稳定
        d.sleep(0.5)
        _source = self._dump_hierarchy(ctx.d)
        x_trans_list = ctx.d.xpath('//*[@resource-id="time-list"]', _source)
        if not x_trans_list.exists:
            raise BotParseError('未获取到流水列表')
        _, _, _, l_height = x_trans_list.get().rect
        x_items = x_trans_list.child('/*')
        if not x_items.exists:
            raise BotParseError('未获取到流水列表内容项')

        item_list = x_items.all()
        self._log(f'流水列表内容长度: {len(item_list)}')
        for item in item_list:
            item_values = d.xpath(item.get_xpath(), _source).child('/*').all()
            if len(item_values) == 0:
                continue
            # 日期分隔 fw-gen-10001-group-2021年10月04日
            # 底部温馨提示 yui-desc
            item_r_id = item.attrib.get("resource-id").replace('fw-gen-10001-group-', '')
            if item_r_id:
                if item_r_id != 'yui-desc':
                    self._item_date = item_r_id
                    # self._log(f'标题日期: {self._item_date}')
                continue
            _, _, _, item_height = item.rect
            self._last_item_height = item_height
            # 设定第一项为列表项全显高度
            if not self._item_height:
                self._item_height = item_height
            # 小于列表项全显高度则忽略
            if (item_height + 20) < self._item_height:
                continue
            # 用于快速滑动找到未获取详情那条记录
            item_key = f'{self._item_date}__{self._get_item_key(item_values)}'
            # 列表项过滤
            # 跨行汇款张三110.00网上银行余额10.00时间2022年01月03日14时52分30秒
            if self._distinct_list.contains_key(item_key):
                # self._log(f'流水明细数据已存在数据，忽略: {item_id}')
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

                # 非首屏时，每次都要滑动
                if self._list_swipe_height > 0:
                    # 因无法确定滑动准确性，滑动后仍在包含数据中，则累加 1/2 项高度，否则累加每项高度
                    self._list_swipe_height += self._item_height / 2 if contains_detail else self._item_height
                    return True, True
                # 避免点击详情过快
                d.sleep(0.5)

        # 已读取到列表最后时，有显示无更多数据
        x_load = d.xpath('//*[@resource-id="time-list-loadmore-text"]', _source)
        if x_load.exists and StrHelper.contains('没有更多数据', x_load.get_text()):
            self._log('[查询流水] 没有更多数据')
            return False, False

        # 列表已检查不到新数据时，则触发默认滑动，首次使用第一屏高度，再次累加内容项高度
        if self._list_swipe_height == 0:
            self._list_swipe_height = l_height
        had_next = len(item_list) > 0
        return had_next, had_next

    @staticmethod
    def _get_item_key(elements: List[u2.xpath.XMLElement]):
        if not elements:
            return ''
        # 避免不固定文字
        return ''.join([(_s.text.replace('可退款', '') + '_') for _s in elements])

    def _get_detail(self, d: u2.Device, item_parent: u2.xpath.XMLElement) -> Optional[Transaction]:
        item_parent.click()
        try:
            _r = self._exec_retry('等待交易明细详情', 60, lambda **_kwargs: self._wait_trans_detail(d))
            if not _r:
                raise BotParseError('未获取到交易明细详情')
            _source = self._dump_hierarchy(d)
            return self._parse_detail(d.xpath('//*[@resource-id="detailShow"]/*[1]/*', _source).all())
        finally:
            DeviceHelper.press_back(d)

    def _parse_detail(self, item_nodes: List[u2.xpath.XMLElement]) -> Optional[Transaction]:
        """解析详情，兼容 收入、支出、利息"""

        nodes_len = len(item_nodes)
        if nodes_len < 3:
            self._log('流水详情内容数量过小，忽略')
            return None

        # -￥5.00  or  +￥40,000.00
        amount = BotHelper.amount_fen(PSBCHelper.convert_amount(item_nodes[0].text))
        # 账户余额￥29,988.26
        balance_str = item_nodes[1].text.replace('账户余额', '')
        balance = BotHelper.amount_fen(PSBCHelper.convert_amount(balance_str))
        direction = 1 if amount > 0 else 0
        trans = Transaction(amount=abs(amount), balance=balance, direction=direction, extension={})

        pass_next = False
        # 前两个节点为固定 交易金额 和 余额
        for i in range(2, nodes_len):
            if pass_next:
                pass_next = False
                continue

            # 配对项值为空时，不会为值节点
            _key = item_nodes[i].text
            _key_val = item_nodes[i + 1].text if (i + 1) < nodes_len else None
            if StrHelper.contains('交易时间', _key):
                # 2022/02/13 12:58:27
                trans.time = DateTimeHelper.to_datetime(_key_val)
            elif StrHelper.contains('摘要', _key):
                trans.extension['摘要'] = _key_val
            elif StrHelper.any_contains(['付款人', '收款人'], _key):
                trans.name = _key_val
            elif StrHelper.any_contains(['付款账号', '收款账号'], _key):
                trans.customerAccount = PSBCHelper.get_card_no(_key_val)
            elif StrHelper.any_contains(['附言', '备注'], _key):
                trans.postscript = _key_val
            elif StrHelper.contains('交易卡号', _key):
                # trans.extension['交易卡号'] = PSBCHelper.get_card_no(_key_val)
                pass
            elif StrHelper.any_contains(['付款行名', '收款行名'], _key):
                trans.extension['对方行名'] = _key_val
            else:
                self._log(f'[流水详情] 未知项 {_key} -> {_key_val}')
                continue
            # 默认表示已配对读取
            pass_next = True

        return trans

    def _wait_trans_detail(self, d: u2.Device):
        return PSBCTransactionDetailActivityExecutor.is_current(d, self._dump_hierarchy(d))


class PSBCTransferIndexActivityExecutor(PSBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return PSBCHelper.is_eq_title(ctx.d, ctx.source, '转账汇款') \
               and ctx.d.xpath('//*[@resource-id="cardTrans"]', ctx.source).exists

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        if target_type == BotActivityType.Transfer:
            ctx.d.xpath('//*[@resource-id="cardTrans"]').click_exists(1)
        if target_type == BotActivityType.QueryReceipt or target_type == BotActivityType.QueryReceiptTransition:
            # 转账记录查询
            ctx.d.xpath('//*[@resource-id="transStatus"]').click_exists(1)


class PSBCTransferActivityExecutor(PSBCActivityExecutorBase):
    _transferee: Transferee
    _sms_code_func: Callable

    def check(self, ctx: ActivityCheckContext):
        # 转账填写页面 OR 转账认证页面
        return PSBCHelper.is_eq_title(ctx.d, ctx.source, '银行账号转账') \
               and (ctx.d.xpath('//*[@resource-id="TRANS_AMT" or @resource-id="confirm"]', ctx.source).exists
                    or ctx.d.xpath('//*[@resource-id="_transeDialog"]', ctx.source).exists)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入转账页面')
        self._transferee, self._sms_code_func = BotActionParameter.get_transfer(**kwargs)
        d = ctx.d
        self._wait_loading(d)

        name_xpath = '//*[@resource-id="PAYEE_NAME"]'
        card_xpath = '//*[@resource-id="PAYEE_ACCT_NO"]'
        bank_xpath = '//*[@resource-id="BANK_NAME"]'
        postscript_xpath = '//*[@resource-id="REMARK"]'

        # 先输入金额，因输入卡号后，同行转账会显示`业务类型`字段，导致获取不到`转账金额`节点
        self._input_amount(ctx)

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

        # 向上滑动，显示确认按钮
        d.swipe_ext(direction='up', scale=0.5)
        d.sleep(1)

        if self._transferee.postscript:
            self._log(f'输入附言: {self._transferee.postscript}')
            d.xpath(postscript_xpath).set_text(self._transferee.postscript)
            # 关闭键盘输入
            DeviceHelper.press_back(d)

        self._log(f'点击转账')
        d.xpath(f'//*[@resource-id="confirm"]').click()
        self._wait_loading(d)

        self._log(f'检查转账认证方式和获取短信验证码')
        send_sms_node: u2.xpath.XMLElement
        send_sms_node = self._exec_retry('获取发送短信验证码节点', 30, lambda: self._get_send_sms_node(d))
        if send_sms_node is None:
            self._save_screenshot_transfer(d, '转账失败_未找到 [获取短信验证码按钮]')
            self._tooltip_back(d)
            raise BotErrorBase('未识别到输入短信验证码操作，疑似转账过程提示错误')
        send_sms_node.click()
        self._wait_loading(d)

        self._log(f'等待短信验证码')
        sms_code = BotHelper.get_sms_code(sms_code_func=self._sms_code_func)
        # 短信验证码，等待顶部短信通知关闭
        d.sleep(6)
        self._log(f'输入短信验证码')
        # mulTransDialogCode0
        self._trans_child(d, '//*[contains(@resource-id,"mulTransDialogCode")]').set_text(sms_code)
        # 关闭键盘输入
        DeviceHelper.press_back(d)

        # 非必需，交易密码验证
        x_pay_pwd = d.xpath('//android.widget.EditText[contains(@text,"交易密码") or @password="true"]')
        if x_pay_pwd.exists:
            self._log(f'输入交易密码')
            self._input_pay_pwd(d, x_pay_pwd.get(), ctx.account.payment_pwd)

        # dialogButton0
        self._log(f'确定转账')
        self._trans_child(d, '//*[contains(@resource-id,"dialogButton")][@text="确定"]').click()
        self._wait_loading(d)

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

    def _input_amount(self, ctx: ActivityExecuteContext):
        d = ctx.d
        payer_card_xpath = '//*[@resource-id="ACCT_NO"]'
        usable_xpath = '//*[@resource-id="USEABLE_AMT"]'
        amount_xpath = '//*[@resource-id="TRANS_AMT"]'
        realtime_xpath = '//android.widget.RadioButton[contains(@text,"实时")]'

        # 检查付款账号、可用余额
        payer_text = d.xpath(payer_card_xpath).get_text()
        payer_card_no = PSBCHelper.get_card_no(payer_text)
        if not BotHelper.is_match_card_num(payer_card_no, ctx.account.account):
            msg = f'未匹配付款卡号 {payer_card_no}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.Data, msg, is_stop=True)

        payer_amt_text = d.xpath(usable_xpath).get_text()
        usable_amt = PSBCHelper.convert_amount(payer_amt_text)
        trans_amount = self._transferee.amount_yuan()
        if usable_amt < trans_amount:
            msg = f'可用余额 {usable_amt} 小于转账余额 {trans_amount}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.BankWarning, msg)

        # 输入转账金额
        self._log(f'输入转账金额')
        while True:
            # 每次点击转账金额，都会重新输入
            d.xpath(amount_xpath).click()
            d.sleep(0.5)
            kb = PSBCNumberKeyboard(d)
            [kb.input(_s, interval=0.2, has_point=True) for _s in self._transferee.amount_yuan_str()]
            kb.close()
            x_payee_amt = d.xpath(amount_xpath, self._dump_hierarchy(d)).get_text()
            payee_amt = PSBCHelper.convert_amount(x_payee_amt)
            if payee_amt == trans_amount:
                self._log(f'转账金额输入正确: {payee_amt}')
                break
            else:
                self._log(f'转账金额输入不正确: {payee_amt}，重新输入')

        self._log(f'选择实时转账')
        d.xpath(realtime_xpath).click_exists(5)

    def _get_choose_bank(self, d: u2.Device, item_xpath: str):
        # 检查错误
        _source = self._dump_hierarchy(d)
        x_item = d.xpath(item_xpath, _source)
        # 未选择时为 【请选择】
        bank_text = x_item.get_text() if x_item.exists else None
        if bank_text and not StrHelper.contains('请选择', bank_text):
            return bank_text
        return False

    def _get_send_sms_node(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        # 获取验证码
        get_sms_node = self._trans_child(d, '//android.widget.Button[contains(@text,"获取验证码")]', _source)
        return get_sms_node.get() if get_sms_node.exists else None

    @staticmethod
    def _trans_child(d: u2.Device, child_xpath: str, source=None):
        return d.xpath(f'//*[@resource-id="_transeDialog"]', source).child(child_xpath)

    def _input_pay_pwd(self, d: u2.Device, pay_pwd_node: u2.xpath.XMLElement, pwd: str):
        if not pwd:
            raise BotCategoryError(ErrorCategory.Data, '交易密码 不能为空', is_stop=True)
        if not pay_pwd_node:
            raise BotParseError(f'未识别到交易密码节点')

        pay_pwd_node.click()
        d.sleep(1)

        self._log('开始输入 交易密码')
        kb_xpath = '//*[@resource-id="com.yitong.mbank.psbc:id/llayout_keyboard_panel"]'
        pwd_kb = PSBCFullPwdKeyboard(d, kb_xpath)
        [pwd_kb.input(_char, 0.2) for _char in pwd]
        pwd_kb.close()
        self._log('结束输入 交易密码')

    def _transfer_result_check(self, d: u2.Device):
        """转账后返回上页处理"""
        # 检查错误和成功结果
        _source = self._dump_hierarchy(d)
        if PSBCTransferResultActivityExecutor.is_current(d, _source):
            try:
                trans_result, error_detail = PSBCTransferResultActivityExecutor.trans_result(d, _source)
                self._log(f'转账结果: {trans_result}, {error_detail}')
                if not trans_result:
                    raise BotCategoryError(ErrorCategory.BankWarning, error_detail)
                elif trans_result:
                    return True
            finally:
                if settings.debug:
                    self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功')
                # 点击完成，返回到转账首页
                PSBCTransferResultActivityExecutor.go_back_core(d, _source)
        # 未检查到结果，重试
        return False


class PSBCReceiptTransitionActivityExecutor(PSBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return PSBCHelper.is_eq_title(ctx.d, ctx.source, '转账记录查询') \
               and ctx.d.xpath('//*[@resource-id="transferRecord"]//*[@text="转账记录"]', ctx.source).exists

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        if target_type == BotActivityType.QueryReceipt:
            ctx.d.xpath('//*[@resource-id="transferRecord"]//*[@text="转账记录"]').click_exists(1)


class PSBCReceiptIndexActivityExecutor(PSBCActivityExecutorBase):
    # 去重列表
    _distinct_list = DistinctList()
    _max_query_count: int
    _last_transferee: Transferee
    # 每项高度，避免显示不全，导致列表 key 不准确，多次进入详情
    _item_height = 0

    def check(self, ctx: ActivityCheckContext):
        return PSBCHelper.is_eq_title(ctx.d, ctx.source, '转账记录') \
               and ctx.d.xpath('//*[@resource-id="searchBar" or @resource-id="tab1"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        """
        回单须知：
        1. 默认展示7天内交易
        2. 已处理情况：首屏回单，无记录
        3. 因目前只抓取转账的那一条回单，固理解为只获取最新一条即可
        """
        self._log('进入回单页面')
        self._reset_data()  # 每次重置当前列表
        self._last_transferee, self._max_query_count = BotActionParameter.get_query_receipt(**kwargs)

        d = ctx.d
        self._wait_loading(d)

        # 只读取首屏回单，因目前只抓取转账的那一条回单
        self._curr_list(ctx)

        receipt_list = self._distinct_list.data_list()
        return BotHelper.sort_receipt_list(receipt_list)

    def _reset_data(self):
        self._distinct_list.reset()
        self._item_height = 0

    def _curr_list(self, ctx: ActivityExecuteContext) -> (bool, bool):
        d = ctx.d
        # 滑动后 显示 加载中
        self._wait_loading(d)

        # 等30秒保证加载完成，有数据 或 无数据时
        ctx.d.xpath('//*[@resource-id="list" or @resource-id="list-loadmore"]/*').wait(30)
        # 等会儿，保证获取到元素渲染完成
        d.sleep(0.5)

        _source = self._dump_hierarchy(d)
        item_list = d.xpath('//*[@resource-id="list"]/*', _source).all()
        self._log(f'回单列表内容长度: {len(item_list)}')
        for item in item_list:
            item_values = d.xpath(item.get_xpath(), _source).child('//*[string-length(@text)>0]').all()
            if len(item_values) == 0:
                continue
            _, _, _, _height = item.rect
            # 设定第一项为列表项全显高度
            if not self._item_height:
                self._item_height = _height
            # 小于列表项全显高度则忽略
            if (_height + 20) < self._item_height:
                continue
            item_key = self._get_item_key(item_values)
            # 305_张三(尾号8883)_-￥5.00_2022-02-13 12:58:27_余额 ￥5.00_
            if self._distinct_list.contains_key(item_key):
                # self._log(f'流水明细数据已存在数据，忽略: {item_id}')
                continue

            item_detail = self._get_detail(d, item)
            self._log(f'回单明细: {item_detail}')
            if item_detail is not None:
                if self._distinct_list.contains_key_val(item_key, item_detail):
                    self._log(f'回单明细数据已存在数据，忽略: {item_detail.name}')
                else:
                    self._distinct_list.append(item_key, item_detail)

                if BotHelper.is_transfer_receipt(item_detail, self._last_transferee):
                    self._log(f'查询到最后一条回单，终止查询，回单 ({item_detail.time}, {item_detail.amount})')
                    return False, False
                if self._distinct_list.count() >= self._max_query_count:
                    self._log(f'符合查询回单条数限制，终止查询，条数: {self._distinct_list.count()}')
                    return False, False
            d.sleep(0.5)

        # 无数据 或 已读取到列表最后时，显示无更多数据
        x_load = d.xpath('//*[@resource-id="list-loadmore-text"]', _source)
        if x_load.exists and StrHelper.contains('没有更多数据', x_load.get_text()):
            self._log('[查询回单] 没有更多数据')
            return False, False
        had_next = len(item_list) > 0
        return had_next, had_next

    @staticmethod
    def _get_item_key(elements: List[u2.xpath.XMLElement]):
        if not elements:
            return ''
        # 避免不固定文字
        return ''.join([(_s.text.replace('可退款', '') + '_') for _s in elements])

    def _get_detail(self, d: u2.Device, item_parent: u2.xpath.XMLElement):
        """获取详情"""
        item_parent.click()
        try:
            _r = self._exec_retry('等待交易明细详情', 60, lambda **_kwargs: self._wait_receipt_detail(d))
            if not _r:
                raise BotParseError('未获取到交易明细详情')
            self._wait_loading(d)
            return self._parse_detail(d)
        finally:
            self._tooltip_back(d, wait_second=0.5)

    def _parse_detail(self, d: u2.Device):
        """解析详情，兼容 卡号转账"""
        _source = self._dump_hierarchy(d)
        item_nodes = d.xpath('//*[@resource-id="view"]/*', _source).all()
        nodes_len = len(item_nodes)
        if nodes_len < 5:
            self._log(f'回单详情内容项过小，忽略')
            return None

        # -￥5.00  or  +￥40,000.00
        amount = BotHelper.amount_fen(PSBCHelper.convert_amount(item_nodes[0].text))
        # 余额大于0 为收款记录(也无回单按钮)，无需查回单
        if amount > 0:
            return None
        # 账户余额￥29,988.26
        # balance_str = item_nodes[1].text.replace('账户余额', '')
        # balance = BotHelper.amount_fen(PSBCHelper.convert_amount(balance_str))
        receipt = Receipt(amount=abs(amount))

        # 前两个节点为固定 交易金额 和 余额
        for i in range(2, nodes_len):
            # 配对项为 item 的两个子节点
            kv_nodes = d.xpath(item_nodes[i].get_xpath(), _source).child('/*').all()
            if len(kv_nodes) < 2:
                continue
            _key = kv_nodes[0].text
            _key_val = kv_nodes[1].text

            # 已识别配对项，但无需使用字段
            if StrHelper.any_contains(['付款行名', '交易卡号'], _key):
                pass
            elif StrHelper.contains('交易时间', _key):
                # 2022-02-10 04:37:01
                receipt.time = DateTimeHelper.to_datetime(_key_val)
            elif StrHelper.contains('摘要', _key):
                # 他行来账
                receipt.inner = not StrHelper.any_contains(['他行', '跨行'], _key_val)
            elif StrHelper.contains('收款行名', _key):
                # 中国邮政储蓄银行
                receipt.inner = StrHelper.any_contains(['中国邮政', '邮政银行', '邮政储蓄'], _key_val)
            elif StrHelper.any_contains(['付款人', '收款人'], _key):
                receipt.name = _key_val
            elif StrHelper.any_contains(['付款账号', '收款账号'], _key):
                receipt.customerAccount = PSBCHelper.get_card_no(_key_val)
            elif StrHelper.any_contains(['附言', '备注'], _key):
                receipt.postscript = _key_val
            else:
                self._log(f'[流水详情] 未知项 {_key} -> {_key_val}')
                continue

        self._parse_receipt_image(d, receipt)
        return receipt

    def _parse_receipt_image(self, d: u2.Device, receipt: Receipt):
        # 部分回单记录，没有电子回单图片。如：跨行转账网银发起，有误即退。
        x_receipt_img = d.xpath('//android.widget.Button[@text="电子回单"]')
        if not x_receipt_img.exists:
            return

        x_receipt_img.click()
        try:
            _r = self._exec_retry('等待回单图片', 60, lambda **_kwargs: self._wait_receipt_img(d))
            if not _r:
                raise BotParseError('未获取到回单凭证图片')
            d.sleep(0.5)  # 避免过快
            receipt.content = DeviceHelper.screenshot_base64(d)
            receipt.need_image_format()

            if settings.debug:
                self._save_screenshot_receipt(d, receipt.time, receipt.name)
        finally:
            self._tooltip_back(d, wait_second=0.5)

    def _wait_receipt_detail(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        return PSBCReceiptDetailActivityExecutor.is_current(d, _source)

    def _wait_receipt_img(self, d: u2.Device):
        _source = self._dump_hierarchy(d)
        return PSBCReceiptDetailImgActivityExecutor.is_current(d, _source)


class PSBCLoginVerifyActivityExecutor(PSBCActivityExecutorBase):
    """登录安全验证公共处理，页面流转过程中关闭元素或提示异常"""

    def check(self, ctx: ActivityCheckContext):
        d, _source = ctx.d, ctx.source
        # 登录安全认证
        if PSBCHelper.is_title(d, _source, '设备绑定'):
            raise BotCategoryError(ErrorCategory.Environment, '登录后需要安全验证，请先在手机完成认证', is_stop=True)
        return False


class PSBCTransactionDetailActivityExecutor(PSBCActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return PSBCHelper.is_eq_title(d, source, '交易详情') \
               and d.xpath('//*[@resource-id="detailShow"]/*[1]/*', source).exists


class PSBCTransferResultActivityExecutor(PSBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self.go_back_core(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return PSBCHelper.is_eq_title(d, source, '转账结果') and d.xpath('//*[@resource-id="transResult"]', source).exists

    @staticmethod
    def trans_result(d: u2.Device, source=None) -> tuple[bool, str]:
        x_result = d.xpath('//*[@resource-id="transResult"]', source)
        result_msg = x_result.get_text()
        # 转账成功
        return '转账成功' in result_msg, result_msg

    @staticmethod
    def go_back_core(d: u2.Device, source=None):
        # 完成
        source = source or d.dump_hierarchy()
        x_done = d.xpath('//*[@resource-id="gotoHomePage"]', source)
        x_home = d.xpath('//*[@resource-id="com.yitong.mbank.psbc:id/btnTopRight"]', source)
        if x_done.exists:
            x_done.click()
        if x_home.exists:
            x_home.click()
        else:
            PSBCHelper.go_back(d, source)


class PSBCReceiptDetailActivityExecutor(PSBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return PSBCHelper.is_eq_title(d, source, '转账记录') \
               and d.xpath('//*[@resource-id="view" or @resource-id="tab2"]', source).exists


class PSBCReceiptDetailImgActivityExecutor(PSBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return PSBCHelper.is_eq_title(d, source, '电子回单') \
               and d.xpath('//*[@resource-id="container" or @resource-id="tab3"]', source).exists
