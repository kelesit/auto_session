"""
淘天
"""

import hmac
import socket
import requests
import time
import hashlib
import platform
from urllib.parse import quote
import redis
import json
import pendulum
from typing import Dict, List
from dataclasses import dataclass, field
import webbrowser

from ..utils.logger import get_logger

logger = get_logger(__name__)

# 淘天应用配置
## 主账号
TAOTIAN_APP_KEY = '501176'
TAOTIAN_APP_SECRET = '9evPt00JW5Z63WXUsjOYlKjPqhkGkBjX'
TAOTIAN_REDIRECT_URI = 'http://region-42.seetacloud.com:40555/post'
TAOTIAN_AUTH_ACCOUNT = '贝勤国际有限公司:chanpin01'
TAOTIAN_AUTH_PASSWORD = 'cp123456'

## 子账号
SUB_USER_ID_ACCOUNT_MAP = {
    2100007827016: '贝勤国际有限公司:gendan01',
    2100007344189: '贝勤国际有限公司:caigou01',
    2100007839018: '贝勤国际有限公司:caigou16',
    2100007824026: '贝勤国际有限公司:caigou15',
    2100007842071: '贝勤国际有限公司:caigou19',
    2100007833021: '贝勤国际有限公司:caigou13',
}

SUB_ACCOUNT = {
    '贝勤国际有限公司:caigou12': 'M48J7g2T',
    '贝勤国际有限公司:caigou01': 'OEWQLlFx',
    '贝勤国际有限公司:caigou16': 'zrg123456',
    '贝勤国际有限公司:gendan01': 'gd123456',
    '贝勤国际有限公司:caigou15': 'hhz123456',
    '贝勤国际有限公司:caigou19': 'OOrqABbR',
    '贝勤国际有限公司:caigou13':  'yyl123456'
}




P_SDK_VERSION = "iop-sdk-python-20181207"

P_APPKEY = "app_key"
P_ACCESS_TOKEN = "access_token"
P_TIMESTAMP = "timestamp"
P_SIGN = "sign"
P_SIGN_METHOD = "sign_method"
P_PARTNER_ID = "partner_id"
P_DEBUG = "debug"

P_CODE = 'code'
P_TYPE = 'type'
P_MESSAGE = 'message'
P_REQUEST_ID = 'request_id'

P_API_GATEWAY_URL_TW = 'https://api.taobao.tw/rest'
P_API_AUTHORIZATION_URL = 'https://auth.taobao.tw/rest'

P_LOG_LEVEL_DEBUG = "DEBUG"
P_LOG_LEVEL_INFO = "INFO"
P_LOG_LEVEL_ERROR = "ERROR"

def sign(secret,api, parameters):
    #===========================================================================
    # @param secret
    # @param parameters
    #===========================================================================
    sort_dict = sorted(parameters)
    
    parameters_str = "%s%s" % (api,
        str().join('%s%s' % (key, parameters[key]) for key in sort_dict))

    h = hmac.new(secret.encode(encoding="utf-8"), parameters_str.encode(encoding="utf-8"), digestmod=hashlib.sha256)

    return h.hexdigest().upper()

def mixStr(pstr):
    if(isinstance(pstr, str)):
        return pstr
    elif(isinstance(pstr, bytes)):
        return pstr.decode('utf-8')
    else:
        return str(pstr)

def logApiError(appkey, sdkVersion, requestUrl, code, message):
    localIp = socket.gethostbyname(socket.gethostname())
    platformType = platform.platform()
    logger.error("%s^_^%s^_^%s^_^%s^_^%s^_^%s^_^%s^_^%s" % (
        appkey, sdkVersion,
        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        localIp, platformType, requestUrl, code, message))



class IopRequest(object):
    def __init__(self,api_pame,http_method = 'POST'):
        self._api_params = {}
        self._file_params = {}
        self._api_pame = api_pame
        self._http_method = http_method

    def add_api_param(self,key,value):
        self._api_params[key] = value

    def add_file_param(self,key,value):
        self._file_params[key] = value

