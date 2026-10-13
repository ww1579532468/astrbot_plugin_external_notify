"""向已配置的 Webhook 发送一次文本通知。"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--message', required=True)
args = parser.parse_args()
if not args.message.strip():
    parser.error('Message must not be empty')

try:
    # 手动填写技能目录中的 config.txt，内容使用 JSON 格式。
    config_path = Path(__file__).resolve().parents[1] / 'config.txt'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))['server']
    url = config.get('webhook_url', '').strip()
    token = config.get('webhook_token', '').strip()
    if not url:
        sys.exit('Fill server.webhook_url in config.txt.')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    # level=0 直接转发正文，接收目标使用服务端默认配置。
    request = urllib.request.Request(url,
        data=json.dumps({'message': args.message, 'level': 0, 'source': 'codex'}).encode('utf-8'),
        headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    ok = result.get('success') is True and result.get('notified') is True and result.get('status') in ('sent', 'fallback_sent')
    print(json.dumps({'success': ok, 'status': result.get('status')}))
    sys.exit(0 if ok else 1)
except Exception as error:
    # 超时可能发生在已发送之后，不自动重试。
    sys.exit('Notification failed or uncertain (%s); do not automatically resend.' % type(error).__name__)
