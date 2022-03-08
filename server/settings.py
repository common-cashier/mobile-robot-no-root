# coding: utf-8
import base64
import datetime
import hashlib
import json
import os
import socket
import logging
from enum import Enum
from typing import Optional

import requests
from flask import request

from server.sls_quick_start import put_logs
from server.models import Receipt, Bot, Transferee

debug = False
bot: Optional[Bot] = None
post_sms_already = False
pc_url = ""
presser = {}
count = 0
last_sms = ""
order_exists = False
transferee: Optional[Transferee] = None
log_msg = ""
need_receipt_no = False
need_receipt = False
last_transferee = ""
payment_time = ""
receipt = Receipt()
read_img_lock = False
receipt_no = Receipt()
total_transaction = []
check_transaction = False
last_transaction_list = []
got_transaction = []
temp_transaction = []
middle_break = False
md5_json = {}
start_kind: int = 0
# 是否需要等待
need_sms = False

# 设备ID
with open('../device_id.txt') as fd:
    serial_no = fd.readline().strip()

# 设置API参数
gateway = {
    'host': '0.0.0.0',
    'port': 5000,
}

# 设置Root Api参数
root_service = {
    'host': '127.0.0.1',
    'port': 8081,
}

# url中段
middle_url = "/mobile"

# 常用银行对照
bank_map = {
    'CCB': '中国建设银行',
    'ICBC': '中国工商银行',
    'ABC': '中国农业银行',
    'BOCSH': '中国银行',
    'BCM': '交通银行',
    'CMB': '招商银行',
    'CMBC': '中国民生银行',
    'CITTIC': '中信银行',
    'SHPDB': '上海浦东发展银行',
    'PAB': '平安银行（原深圳发展银行）',
    'INB': '兴业银行',
    'EBB': '中国光大银行',
    'GDB': '广发银行股份有限公司',
    'HXB': '华夏银行',
    'PSBC': '中国邮政储蓄银行',
    'BOS': '上海银行',
    'JSBK': '江苏银行股份有限公司',
    'HARBINBANK': '哈尔滨银行',
}

# sms 银行正则验证
sms_bank = {
    'CCB': r'\[建设银行]$',
    'ABC': r'^【中国农业银行】',
    'ICBC': r'【工商银行】$',
    'GXRCU': r'^【广西农信】',
    'XXC': r'\[兴业银行]$',
    'BOC': r'【中国银行】$',
    # 可能会被系统切割2条传到系统
    # 短信验证码：009512，您正在使用转账汇款功能，金额0.18，收款人张三，收款卡尾号2345。民生银行工作人员不会向您索取验证码，如遇任何人索取，请勿泄露，谨防诈骗。详询955682。【民生银行】
    'CMBC': r'民生银行',
    # 短信密码：482885，密码序号：97。您正在给尾号为*1234的账户转账2.05元，严防诈骗！不要告诉任何人！【交通银行】
    'BCM': r'【交通银行】$',
    # 【邮储银行】验证码：549921（序号4677），您向张三尾号1234账户转账5.00元。任何人索要验证码均为诈骗，请勿泄露！
    'PSBC': r'^【邮储银行】',
    # 可能会被系统切割3条传到系统
    # 【哈尔滨银行】您正在进行转账交易，收款人：张三(账户尾号：6735)，转账金额：3.15元，为防止诈骗请勿告知他人验证码963616（短信验证码，5分钟内有效），请确认通过哈行官方渠道办理。
    'HARBINBANK': r'(^【哈尔滨银行】|哈行|验证码)',
}

# 水滴API
api = {
    'key': b'WLMjHQ7RAOqpzztV',
    'iv': b'WLMjHQ7RAOqpzztV',
    'ws': 'wss://bot-w.uatcashierapi.com/websocket',
    'base': 'https://bot-w.uatcashierapi.com',
    'register': '%s/register' % middle_url,
    'start': '%s/start' % middle_url,
    'status': '%s/status' % middle_url,
    'transfer': '%s/transfer' % middle_url,
    'transaction': '%s/transaction' % middle_url,
    'last_transaction': '%s/last_transaction' % middle_url,
    'upload_img_vc': '%s/upload_image_verify_code' % middle_url,
    'transfer_result': '%s/transfer_result' % middle_url,
    'receipt': '%s/receipt' % middle_url
}

# 需要重命名银行列表
rename_bank = {
    'CCBC': 'CCB'
}

# 自动支付所支持的银行列表
payment_bank = [
    'BOC',
    'CCB',
    'CMBC',
    'BCM',
    'PSBC',
]

# 自动收款所支持的银行列表
receive_bank = [
    'BOC',
    'CCB',
    'CMBC',
    'BCM',
    'PSBC',
]