class IopResponse(object):
    def __init__(self):
        self.type = None
        self.code = None
        self.message = None
        self.request_id = None
        self.body = None
    
    def __str__(self, *args, **kwargs):
        sb = "type=" + mixStr(self.type) +\
            " code=" + mixStr(self.code) +\
            " message=" + mixStr(self.message) +\
            " requestId=" + mixStr(self.request_id)
        return sb

class IopClient(object):
    
    log_level = P_LOG_LEVEL_ERROR
    def __init__(self, server_url,app_key,app_secret,timeout=30):
        self._server_url = server_url
        self._app_key = app_key
        self._app_secret = app_secret
        self._timeout = timeout
    
    def execute(self, request,access_token = None):

        sys_parameters = {
            P_APPKEY: self._app_key,
            P_SIGN_METHOD: "sha256",
            P_TIMESTAMP: str(int(round(time.time()))) + '000',
            P_PARTNER_ID: P_SDK_VERSION
        }

        if(self.log_level == P_LOG_LEVEL_DEBUG):
            sys_parameters[P_DEBUG] = 'true'

        if(access_token):
            sys_parameters[P_ACCESS_TOKEN] = access_token

        application_parameter = request._api_params;

        sign_parameter = sys_parameters.copy()
        sign_parameter.update(application_parameter)

        sign_parameter[P_SIGN] = sign(self._app_secret,request._api_pame,sign_parameter)

        api_url = "%s%s" % (self._server_url,request._api_pame)

        full_url = api_url + "?";
        for key in sign_parameter:
            full_url += key + "=" + str(sign_parameter[key]) + "&";
        full_url = full_url[0:-1]

        try:
            if(request._http_method == 'POST' or len(request._file_params) != 0) :
                r = requests.post(api_url,sign_parameter,files=request._file_params, timeout=self._timeout)
            else:
                r = requests.get(api_url,sign_parameter, timeout=self._timeout)
        except Exception as err:
            logApiError(self._app_key, P_SDK_VERSION, full_url, "HTTP_ERROR", str(err))
            raise err

        response = IopResponse()

        jsonobj = r.json()

        if P_CODE in jsonobj:
            response.code = jsonobj[P_CODE]
        if P_TYPE in jsonobj:
            response.type = jsonobj[P_TYPE]
        if P_MESSAGE in jsonobj:
            response.message = jsonobj[P_MESSAGE]
        if P_REQUEST_ID in jsonobj:
            response.request_id = jsonobj[P_REQUEST_ID]

        if response.code is not None and response.code != "0":
            logApiError(self._app_key, P_SDK_VERSION, full_url, response.code, response.message)
        else:
            if(self.log_level == P_LOG_LEVEL_DEBUG or self.log_level == P_LOG_LEVEL_INFO):
                logApiError(self._app_key, P_SDK_VERSION, full_url, "", "")

        response.body = jsonobj

        return response
    

def escape_special_characters(url):
    return quote(url, safe=':/?&=')  # 允许保留 :/?&= 这些符号




def twtoken():
    """
先获取ACCESS token
如果ACCESS TOKEN存在且过期时间没到，则不管他，如果到了则重新获取一次，考虑刷新机制
    """
    import webbrowser
    appkey = '501176'
    appSecret =  '9evPt00JW5Z63WXUsjOYlKjPqhkGkBjX'
    reget_token = 0
    url = 'https://api.taobao.global/rest'
    client = IopClient(url, appkey ,appSecret)
    r = redis.StrictRedis(host='192.168.100.44', port=7379, db=11,password="123456")
    tokenbody = r.hgetall('twtoken')
    if tokenbody:
        data = {k.decode('utf-8'): v.decode('utf-8') for k, v in tokenbody.items()}

        # data['expire_date'] = "2024-05-25"
        if pendulum.parse(data['expire_date']) >= pendulum.now():
            return data["access_token"]

        elif pendulum.parse(data['refresh_expire_date']) >= pendulum.now():
            url = 'https://api.taobao.global/rest'

            request = IopRequest('/auth/token/refresh')
            request.add_api_param('refresh_token', data['refresh_token'])
            response = client.execute(request)
            for key in response.body:
                if key in data:
                    data[key] = response.body[key]
            return data['access_token']
        else:
            reget_token = 1

    if reget_token == 1 or not tokenbody:
        """
        重新授权
        """
        redirect_uri = 'http://region-42.seetacloud.com:40555/post'
        original_url = f'https://api.taobao.global/oauth/authorize?response_type=code&redirect_uri={redirect_uri}&force_auth=true&client_id={appkey}'
        formatted_url = escape_special_characters(original_url)
        webbrowser.open_new(formatted_url)
        webbrowser.open_new_tab(formatted_url)
        print("账号: 贝勤国际有限公司:chanpin01\r\n密码: cp123456")
        code = input("输入获得的code:")

        request = IopRequest('/auth/token/create')
        request.add_api_param('code', code)
        response = client.execute(request)
        data = response.body
        data['expire_date']=pendulum.now().add(seconds=int(data['expires_in'])).strftime("%Y-%m-%d")
        data['refresh_expire_date']=pendulum.now().add(seconds=int(data['refresh_expires_in'])).strftime("%Y-%m-%d")
        r.hmset('twtoken',data)
        return data['access_token']
    
