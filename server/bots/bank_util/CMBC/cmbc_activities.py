import re
import time
from datetime import datetime
from typing import Callable, Union

from server import settings
from server.models import Transaction, Transferee, Receipt

from server.bots.act_scheduler import *

from server.common_helpers import StrHelper, DateTimeHelper
from server.bots.act_scheduler.u2_helpers import DeviceHelper
from server.bots.act_scheduler.bot_helpers import BotHelper
from server.bots.common.common_models import DistinctList

from server.bots.bank_util.CMBC.cmbc_keyboard import *
from server.bots.bank_util.CMBC.cmbc_helper import *
from server.bots.bank_util.CMBC.cmbc_check import CMBCErrorChecker


_package = 'cn.com.cmbc.newmbank'
_version = '6.11'


def _xpath_desc_text(text, contains=False) -> str:
    if contains:
        return f'[contains(@text,"{text}") or contains(@content-desc,"{text}")]'
    return f'[@text="{text}" or @content-desc="{text}"]'


def _ele_desc_text(ele: Union[u2.xpath.XMLElement, u2.xpath.XPathSelector]) -> Optional[str]:
    if isinstance(ele, u2.xpath.XPathSelector):
        ele = ele.get()
    if isinstance(ele, u2.xpath.XMLElement):
        return ele.attrib.get("content-desc") or ele.attrib.get("text")
    return None  # 正常不会进入此处


def _get_card_child_ele(d: u2.Device, _source, card_xpath: str, child_xpath: str) -> u2.xpath.XPathSelector:
    return d.xpath(card_xpath, _source).child(child_xpath)


class CMBCActivityExecutorBase(BotActivityExecutor):
    def _dump_hierarchy(self, d, check_error=True):
        retry_limit = 5
        while True:
            source = super()._dump_hierarchy(d, check_error=check_error)
            if check_error:
                had_error, error_msg = CMBCErrorChecker.check(d, source)
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

    def _find_keyboard_node(self, d: u2.Device, _source: str = None) -> Optional[u2.xpath.XMLElement]:
        kb_xpath = f'//android.widget.FrameLayout/android.view.View[@package="{_package}"][not(*)]'
        x_kb = d.xpath(kb_xpath, _source)
        return x_kb.get() if x_kb.exists else None

    @staticmethod
    def _is_loading(d: u2.Device, _source: str = None):
        """是否为请求后台加载中"""
        loading_xpath = '//*[@resource-id="cnt-wrapper"]/*/*/android.view.View/android.widget.Image[not(*)]'
        return d.xpath(loading_xpath, _source).exists

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self._log('点击页面返回')
        self._tooltip_back(ctx.d, ctx.source)

    def _tooltip_back(self, d: u2.Device, _source: str):
        x_back = d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/btn_back"]', _source)
        if x_back.exists:
            self._log(f'点击页面返回')
            x_back.click()
        else:
            self._log(f'点击手机返回')
            DeviceHelper.press_back(d)


class CMBCMainActivityExecutor(CMBCActivityExecutorBase):
    _main_activity = ['cn.com.cmbc.newmbank.activity.MainActivity', '.activity.MainActivity']

    def check(self, ctx: ActivityCheckContext):
        return StrHelper.any_contains(self._main_activity, ctx.current_activity)

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        account_btn_xpath = '//*[@resource-id="cn.com.cmbc.newmbank:id/item_tv"][@text="我的账户"]'
        x_account = ctx.d.xpath(account_btn_xpath, ctx.source)
        if not x_account.exists:
            index_btn_xpath = '//*[@resource-id="cn.com.cmbc.newmbank:id/bottombar_item_img"][@content-desc="首页"]'
            ctx.d.xpath(index_btn_xpath, ctx.source).click_exists(1)
            ctx.d.sleep(1)
            ctx.reset()  # 下次使用时，重新加载页面结构

        x_account = ctx.d.xpath(account_btn_xpath, ctx.source)
        if target_type == BotActivityType.Login or target_type == BotActivityType.QueryAccount:
            x_account.click_exists(1)


