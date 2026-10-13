"""通过本机 AstrBot 内置接口发送一次文本通知。"""
import argparse
import base64
import hashlib
import hmac
import json
from pathlib import Path
import sys
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--message', required=True)
args = parser.parse_args()
if not args.message.strip():
    parser.error('Message must not be empty')

def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).rstrip(b'=')

try:
    # 手动填写技能目录中的 config.txt，内容使用 JSON 格式。
    config_path = Path(__file__).resolve().parents[1] / 'config.txt'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))['local']
    target = config.get('target', '').strip()
    if not target:
        sys.exit('Fill local.target in config.txt.')
    path = Path(config.get('astrbot_config', '').strip() or Path.home() / '.astrbot' / 'data' / 'cmd_config.json')
    dashboard = json.loads(path.read_text(encoding='utf-8-sig'))['dashboard']
    # 使用本机已有签名密钥生成 60 秒 JWT，不修改服务配置。
    unsigned = encode({'alg': 'HS256', 'typ': 'JWT'}) + b'.' + encode(
        {'username': dashboard['username'], 'exp': int(time.time()) + 60})
    signature = hmac.new(dashboard['jwt_secret'].encode(), unsigned, hashlib.sha256).digest()
    token = (unsigned + b'.' + base64.urlsafe_b64encode(signature).rstrip(b'=')).decode()
    request = urllib.request.Request(
        'http://127.0.0.1:%s/api/v1/im/messages' % int(dashboard.get('port', 6185)),
        data=json.dumps({'umo': target, 'message': args.message}).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    ok = result.get('status') == 'ok'
    print(json.dumps({'success': ok, 'status': result.get('status')}))
    sys.exit(0 if ok else 1)
except Exception as error:
    # 超时可能发生在已发送之后，不自动重试。
    sys.exit('Notification failed or uncertain (%s); do not automatically resend.' % type(error).__name__)
