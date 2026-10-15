"""向已配置的 Webhook 发送一次文本通知。"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--message', required=True)
parser.add_argument('--level', type=int, choices=range(4), default=0,
                    help='0: forward; 1: AI; 2: AI with fallback; 3: main conversation')
parser.add_argument('--target', default='', help='Override the server default conversation')
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
    # 默认直接转发；可指定处理等级和目标会话。
    payload = {'message': args.message, 'level': args.level, 'source': 'codex'}
    if args.target.strip():
        payload['target'] = args.target.strip()
    request = urllib.request.Request(url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    status = result.get('status')
    ok = result.get('success') is True and (
        (result.get('notified') is True and status in ('sent', 'fallback_sent'))
        or (args.level in (1, 2) and status == 'ignored')
        or (args.level == 3 and status == 'accepted'))
    print(json.dumps({'success': ok, 'status': status, 'notified': result.get('notified')}))
    sys.exit(0 if ok else 1)
except Exception as error:
    # 超时可能发生在已发送之后，不自动重试。
    sys.exit('Notification failed or uncertain (%s); do not automatically resend.' % type(error).__name__)
