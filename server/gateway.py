# coding: utf-8
import sys
from builtins import ConnectionRefusedError

import uiautomator2 as u2
from flask import Flask, request

# 添加上级目录，用于查找 server 包
sys.path.append('..')

from server import settings, api
from server.update import update_init
from server.settings import gateway, log
from server.obj_factory import bot_util
from server.bot_factory import BotFactory

app = Flask(__name__)
global rsp

"""
测试接口
params：none
"""


@app.route('/', methods=['GET'])
def hello():
    settings.ip()
    return "hello world"


"""
检查安装环境
params：none
"""


@app.route('/check_evn', methods=['GET'])
def check():
    global rsp
    try:
        settings.ip()
        ready = len(dir(u2)) > 100
        rsp = ready and {'code': 0, 'msg': '环境安装成功！'} or {'code': 1, 'msg': '环境安装失败，请重装！'}
        log('/check_env rsp: %s' % rsp)
    except ConnectionRefusedError:
        rsp = {'code': 2, 'msg': 'atx未启动，请先插上usb线，运行电脑脚本！'}
        log(rsp, settings.Level.SYSTEM)
    except Exception as ext:
        rsp = {'code': 1, 'msg': ext}
        log(rsp, settings.Level.SYSTEM)
    return rsp


"""
短信上报完成付款接口
params：sms
"""


@app.route('/sms', methods=['POST'])
def sms():
    global rsp
    if request.is_json:
        settings.ip()
        try:
            params = request.get_json()
            print('/sms req: %s' % params)
            if not settings.last_sms == "" and settings.last_sms == params['sms']:
                ext = {'code': 1, 'msg': '短信已经接收，不接收重复短信'}
                print('/sms rsp: %s' % ext)
                return ext
            try:
                settings.last_sms = params['sms']
                if bot_util.cast_sms is not None:
                    rsp = bot_util.cast_sms(params)
                    rsp = rsp is not None and rsp or {'code': 1, 'msg': '服务器未响应，请稍后再试!'}
                    rsp = {'code': 0, 'msg': rsp}
                    print('/sms rsp: %s ' % rsp)
                    return rsp
                else:
                    ext = {'code': 1, 'msg': '需要先启动卡机'}
                    print('/sms rsp: %s 需要先启动卡机' % ext)
                    return ext
            except Exception as ext:
                ext = {'code': 1, 'msg': repr(ext)}
                print('/sms rsp: %s 需要先启动卡机' % repr(ext))
                return ext
        except ConnectionRefusedError:
            ext = {'code': 1, 'msg': '服务未开启，请重新运行激活程序！'}
            log(ext, settings.Level.SYSTEM)
            return ext


"""
启动前置检查及信息获取
params：
baseURL 接口前缀
serialNo 手机序列号
kind 支付种类 
bank 银行
account_alias 银行别名
devices_id 阿里控制ID
"""


@app.route('/start', methods=['POST'])
def start():
    global rsp
    if request.is_json:
        settings.ip()
        try:
            params = request.get_json()
            log('/start req: %s' % params)
            settings.api['base'] = params['baseURL']
            settings.start_kind = params['kind']
            if hasattr(settings.rename_bank, params['bank']):
                params['bank'] = settings.rename_bank[params['bank']]
            if params['kind'] == 0:
                if not params['bank'] in settings.receive_bank:
                    res = {"code": 1, 'msg': '收款暂时未支持您所启动的银行，请耐心等待开发！'}
                    log("check_bank: %s" % res)
                    return {"code": 1, 'msg': res}
            else:
                if not params['bank'] in settings.payment_bank:
                    res = {"code": 1, 'msg': '付款暂时未支持您所启动的银行，请耐心等待开发！'}
                    log("check_bank: %s" % res)
                    return res
            log("check_bank: is supported")
            # 假数据
            # data = {
            #     "accountAlias": "中国银行-BOC(徐秀策)-4249）",
            #     "loginName": "18648890160",
            #     "loginPassword": "aa080706",
            #     "paymentPassword": "080706",
            #     "ukeyPassword": "080706",
            #     "bank": "BOC"
            # }
            # data_obj = convert(data=data)

            bot_factory = BotFactory()
            bot_util.cast_transaction = bot_factory.cast_transaction
            bot_util.cast_start = bot_factory.cast_start
            bot_util.cast_sms = bot_factory.cast_sms
            bot_util.make_bot = bot_factory.make_bot
            bot_util.cast_work = bot_factory.cast_work
            rsp = bot_util.cast_start(params)
            if rsp['code'] == 0 and rsp['data'] is not None:
                rsp['data']['kind'] = params['kind']
                rsp['data']['devicesId'] = settings.serial_no
                log("rsp['data']: %s" % rsp)
                return {'code': 0, 'msg': '启动成功', 'data': rsp['data']}
            else:
                return {'code': 1, 'msg': rsp['msg'], 'data': rsp['data']}
        except ConnectionRefusedError:
            rsp = {'code': 1, 'msg': '服务未开启，请重新运行激活程序！'}
            log(rsp, settings.Level.SYSTEM)
        except Exception as ext:
            rsp = {'code': 1, 'msg': repr(ext)}
            log(rsp, settings.Level.SYSTEM)
            return rsp
        return {'code': 0, 'msg': '启动成功', 'data': rsp}


"""
执行指定工作
params：
do_work: start 启动和操控App
do_work: stop 关闭所有卡机应用
"""


@app.route('/do_work', methods=['POST'])
def do_work():
    global rsp
    if request.is_json:
        settings.ip()
        try:
            if bot_util.cast_work is None or settings.bot is None or settings.bot.account is None:
                return {'code': 1, 'msg': '请先启动卡机！'}

            params = request.get_json()
            log('/do_work req: %s' % params)
            _work = params['do_work']
            if _work == 'stop':
                if params['extension'] is not None and params['extension'] != '':
                    settings.api['base'] = params['extension']
                api.status(params['account_alias'], settings.Status.PAUSE)
            elif _work == 'start':
                api.status(settings.bot.account.alias, settings.Status.RUNNING)

            bot_util.cast_work(params)
            rsp = {'code': 0, 'msg': '正在执行任务！'}
            log("do_work: %s" % params)
        except ConnectionRefusedError:
            rsp = {'code': 1, 'msg': '服务器异常，无法执行任务！'}
            log("{'code': 1, 'msg': '服务器异常，无法执行任务！'}", settings.Level.SYSTEM)
        except Exception as ext:
            rsp = {'code': 1, 'msg': repr(ext)}
            log(rsp, settings.Level.SYSTEM)
        return rsp


if __name__ == '__main__':
    update_init()
    app.run(host=gateway['host'], port=gateway['port'])
