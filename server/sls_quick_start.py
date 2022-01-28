import json
import os
import time

from aliyun.log import LogClient, PutLogsRequest, LogItem, GetLogsRequest, IndexConfig

from server.obj_factory import bot_util


third_party_api = {
    "accessKeyId": "",
    "accessKey": "",
    "SecretId": "",
    "SecretKey": ""
}

if os.path.exists('../config.json'):
    with open('../config.json', 'r') as conf:
        config = json.loads(conf.read())
        third_party_api['accessKeyId'] = config['accessKeyId']
        third_party_api['accessKey'] = config['accessKey']
        third_party_api['SecretId'] = config['SecretId']
        third_party_api['SecretKey'] = config['SecretKey']

accessKeyId = third_party_api['accessKeyId']
accessKey = third_party_api['accessKey']
endpoint = "cn-hongkong.log.aliyuncs.com"

client = LogClient(endpoint, accessKeyId, accessKey)

project_name = "mobile-robot"
logstore_name = "internal"
query = "*| select dev,id from " + logstore_name
logstore_index = {'line': {
    'token': [',', ' ', "'", '"', ';', '=', '(', ')', '[', ']', '{', '}', '?', '@', '&', '<', '>', '/', ':', '\n', '\t',
              '\r'], 'caseSensitive': False, 'chn': False}, 'keys': {'dev': {'type': 'text',
                                                                             'token': [',', ' ', "'", '"', ';', '=',
                                                                                       '(', ')', '[', ']', '{', '}',
                                                                                       '?', '@', '&', '<', '>', '/',
                                                                                       ':', '\n', '\t', '\r'],
                                                                             'caseSensitive': False, 'alias': '',
                                                                             'doc_value': True, 'chn': False},
                                                                     'id': {'type': 'long', 'alias': '',
                                                                            'doc_value': True}}, 'log_reduce': False,
    'max_text_len': 2048}

from_time = int(time.time()) - 3600
to_time = time.time() + 3600


def create_project():
    print("ready to create project %s" % project_name)
    client.create_project(project_name, project_des="")
    print("create project %s success " % project_name)
    time.sleep(60)


def create_logstore():
    print("ready to create logstore %s" % logstore_name)
    client.create_logstore(project_name, logstore_name, ttl=3, shard_count=2)
    print("create logstore %s success " % project_name)
    time.sleep(30)


def create_index():
    print("ready to create index for %s" % logstore_name)
    index_config = IndexConfig()
    index_config.from_json(logstore_index)
    client.create_index(project_name, logstore_name, index_config)
    print("create index for %s success " % logstore_name)
    time.sleep(60 * 2)


def put_logs(devices_id, log, level):
    print("ready to put logs for %s" % logstore_name)
    log_group = []
    log_item = LogItem()
    contents = [
        ('devices_id', devices_id),
        ('log', log),
        ('level', level)
    ]
    log_item.set_contents(contents)
    log_group.append(log_item)
    request = PutLogsRequest(project_name, logstore_name, "", "", log_group, compress=False)
    try:
        client.put_logs(request)
    except Exception as ext:
        if bot_util.cast_work is not None:
            bot_util.cast_work({"do_work": "stop"})
        print("日志连接问题: %s" % ext)
        print("日志系统连接不上-------> 无法启动卡机，强制stop")
    print("put logs for %s success " % logstore_name)


def get_logs():
    print("ready to query logs from logstore %s" % logstore_name)
    request = GetLogsRequest(project_name, logstore_name, from_time, to_time, query=query)
    response = client.get_logs(request)
    for log in response.get_logs():
        for k, v in log.contents.items():
            print("%s : %s" % (k, v))
        print("*********************")


if __name__ == '__main__':
    put_logs("7d19caab", "success put in")