class CMBCLoginActivityExecutor(CMBCActivityExecutorBase):
    _login_activity = ['.activity.login.tradlogin.LoginActivity',
                       '.login.view.activity.PwdLoginActivity',
                       'cn.com.cmbc.newmbank.login.view.activity.PwdLoginActivity']

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.current_activity) and CMBCActivityWebView.is_title(ctx.d, ctx.source, '登录')

    def is_current(self, activity: str):
        return StrHelper.any_contains(self._login_activity, activity)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        u_phone = ctx.d(resourceId="cn.com.cmbc.newmbank:id/et_user_phone")
        if u_phone.exists:
            self._log('输入手机号')
            u_phone.set_text(ctx.account.login_name)
        self._retry_logic(3, lambda **_kwargs: self._login_logic(ctx, **_kwargs))

    def _login_logic(self, ctx: ActivityExecuteContext, **kwargs):
        d = ctx.d
        account = ctx.account
        error_msg = kwargs.get('error_msg')  # 重试时错误消息

        pwd_retry_limit = 2  # 最多试2次
        done_pwd = False
        while not done_pwd and pwd_retry_limit > 0:
            pwd_retry_limit -= 1
            d(resourceId="cn.com.cmbc.newmbank:id/pge_password").click()
            d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/imgDeletePwd"]').click_exists(1)
            d.sleep(0.5)  # 等待点选后的显示键盘
            done_pwd = self._input_password(d, account.login_pwd)
        if not done_pwd:
            raise BotParseError('输入密码失败')

        if error_msg and StrHelper.any_contains(['勾选同意', '隐私政策'], error_msg):
            ctx.d(resourceId="cn.com.cmbc.newmbank:id/lpcb_login_privacy").click_exists(0.2)
        ctx.d(resourceId="cn.com.cmbc.newmbank:id/btnLogin").click()

        if self._exec_retry('登录结果检查', 100, lambda: self._login_result_check(ctx.d)):
            self._log('登录成功')
        else:
            raise BotParseError('未检查到登录结果', is_stop=True)

    def _input_password(self, d: u2.Device, pwd: str):
        if not pwd:
            raise BotCategoryError(ErrorCategory.Data, '密码不能为空', is_stop=True)

        dump_source = self._dump_hierarchy(d)
        kb_node = self._find_keyboard_node(d, dump_source)
        if kb_node is None:
            raise BotParseError(f'未识别到密码键盘信息')

        self._log('开始输入登录密码')
        pwd_keyboard = CMBCLoginPwdKeyboard(d, kb_node.get_xpath(), dump_source)
        [pwd_keyboard.input(_char, 0.01) for _char in pwd]
        pwd_keyboard.close()  # 关闭重新点开会从重置键盘字符

        pwd_text = d(resourceId="cn.com.cmbc.newmbank:id/pge_password").get_text()
        match_len = len(pwd_text) == len(pwd)
        self._log(f'登录密码输入结果: 是否正确 {match_len}, 长度 {len(pwd_text)}, 脱敏密码 {pwd_text}')
        return match_len

    def _login_result_check(self, d: u2.Device):
        curr_act = DeviceHelper.current_activity(d)
        if not self.is_current(curr_act):
            return True  # 跳转页面，表示成功

        self._dump_hierarchy(d)
        return False