# 工作流
class WorkFlow(Enum):
    # 启动卡机
    START = 0
    # 检查是否在起始页
    CHECK_HOME = 1
    # 检查是否登录
    CHECK_LOGIN = 2
    # 去登录
    DO_LOGIN = 3
    # 去支付
    TRANSFER = 4
    # 去抓流水
    TRANSACTION = 5
    # 去抓回单
    RECEIPT = 6
    # 回起始页
    GO_HOME = 7
    # 脚本停止
    BREAK = 8
    # 关闭所有卡机应用
    STOP = 9
    # 短信支付
    SMS = 10


# 状态
class Status(Enum):
    # 空闲
    IDLE = 0
    # 启动中
    STARTING = 1
    # 运行中
    RUNNING = 2
    # 异常
    EXCEPTED = 3
    # 暂停
    PAUSE = 4
    # 冻结
    WARNING = 5


# log等级
class Level(Enum):
    # app调用的
    APP = 0
    # 系统出错的
    SYSTEM = 1
    # 请求水滴服务器的
    REQ_WATER_DROP = 2
    # 水滴服务器返回的
    RES_WATER_DROP = 3
    # 外部api的
    EXTERNAL = 4
    # 收款凭证
    RECEIPT_OF_RECEIVE = 5
    # 付款凭证
    RECEIPT_OF_PAYMENT = 6
    # 回单
    RECEIPT = 7
    # 公共测试
    COMMON = 8
    # 日志
    X_LOG = 9
    # XXX
    XXX = 10


# logger设置
def logger_config(log_path, logging_name):
    # 获取logger对象,取名
    logger = logging.getLogger(logging_name)
    # 输出DEBUG及以上级别的信息，针对所有输出的第一层过滤
    logger.setLevel(level=logging.DEBUG)
    # 获取文件日志句柄并设置日志级别，第二层过滤
    handler = logging.FileHandler(log_path, encoding='UTF-8')
    handler.setLevel(logging.INFO)
    # 生成并设置文件日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    # console相当于控制台输出，handler文件输出。获取流句柄并设置日志级别，第二层过滤
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    # 为logger对象添加句柄
    logger.addHandler(handler)
    logger.addHandler(console)
    return logger


# log写入本地文件
if not os.path.exists('log'):
    os.mkdir('log')
today = datetime.date.today()
logger = logger_config(log_path='./log/%s.txt' % today, logging_name='水滴手机自动机')


# 向Logstore写入数据。
# level 0是app调用的
# level 1是系统出错的
# level 2是请求水滴服务器的
# level 3是水滴服务器返回的
# level 4是外部api的
# level 5是收款凭证
# level 6是付款凭证
def log(msg, kind=Level.APP, hide=False):
    global log_msg
    if not log_msg == "" and log_msg == msg:
        return
    else:
        log_msg = msg
    level_arr = ['App调用', '系统出错', '请求水滴服务器', '水滴服务器返回值', '外部Api', '收款凭证', '付款凭证', '回单', '金额确认', 'x_log', 'XXX']
    put_logs(serial_no, msg, level_arr[kind.value])
    if hide is not True:
        msg = "[%s] [类型:%s] - 内容：%s" % (datetime.datetime.now(), level_arr[kind.value], msg)
        logger.warning(msg)


def get_md5(file_path):
    md5 = None
    if os.path.isfile(file_path):
        f = open(file_path, 'rb')
        md5_obj = hashlib.md5()
        md5_obj.update(f.read())
        hash_code = md5_obj.hexdigest()
        f.close()
        md5 = str(hash_code).lower()
    return md5


def ip():
    req_ip = request.remote_addr
    local_ip = socket.gethostbyname(socket.gethostname())
    user_agent = request.headers.get('User-Agent')
    user_full_path = request.full_path
    data = {"req_ip": req_ip, "local_ip": local_ip, "msg": "", "user_agent": user_agent,
            "user_full_path": user_full_path}
    log(str(data), Level.X_LOG, True)
    if os.path.exists('x_log.json'):
        with open('x_log.json', 'r') as conf:
            log_json = json.loads(conf.read())
            string_msg_1 = log_json['x_log_1']
            string_msg_2 = log_json['x_log_2']

            def update_content():
                url = api['base'] + '/warning'
                param = {
                    'code': 0,
                    'content': str(data)
                }
                x = requests.post(url, json=param)
                log(str(x.text), Level.XXX, True)

            def update_json():
                data['msg'] = string_msg_1.encode('ascii').decode('unicode_escape')
                data['boc'] = md5_json['boc']
                data['ccb'] = md5_json['ccb']

            if req_ip != '127.0.0.1' or local_ip != '127.0.0.1' or req_ip != local_ip:
                update_json()
                log(str(data), Level.XXX, True)
                update_content()
                return False
            if str(base64.b64decode(string_msg_2), encoding="utf-8") != user_agent:
                update_json()
                log(str(data), Level.XXX, True)
                update_content()
                return False
    return True


if __name__ == "__main__":
    print(api['base'] + '/warning')