def get_twtoken(account):
    """
    获取子账号的ACCESS TOKEN
    先获取ACCESS token
    如果ACCESS TOKEN存在且过期时间没到，则不管他，如果到了则重新获取一次，考虑刷新机制
    """
    appkey = '501176'
    appSecret =  '9evPt00JW5Z63WXUsjOYlKjPqhkGkBjX'
    reget_token = 0
    url = 'https://api.taobao.global/rest'
    client = IopClient(url, appkey ,appSecret)
    r = redis.StrictRedis(host='192.168.100.44', port=7379, db=11,password="123456")
    tokenbody = r.hgetall(f'twtoken_{account}')
    if tokenbody:
        data = {k.decode('utf-8'): v.decode('utf-8') for k, v in tokenbody.items()}

        # data['expire_date'] = "2024-05-25"
        if pendulum.parse(data['expire_date']) >= pendulum.now():
            return data["access_token"]

        elif pendulum.parse(data['refresh_expire_date']) >= pendulum.now():
            url = 'https://api.taobao.global/rest'

            request = IopRequest('/auth/token/refresh')
            request.add_api_param('refresh_token', data['refresh_token'])
            response = client.execute(request)
            for key in response.body:
                if key in data:
                    data[key] = response.body[key]
            return data['access_token']
        else:
            reget_token = 1
    if reget_token == 1 or not tokenbody:
        """
        报错 终止程序运行
        """
        raise Exception(f"账号 {account} twtoken获取失败，请检查子账号是否正确，或重新授权")



def get_order_info_tw(outer_purchase_id=None):
    
        appkey = '501176'
        appSecret =  '9evPt00JW5Z63WXUsjOYlKjPqhkGkBjX'
        url = 'https://api.taobao.global/rest'
        client = IopClient(url, appkey ,appSecret)
        access_token = twtoken()
        if not access_token:
            raise Exception("获取ACCESS TOKEN失败")
        request = IopRequest('/purchase/orders/query')
        request.add_api_param('status', 'WAIT_BUYER_P')
        request.add_api_param('sort_type', 'ASC')
        request.add_api_param('page_no', '1')
        request.add_api_param('sort_field', 'modify_time')
        request.add_api_param('page_size', '10')
        request.add_api_param('outer_purchase_id', f'{outer_purchase_id}')
        response = client.execute(request, access_token)
        resp = response.body
        if not resp.get('success'):
            return {'msg': '获取订单信息失败', 'data': None, 'success': False}
        
        return {'msg': '获取订单信息成功', 'data': resp.get('data'), 'success': True}