class CMBCAccountActivityExecutor(CMBCActivityExecutorBase):
    def check(self, ctx: ActivityCheckContext):
        return CMBCActivityWebView.is_title(ctx.d, ctx.source, '我的账户') and ctx.d.xpath(
            '//*[@resource-id="cnt-wrapper"]',
            ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        d = ctx.d
        _, card_xpath = self._retry_logic(30, lambda **_kwargs: self._get_card_xpath(ctx, **_kwargs))
        dump_source = None  # self._dump_hierarchy(d)
        x_balance = _get_card_child_ele(d, dump_source, card_xpath, '/*[6]')
        balance = CMBCHelper.convert_amount(_ele_desc_text(x_balance))
        self._log(f'查询余额: {balance}')
        return {'balance': BotHelper.amount_fen(balance)}

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        if target_type not in [BotActivityType.QueryTrans, BotActivityType.Transfer, BotActivityType.TransferIndex]:
            return

        _, card_xpath = self._retry_logic(30, lambda **_kwargs: self._get_card_xpath(ctx, **_kwargs))
        _source = self._dump_hierarchy(ctx.d)

        if target_type == BotActivityType.QueryTrans:
            x_trans_detail = _get_card_child_ele(ctx.d, _source, card_xpath, '//*[@content-desc="明细"]')
            self._log(f'点击明细按钮')
            x_trans_detail.click_exists(1)
        elif target_type == BotActivityType.Transfer or target_type == BotActivityType.TransferIndex:
            x_transfer = _get_card_child_ele(ctx.d, _source, card_xpath, '//*[@content-desc="转账"]')
            self._log(f'点击转账按钮')
            x_transfer.click_exists(1)

    def _get_card_xpath(self, ctx: ActivityExecuteContext, **_) -> [str, str]:
        """获取匹配账户详情"""
        d = ctx.d
        d.sleep(2)  # 广告消息未显示完

        if not d.xpath('//*[@resource-id="cnt-wrapper"]/*[node()][last()]/*').wait(100):  # 延长等待时间，有时会很慢
            raise BotParseError('未获取到银行卡列表')

        x_card_list = d.xpath('//*[@resource-id="cnt-wrapper"]//*[@content-desc="icon"]/..')
        x_card_list.wait()  # 先等待加载元素，允许元素不存在
        if self._is_change_list_view(d):
            d.sleep(0.5)
        acct_list = x_card_list.all()

        if len(acct_list) > 1:
            self._log(f'账户列表数量: {len(acct_list)}')
        dump_source = self._dump_hierarchy(d)
        for item in acct_list:
            item_xpath = item.get_xpath()
            item_child = d.xpath(item_xpath, dump_source).child('/*').all()
            if len(item_child) < 2:
                continue
            card_no = CMBCHelper.get_card_no(_ele_desc_text(item_child[1]))
            if not card_no:
                raise BotLogicRetryError('加载卡号为空，需重试')
            if not StrHelper.is_match_card_num(card_no, ctx.account.account):
                self._log(f'过滤不匹配卡号:{card_no}')
                continue
            self._log(f'匹配到卡号: {card_no}')
            return item_xpath
        raise BotCategoryError(ErrorCategory.Data, BotErrorMsg.NotMatchedCardNo)

    def _is_change_list_view(self, d: u2.Device):
        """是否变更视图，目前仅支持卡片视角"""
        change_list_view = d.xpath(f'//*[@resource-id="cnt-wrapper"]//*{_xpath_desc_text("卡片视角")}')
        if change_list_view.exists:
            self._log('切换为卡片视角')
            change_list_view.click()
            return True
        return False


class CMBCTransactionActivityExecutor(CMBCActivityExecutorBase):
    _distinct_list = DistinctList()  # 去重列表
    _item_date_year: Optional[str] = None  # 日期标题
    _last_trans: Transaction
    _max_query_count: int
    _start_time: datetime
    _list_swipe_height: int = 0  # 列表滑动高度，读取流水列表滑动时需要
    _last_item_height: int = 0  # 最后一项流水项高度，避免滑过导致流水丢失
    _re_title_date_year = re.compile(r'(\d{4})年')
    _re_trans_date = re.compile(r'(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})')

    def check(self, ctx: ActivityCheckContext):
        d, _source = ctx.d, ctx.source
        return (CMBCActivityWebView.is_title(d, _source, '交易明细') and
                d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/rl_webkit_root"]', _source).exists)

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入流水页面')
        self._reset_data()  # 每次重置当前流水列表
        self._last_trans, self._max_query_count, self._start_time, _ = BotActionParameter.get_query_trans(**kwargs)

        d = ctx.d

        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))
        d.xpath('//*[@resource-id="cnt-wrapper"]/*[last()]/*/*/*/*/*').wait(30)

        had_next = True
        while had_next:
            had_next = self._curr_list(ctx)
            self._log(f'当前流水条数: {self._distinct_list.count()}')
            if had_next:
                move = min(self._last_item_height * 3, self._list_swipe_height)
                self._log(f'分页滑动高度: {move}')
                DeviceHelper.swipe_up_until(ctx.d, ctx.win_size_height, move)

        trans_list = self._distinct_list.data_list()
        return BotHelper.sort_trans_list(trans_list)

    def _reset_data(self):
        self._distinct_list.clear()
        self._item_date_year = None
        self._list_swipe_height = 0
        self._last_item_height = 0

    def _curr_list(self, ctx: ActivityExecuteContext) -> bool:
        d = ctx.d

        dump_source = self._dump_hierarchy(d)
        if d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/rl_webkit_root"]//android.webkit.WebView[not(*)]',
                   dump_source).exists:
            self._log(f'抓取不到内容节点，终止查询')
            return False

        x_trans_list = ctx.d.xpath('//*[@resource-id="cnt-wrapper"]/*[last()]/*', dump_source)
        if not x_trans_list.exists:
            raise BotParseError('未获取到流水列表')

        _, _, _, self._list_swipe_height = x_trans_list.get().rect
        x_items = x_trans_list.child('/*/*/*/*')
        if not x_items.exists:
            raise BotParseError('未获取到流水列表内容项')

        item_list = x_items.all()
        self._log(f'流水列表内容长度: {len(item_list)}')
        for _item in item_list:
            item_xpath = _item.get_xpath()
            _type, _item_data = self._parse_item_type(d, dump_source, item_xpath)
            if _type == 1:
                self._item_date_year = self._re_title_date_year.search(_item_data).group(1)
                self._log(f'流水日期标题: {_item_data} > {self._item_date_year}')
            elif _type == 2:
                item_key, item_detail = self._parse_detail(d, dump_source, _item)
                _, _, _, _item_height = _item.rect
                self._last_item_height = max(self._last_item_height, _item_height)
                self._log(f'流水明细: {item_detail}')
                if item_detail is not None:
                    if BotHelper.is_last_trans(item_detail, self._last_trans):
                        self._log(f'查询到最后一条流水，终止查询，流水 ({item_detail.time}, {item_detail.amount})')
                        return False
                    if self._distinct_list.contains_key(item_key) or self._distinct_list.contains_val(item_detail):
                        self._log(f'流水明细数据已存在数据，忽略: {item_detail.name}')
                    else:
                        self._distinct_list.append(item_key, item_detail)

                    if self._distinct_list.count() >= self._max_query_count:
                        self._log(f'符合查询流水条数限制，终止查询，条数: {self._distinct_list.count()}')
                        return False

        if d.xpath(f'//*{_xpath_desc_text("加载完成")}', dump_source).exists:
            self._log('检测到流水-加载完成')
            return False
        return len(item_list) > 0

    def _parse_item_type(self, d: u2.Device, source: str, parent_xpath: str) -> [int, str]:
        """列表项类型 1. 日期  2. 流水明细  3. 暂无数据  4. 忽略"""
        sub_items = d.xpath(parent_xpath, source).child('/*').all()
        if len(sub_items) == 1:
            sub_date_items = d.xpath(parent_xpath, source).child(f'//*{_xpath_desc_text("年", contains=True)}').all()
            date_title = _ele_desc_text(sub_date_items[0]) if sub_date_items else None
            if date_title and self._re_title_date_year.match(date_title):
                return 1, date_title
        return 2, None

    def _parse_detail(self, d: u2.Device, source: str, item_parent: u2.xpath.XMLElement) \
            -> [str, Optional[Transaction]]:
        """解析详情，兼容 收入、支出、利息"""

        item_nodes = d.xpath(item_parent.get_xpath(), source).child('/*').all()
        if len(item_nodes) < 4:
            return None, None

        title_date_nodes = d.xpath(item_nodes[0].get_xpath(), source).child('/*').all()
        if len(title_date_nodes) < 2:
            self._log('流水详情内容未找到标题和日期，忽略')
            return None, None
        txt_date = _ele_desc_text(title_date_nodes[1])
        title = _ele_desc_text(title_date_nodes[0]) + txt_date  # 标题(附言+转账时间)

        trans = Transaction(extension={})

        date_match = self._re_trans_date.search(txt_date)
        if date_match:
            date_str = f'{self._item_date_year}/{date_match.group(1)}/{date_match.group(2)} {date_match.group(3)}:{date_match.group(4)}:{date_match.group(5)}'
            trans.time = BotHelper.format_time(DateTimeHelper.to_datetime(date_str, '%Y/%m/%d %H:%M:%S'))

        x_amount = d.xpath(item_nodes[1].get_xpath(), source).child('/*[1]')
        if not x_amount.exists:  # 翻页后页面内容会混乱
            self._log(f'流水项找不到金额: {title}')
            return None, None
        amount = CMBCHelper.convert_amount(_ele_desc_text(x_amount))
        _item_key = f'{title}_{amount}'  # 标题(附言+转账时间)_金额

        detail_nodes = d.xpath(item_nodes[3].get_xpath(), source).child('/*').all()
        nodes_len = len(detail_nodes)
        if nodes_len < 8:
            return None, None
        had_postscript = False
        pass_next = 0
        for i in range(1, nodes_len):  # 第一项为空
            if pass_next > 0:
                pass_next -= 1
                continue

            _key = _ele_desc_text(detail_nodes[i]).replace(u'\xa0', '')  # 部分值有特殊符号
            _key_split = _ele_desc_text(detail_nodes[i + 1]) if (i + 1) < nodes_len else None
            _key_val = CMBCHelper.trim_none(_ele_desc_text(detail_nodes[i + 2]) if (i + 2) < nodes_len else None)
            if not _key:
                continue
            if _key_split != ':' and _key_split != '：':
                continue

            if StrHelper.contains('交易卡号', _key) or StrHelper.contains('收款行名', _key):
                pass
            elif StrHelper.contains('开户行', _key):
                trans.extension[_key] = _key_val
            elif StrHelper.contains('摘要', _key):
                had_postscript = True
                trans.postscript = _key_val
            elif StrHelper.contains('对方户名', _key):
                trans.name = _key_val
            elif StrHelper.contains('对方账户', _key):
                trans.customerAccount = _key_val.replace(' ', '')
            else:
                pass
            pass_next = 2

        trans.direction = 1 if amount > 0 else 0
        trans.amount = BotHelper.amount_fen(abs(amount))
        trans.balance = 0
        if not had_postscript:
            self._log(f'无读取到摘要，过滤此条记录 {title}')
            return None, None
        return _item_key, trans