def get_send_url_tw(bizId, sub_user_id):
    """
    获取发送URL
    Return:
        dict: 包含发送URL和状态信息的字典
        {
            'msg': '获取发送URL成功',
            'url': 'https://example.com/send_url',
            'success': True
        }
    """
    account = SUB_USER_ID_ACCOUNT_MAP.get(sub_user_id, None)
    if not account:
        raise Exception(f"未找到子账号对应的账号: {sub_user_id}")
    account_psw = SUB_ACCOUNT.get(account, None)
    if not account_psw:
        raise Exception(f"未找到账号密码: {account}")

    appkey = '501176'
    appSecret =  '9evPt00JW5Z63WXUsjOYlKjPqhkGkBjX'
    url = 'https://api.taobao.global/rest'
    client = IopClient(url, appkey ,appSecret)
    account_id = account.split(':')[1]  # 只取账号部分
    access_token = get_twtoken(account_id)
    request = IopRequest('/page/link/get')
    request.add_api_param('loginName', f'{account}')
    request.add_api_param('password', f'{account_psw}')
    request.add_api_param('pageName', 'imDialog')
    pageParamMap  = {"sourceType":"order","bizId": f"{bizId}"}
    request.add_api_param('pageParamMap', str(pageParamMap))

    response = client.execute(request, access_token)
    
    if not response.body.get('success'):
        errorMsg = response.body.get('errorMsg').split('=')[-1] if response.body.get('errorMsg') else '未知错误'
        return {'msg': f"获取发送URL失败: {errorMsg}", 'url': None, 'success': False}

    return {'msg': '获取发送URL成功', 'url':response.body.get('data', None), 'success': True}



def test_get_send_info():
    try:
        # order_info_tw_resp = get_order_info_tw('501566-191054229361801147') # gandan01
        order_info_tw_resp = get_order_info_tw('501566-191056129362104191')
        if not order_info_tw_resp.get('success'):
            print(f"❌ 获取订单信息失败: {order_info_tw_resp.get('message', '未知错误')}")

        order_info = order_info_tw_resp['data']
        bizId = order_info["purchase_orders"][0]["sub_purchase_orders"][0]["sub_purchase_order_id"]
        sub_user_id = order_info['purchase_orders'][0]['sub_user_id']
        
        send_url_tw_resp = get_send_url_tw(bizId, sub_user_id)
        if not send_url_tw_resp.get('success'):
            print(f"❌ 获取发送URL失败: {send_url_tw_resp.get('msg', '未知错误')}, bizId: {bizId}, sub_user_id: {sub_user_id}")

        send_url = send_url_tw_resp.get('url')

        print(f"✅ 发送URL: {send_url}")
        
    except Exception as e:
        print(f"Error: {e}")

def update_twtoken():
    """手动运行脚本，更新淘天token"""
    r = redis.StrictRedis(host='192.168.100.44', port=7379, db=11,password="123456")
    appkey = '501176'
    appSecret = '9evPt00JW5Z63WXUsjOYlKjPqhkGkBjX'
    url = 'https://api.taobao.global/rest'
    client = IopClient(url, appkey, appSecret)

    for full_account in SUB_ACCOUNT.keys():
        account = full_account.split(':')[1]  # 只取账号部分
        try:
            twtoken = get_twtoken(account)
            print(f"✅ 账号 {account} token有效，跳过")
            if twtoken:
                continue
        except Exception as e:
            print(f'{account}的token获取失败: {e}')
            # 开始进行手动更新授权
            print(f"开始为账号 {account} 进行手动授权...")

            redirect_uri = 'http://region-42.seetacloud.com:40555/post'
            original_url = f'https://api.taobao.global/oauth/authorize?response_type=code&redirect_uri={redirect_uri}&force_auth=true&client_id={appkey}'
            formatted_url = escape_special_characters(original_url)
            print(f"账号: {full_account}")
            print(f"密码: {SUB_ACCOUNT[full_account]}")

            webbrowser.open_new(formatted_url)
            webbrowser.open_new_tab(formatted_url)


            code = input("输入获得的code:")
            if not code.strip():
                print(f"❌ 未输入code，跳过账号 {account}")
                continue

            try:
                request = IopRequest('/auth/token/create')
                request.add_api_param('code', code)
                response = client.execute(request)

                if response.body:
                    data = response.body
                    data['expire_date']=pendulum.now().add(seconds=int(data['expires_in'])).strftime("%Y-%m-%d")
                    data['refresh_expire_date']=pendulum.now().add(seconds=int(data['refresh_expires_in'])).strftime("%Y-%m-%d")
            
                    r.hmset(f'twtoken_{account}',data)
                    print(f"✅ 账号 {account} 的token更新成功")
                else:
                    print(f"❌ 账号 {account} 的token更新失败")
            except Exception as e:
                print(f"❌ 账号 {account} 的token更新过程中发生错误: {e}")





if __name__ == "__main__":
    test_get_send_info()

    # update_twtoken()