class CMBCTransferIndexActivityExecutor(CMBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return CMBCActivityWebView.is_title(ctx.d, ctx.source, '转账') \
               and ctx.d.xpath(f'//*{_xpath_desc_text("银行卡转账")}', ctx.source).exists

    def go_next(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        ctx.d.sleep(0.5)
        if target_type == BotActivityType.Transfer:
            ctx.d.xpath(f'//*{_xpath_desc_text("银行卡转账")}').click_exists(1)
        if target_type == BotActivityType.QueryReceipt:
            ctx.d.xpath(f'//*{_xpath_desc_text("转账历史")}').click_exists(1)


class CMBCTransferActivityExecutor(CMBCActivityExecutorBase):
    _transferee: Transferee
    _sms_code_func: Callable

    def check(self, ctx: ActivityCheckContext):
        return CMBCActivityWebView.is_title(ctx.d, ctx.source, '转账汇款') \
               and ctx.d.xpath(f'//*{_xpath_desc_text("可用余额")}', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入转账页面')
        self._transferee, self._sms_code_func = BotActionParameter.get_transfer(**kwargs)
        d = ctx.d
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))

        name_xpath = '//*[@resource-id="cnt-wrapper"]/*[1]/*[3]/*[1]/*[1]/android.widget.EditText[1]'
        card_xpath = '//*[@resource-id="cnt-wrapper"]/*[1]/*[4]/*[1]/*[1]/android.widget.EditText[1]'
        bank_xpath = '//*[@resource-id="cnt-wrapper"]/*[1]/*[5]/*[1]/*[1]/android.widget.EditText[1]'
        amount_xpath = '//*[@resource-id="cnt-wrapper"]/*[3]/*[1]/*[1]'
        payer_card_xpath = f'//*{_xpath_desc_text("可用余额")}/preceding-sibling::*[1]/*[last()]'
        usable_amount_xpath = f'//*{_xpath_desc_text("可用余额")}/following-sibling::*[1]'
        postscript_xpath = f'//*{_xpath_desc_text("转账用途")}/following-sibling::*[1]/android.widget.EditText'

        self._log(f'输入收款人姓名')
        DeviceHelper.input_correct(ctx.d, name_xpath, self._transferee.holder,
                                   hierarchy_func=lambda **_kwargs: self._dump_hierarchy(ctx.d))
        self._log(f'输入收款人卡号')
        self._input_card_or_amount(d, card_xpath, self._transferee.account)

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

        acct_no = _ele_desc_text(ctx.d.xpath(payer_card_xpath))
        if not StrHelper.is_match_card_num(acct_no, ctx.account.account):
            msg = f'未匹配付款账户信息 {acct_no}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.Data, msg, is_stop=True)

        usable_amt = _ele_desc_text(d.xpath(usable_amount_xpath))
        usable_amt = CMBCHelper.convert_amount(usable_amt)
        trans_amount = self._transferee.amount_yuan()
        if usable_amt < trans_amount:
            msg = f'可用余额 {usable_amt} 小于转账余额 {trans_amount}'
            self._log(f'取消转账: {msg}')
            raise BotCategoryError(ErrorCategory.Data, msg)

        self._log(f'输入转账金额')
        while True:
            self._input_card_or_amount(d, amount_xpath, self._transferee.amount_yuan_str())
            x_payee_amt = ctx.d.xpath(amount_xpath, self._dump_hierarchy(ctx.d))
            payee_amt = CMBCHelper.convert_amount(_ele_desc_text(x_payee_amt))
            if payee_amt == trans_amount:
                self._log(f'转账金额输入正确: {payee_amt}')
                break
            else:
                self._log(f'转账金额输入不正确: {payee_amt}')

        self._exec_retry('等待金额加载完成', 60, lambda: self._wait_postscript(d, postscript_xpath))
        d.sleep(2)  # 等待金额键盘关闭、加载完成
        self._log(f'输入附言: {self._transferee.postscript}')
        x_payee_postscript = ctx.d.xpath(postscript_xpath)
        x_payee_postscript.set_text(self._transferee.postscript)

        self._log(f'点击转账')
        d.xpath(f'//android.widget.Button{_xpath_desc_text("转 账")}').click()

        self._log(f'检查是否发送短信验证码')
        kb_node = self._exec_retry('获取短信验证码键盘节点', 30, lambda: self._get_sms_kb_node(d, self._dump_hierarchy(d)))
        if kb_node is None:
            self._save_screenshot_transfer(d, '转账失败_未获取到短信键盘节点')
            DeviceHelper.press_back(d)
            raise BotErrorBase('未识别到输入短信验证码操作，疑似转账过程提示错误')

        self._log(f'等待短信验证码')
        sms_code = BotHelper.get_sms_code(sms_code_func=self._sms_code_func)
        d.sleep(6)  # 获取到验证码，等待顶部短信通知关闭
        self._log(f'输入短信验证码')
        self._input_sms_or_pwd(d, sms_code)
        d.sleep(3)
        self._log(f'输入交易密码')
        self._input_sms_or_pwd(d, ctx.account.payment_pwd)

        try:
            self._log(f'检查转账结果')
            self._exec_retry('检查转账结果', 60, lambda: self._transfer_result_check(d))
        except BotErrorBase as err:  # 识别到的转账失败异常
            self._log(f'检查转账结果失败: {err.msg}')
            return False, f'转账失败，{err.msg}'
        except Exception as ex:  # 未识别异常，乐观处理
            self._log(f'检查转账结果未知异常: {repr(ex)}')
            DeviceHelper.press_back(d)  # 回退，避免恶意操作
            if settings.debug:
                self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功_待确认')
            return True, '转账成功，需确认'
        return True, '转账成功'

    def _get_choose_bank(self, d: u2.Device, item_xpath: str):
        x_item = d.xpath(item_xpath)
        if x_item.exists and _ele_desc_text(x_item) and not StrHelper.contains('请选择', _ele_desc_text(x_item)):
            return _ele_desc_text(x_item)
        self._dump_hierarchy(d)  # 检查错误
        return False

    def _input_card_or_amount(self, d: u2.Device, item_xpath: str, text: str):
        d.xpath(item_xpath).click()
        d.sleep(1)
        try:
            kb_xpath = '//*[@resource-id="cn.com.cmbc.newmbank:id/top_panel"]/following-sibling::*[1]'
            amount_kb = CMBCAmountKeyboard(d, kb_xpath)
            DeviceHelper.input_clear(d, '//*[@resource-id="cn.com.cmbc.newmbank:id/digitalText"]',
                                     clear_func=lambda **_kwargs: amount_kb.delete(_kwargs['text']))

            [amount_kb.input(_char, 0.1) for _char in text]
        finally:
            d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/btn_confirm"]').click()

    @staticmethod
    def _wait_postscript(d: u2.Device, _xpath, _source: str = None):
        return d.xpath(_xpath, _source).exists

    def _get_sms_kb_node(self, d: u2.Device, _source=None):
        kb_node = self._find_keyboard_node(d, _source)
        return kb_node

    def _input_sms_or_pwd(self, d: u2.Device, pwd: str):
        if not pwd:
            raise BotCategoryError(ErrorCategory.Data, '交易密码 或 短信 不能为空')

        kb_node = self._get_sms_kb_node(d)
        if kb_node is None:
            raise BotParseError(f'未识别到密码键盘信息')

        self._log('开始输入 交易密码 或 短信验证码')
        pwd_kb = CMBCTransferPwdKeyboard(d, kb_node.get_xpath())
        [pwd_kb.input(_char, 0.01) for _char in pwd]
        self._log('结束输入 交易密码 或 短信验证码')

    def _transfer_result_check(self, d: u2.Device):
        """转账后返回上页处理"""

        _source = self._dump_hierarchy(d)
        if CMBCTransferResultActivityExecutor.is_current(d, _source):
            if settings.debug:
                self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账成功')
            CMBCTransferResultActivityExecutor.go_back_core(d)
            return True  # 跳转页面，表示成功

        x_state = d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/tv_process_state"]', _source)
        _loadings = ['转账受理成功', '正在处理', '请稍候']
        if x_state.exists and _ele_desc_text(x_state) \
                and not StrHelper.any_contains(_loadings, _ele_desc_text(x_state)):
            if settings.debug:
                self._save_screenshot_transfer(d, f'{self._transferee.holder}_转账失败')
            msg = _ele_desc_text(x_state)
            self._log(f'错误提示: {msg}')
            d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/tv_cancel"]').click_exists(2)
            if StrHelper.contains('交易密码', msg):
                raise BotCategoryError(ErrorCategory.BankWarning, msg, is_stop=True)
            raise BotCategoryError(ErrorCategory.BankWarning, msg)

        return False


class CMBCReceiptIndexActivityExecutor(CMBCActivityExecutorBase):
    _distinct_list = DistinctList()  # 去重列表
    _max_query_count: int
    _last_transferee: Transferee

    def check(self, ctx: ActivityCheckContext):
        return CMBCActivityWebView.is_eq_title(ctx.d, ctx.source, '转账历史') \
               and ctx.d.xpath('//*[@resource-id="cnt-wrapper"]', ctx.source).exists

    def execute(self, ctx: ActivityExecuteContext, *args, **kwargs):
        self._log('进入回单页面')
        self._reset_data()  # 每次重置当前列表
        self._last_transferee, self._max_query_count = BotActionParameter.get_query_receipt(**kwargs)

        d = ctx.d
        self._exec_retry('等待加载完成', 60, lambda: not self._is_loading(d))
        d.xpath('//*[@resource-id="cnt-wrapper"]/*[last()]/*[1]/*[1]/*').wait(30)

        self._curr_list(ctx)

        receipt_list = self._distinct_list.data_list()
        return BotHelper.sort_receipt_list(receipt_list)

    def _reset_data(self):
        self._distinct_list.clear()

    def _curr_list(self, ctx: ActivityExecuteContext):
        d = ctx.d

        if StrHelper.contains('暂无数据', _ele_desc_text(d.xpath('//*[@resource-id="cnt-wrapper"]/*[1]'))):
            return

        dump_source = self._dump_hierarchy(ctx.d)

        x_trans_list = ctx.d.xpath('//*[@resource-id="cnt-wrapper"]/*[last()]/*[1]/*[1]', dump_source)
        if not x_trans_list.exists:
            raise BotParseError('未获取到回单列表')

        x_items = x_trans_list.child('/*')
        if not x_items.exists:
            raise BotParseError('未获取到回单列表内容项')

        item_list = x_items.all()
        for _item in item_list:
            item_xpath = _item.get_xpath()
            _, _, _, self._last_item_height = _item.rect
            item_detail = self._get_detail(d, dump_source, item_xpath)
            self._log(f'回单明细: {item_detail}')
            if item_detail is not None:
                if self._distinct_list.contains_val(item_detail):
                    self._log(f'回单明细数据已存在数据，忽略: {item_detail.name}')
                else:
                    self._distinct_list.append(str(item_detail), item_detail)

                if BotHelper.is_transfer_receipt(item_detail, self._last_transferee):
                    self._log(f'查询到最后一条回单，终止查询，回单 ({item_detail.time}, {item_detail.amount})')
                    return False, False
                if self._distinct_list.count() >= self._max_query_count:
                    self._log(f'符合查询回单条数限制，终止查询，条数: {self._distinct_list.count()}')
                    return False, False
                d.sleep(0.5)  # 避免过快
        return True, True

    def _get_detail(self, d: u2.Device, source: str, item_parent_xpath: str):
        """解析详情，兼容 收入、支出、利息"""

        item_nodes = d.xpath(item_parent_xpath, source).child('/*').all()
        nodes_len = len(item_nodes)
        if nodes_len < 4:
            self._log('回单详情内容数量过小，忽略')
            return None

        receipt = Receipt()

        try:
            d.xpath(item_parent_xpath, source).click()
            receipt = self._parse_detail(d, receipt)
        finally:
            DeviceHelper.press_back(d)
        return receipt

    def _parse_detail(self, d: u2.Device, receipt: Receipt):
        """解析详情，兼容 卡号转账"""

        self._exec_retry('等待回单明细详情', 60, lambda **_kwargs: self._wait_receipt_detail(d))
        d.sleep(0.5)  # 避免过快

        source = self._dump_hierarchy(d)

        x_amount = d.xpath(f'//*{_xpath_desc_text("转账金额", contains=True)}/following-sibling::*[1]', source)
        x_time = d.xpath(f'//*{_xpath_desc_text("转账时间", contains=True)}/following-sibling::*[1]', source)
        x_type = d.xpath(f'//*{_xpath_desc_text("转账类型", contains=True)}/following-sibling::*[1]', source)
        x_purpose = d.xpath(f'//*{_xpath_desc_text("转账用途", contains=True)}/following-sibling::*[1]', source)
        x_payee_name = d.xpath(f'//*{_xpath_desc_text("收款方", contains=True)}/following-sibling::*[1]/*[2]/*[1]', source)
        x_payee_card = d.xpath(f'//*{_xpath_desc_text("收款方", contains=True)}/following-sibling::*[1]/*[3]', source)

        receipt.name = _ele_desc_text(x_payee_name)
        receipt.postscript = _ele_desc_text(x_purpose)
        receipt.amount = BotHelper.amount_fen(CMBCHelper.convert_amount(_ele_desc_text(x_amount)))
        receipt.customerAccount = CMBCHelper.get_card_no(_ele_desc_text(x_payee_card))
        receipt.time = BotHelper.format_time(DateTimeHelper.to_datetime(_ele_desc_text(x_time), '%Y-%m-%d %H:%M:%S'))
        receipt.inner = not StrHelper.contains('行外', _ele_desc_text(x_type))

        self._parse_receipt_image(d, source, receipt)
        return receipt

    def _parse_receipt_image(self, d: u2.Device, source, receipt: Receipt):

        try:
            d.xpath(f'//*{_xpath_desc_text("回单预览")}', source).click()
            self._exec_retry('等待回单图片', 60, lambda **_kwargs: self._wait_receipt_img(d))
            d.sleep(0.5)  # 避免过快
            receipt.content = DeviceHelper.screenshot_base64(d)
            receipt.need_image_format()

            if settings.debug:
                self._save_screenshot_receipt(d, receipt.time, receipt.name)
        finally:
            DeviceHelper.press_back(d)
            DeviceHelper.orientation_natural(d)  # 回单会变为横屏，需要强制回到竖屏

    def _wait_receipt_detail(self, d: u2.Device):
        dump_source = self._dump_hierarchy(d)
        return CMBCReceiptDetailActivityExecutor.is_current(d, dump_source)

    def _wait_receipt_img(self, d: u2.Device):
        dump_source = self._dump_hierarchy(d)
        return CMBCReceiptDetailImgActivityExecutor.is_current(d, dump_source)


class CMBCTransferResultActivityExecutor(CMBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    def go_back(self, ctx: ActivityExecuteContext, target_type: BotActivityType):
        self.go_back_core(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return CMBCActivityWebView.is_title(d, source, '转账结果') and d.xpath(f'//*{_xpath_desc_text("转账成功")}',
                                                                           source).exists

    @staticmethod
    def go_back_core(d: u2.Device, source=None):
        x_btn_right = d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/btn_right"]', source)
        if x_btn_right.exists:
            x_btn_right.click()
        else:
            DeviceHelper.press_back(d)


class CMBCReceiptDetailActivityExecutor(CMBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return (CMBCActivityWebView.is_eq_title(d, source, '转账历史明细详情')
                and d.xpath('//*[@resource-id="cnt-wrapper"]', source).exists)


class CMBCReceiptDetailImgActivityExecutor(CMBCActivityExecutorBase):

    def check(self, ctx: ActivityCheckContext):
        return self.is_current(ctx.d, ctx.source)

    @staticmethod
    def is_current(d: u2.Device, source=None):
        return (CMBCActivityWebView.is_eq_title(d, source, '电子回单')
                and (d.xpath('//*[@resource-id="cn.com.cmbc.newmbank:id/iv_receipt"]', source).exists
                     or d.xpath('//*[@resource-id="cnt-wrapper"]', source).exists))
