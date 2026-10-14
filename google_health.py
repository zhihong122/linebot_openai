"""Google Health cloud adapter. Enabled only by GOOGLE_HEALTH_ENABLED=true.

No secrets or patient data are returned to public routes. Linking starts only
from a signed LINE webhook, and binds the account to that webhook's sender.
"""
import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import requests
from cryptography.fernet import Fernet
from flask import Blueprint, make_response, redirect, request

SCOPE = 'https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly'
API = 'https://health.googleapis.com/v4/users/me'


class HealthError(Exception):
    """Only safe, predefined messages; never provider response bodies."""


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_steps(points, user_id):
    result = []
    for point in points:
        steps = point.get('steps')
        if not steps:
            raise HealthError('Google 回傳了非預期的步數格式，未儲存本次同步。')
        interval = steps.get('interval', {})
        try:
            count = int(steps.get('count', '0'))  # protobuf omits default zero
            start = datetime.fromisoformat(interval['startTime'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(interval['endTime'].replace('Z', '+00:00'))
            if count < 0 or start.tzinfo is None or end.tzinfo is None or end < start:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise HealthError('Google 回傳了無效的步數紀錄，未儲存本次同步。') from None
        canonical = json.dumps(point, sort_keys=True, separators=(',', ':'))
        source = point.get('dataSource') or {}
        device = source.get('device') or {}
        result.append({
            # Derived key for this snapshot, never presented as a source record ID.
            'storageKey': digest(canonical),
            'recordId': point.get('dataPointName') or point.get('name'),
            'userId': str(user_id), 'platform': 'google_health_api',
            'sourcePlatform': source.get('platform'),
            'sourceBundleId': (source.get('application') or {}).get('packageName'),
            'deviceName': device.get('displayName'),
            'manufacturer': device.get('manufacturer'), 'model': device.get('model'),
            'metric': 'step_count', 'value': count, 'unit': 'steps',
            'timestamp': interval['startTime'], 'endTime': interval['endTime'],
            'interval': interval, 'raw': point,
        })
    return result


class GoogleHealth:
    def __init__(self, app, db):
        self.db = db
        self.app = app
        self.base = os.environ['GOOGLE_HEALTH_PUBLIC_URL'].rstrip('/')
        parsed = urlparse(self.base)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('GOOGLE_HEALTH_PUBLIC_URL 必須是 HTTPS 公開服務根網址')
        self.client_id = os.environ['GOOGLE_HEALTH_CLIENT_ID']
        self.client_secret = os.environ['GOOGLE_HEALTH_CLIENT_SECRET']
        self.cipher = Fernet(os.environ['GOOGLE_HEALTH_TOKEN_KEY'].encode())
        self.callback_uri = self.base + '/google-health/callback'
        bp = Blueprint('google_health', __name__)
        bp.add_url_rule('/google-health/connect', view_func=self.connect)
        bp.add_url_rule('/google-health/callback', view_func=self.callback)
        app.register_blueprint(bp)

    @contextmanager
    def transaction(self):
        connection = self.db()
        try:
            with connection:
                with connection.cursor() as cursor:
                    yield cursor
        finally:
            connection.close()

    def encrypt(self, value):
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value):
        return self.cipher.decrypt(value.encode()).decode()

    def oauth(self, data):
        try:
            response = requests.post('https://oauth2.googleapis.com/token', data={
                **data, 'client_id': self.client_id, 'client_secret': self.client_secret,
            }, timeout=(5, 20))
            if response.status_code != 200:
                raise HealthError('Google 授權已失效或交換失敗，請重新連結。')
            return response.json()
        except (requests.RequestException, ValueError):
            raise HealthError('Google 授權服務暫時無法連線，請稍後再試。') from None

    def get(self, path, token, params=None):
        try:
            response = requests.get(API + path, params=params,
                headers={'Authorization': 'Bearer ' + token}, timeout=(5, 25))
            if response.status_code == 400 and path == '/identity':
                raise HealthError('請先在 Google Health 手機 App 登入同一個 Google 帳號，再重新連結。')
            if response.status_code in (401, 403):
                raise HealthError('Google 權限不足或授權失效，請重新連結並同意步數讀取。')
            if response.status_code != 200:
                raise HealthError('Google 資料查詢暫時失敗，請稍後再試。')
            return response.json()
        except (requests.RequestException, ValueError):
            raise HealthError('Google 資料服務暫時無法連線，請稍後再試。') from None

    def issue_link(self, user_id):
        ticket = secrets.token_urlsafe(32)
        with self.transaction() as cur:
            cur.execute('DELETE FROM google_health_oauth_tickets WHERE expires_at < now() OR user_id=%s', (user_id,))
            cur.execute('INSERT INTO google_health_oauth_tickets (ticket_hash,user_id,expires_at) VALUES (%s,%s,now()+interval \'10 minutes\')', (digest(ticket), user_id))
        return self.base + '/google-health/connect?' + urlencode({'ticket': ticket})

    def page(self, message, status=200):
        response = make_response(message, status)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def connect(self):
        ticket = request.args.get('ticket', '')
        state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.transaction() as cur:
            cur.execute('''DELETE FROM google_health_oauth_tickets
                WHERE ticket_hash=%s AND expires_at>now() RETURNING user_id''', (digest(ticket),))
            row = cur.fetchone()
            if not row:
                return self.page('連結已失效，請回 LINE 私人聊天室重新取得。', 400)
            cur.execute('DELETE FROM google_health_oauth_states WHERE user_id=%s OR expires_at<now()', (row[0],))
            cur.execute('''INSERT INTO google_health_oauth_states
                (state_hash,browser_hash,user_id,expires_at)
                VALUES (%s,%s,%s,now()+interval '10 minutes')''', (digest(state), digest(browser), row[0]))
        response = redirect('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
            'client_id': self.client_id, 'redirect_uri': self.callback_uri,
            'response_type': 'code', 'scope': SCOPE, 'access_type': 'offline',
            'prompt': 'consent', 'state': state,
        }))
        response.set_cookie('gh_browser', browser, max_age=600, secure=True,
            httponly=True, samesite='Lax', path='/google-health')
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    def callback(self):
        state = request.args.get('state', '')
        browser = request.cookies.get('gh_browser', '')
        if not state or not browser:
            return self.page('授權工作階段無效，請從 LINE 重新連結。', 400)
        with self.transaction() as cur:
            cur.execute('''DELETE FROM google_health_oauth_states WHERE
                state_hash=%s AND browser_hash=%s AND expires_at>now() RETURNING user_id''', (digest(state), digest(browser)))
            row = cur.fetchone()
        if not row:
            return self.page('授權工作階段已過期或已使用，請重新連結。', 400)
        if request.args.get('error') or not request.args.get('code'):
            return self.page('未完成 Google 授權。請回 LINE 重新連結。', 400)
        try:
            tokens = self.oauth({'grant_type': 'authorization_code',
                'code': request.args['code'], 'redirect_uri': self.callback_uri})
            if SCOPE not in tokens.get('scope', '').split() or not tokens.get('refresh_token'):
                raise HealthError('未取得完整步數授權，請重新連結並勾選讀取權限。')
            identity = self.get('/identity', tokens['access_token'])
            health_id = identity.get('healthUserId')
            if not health_id:
                raise HealthError('Google Health 帳戶識別失敗，請重新連結。')
            with self.transaction() as cur:
                # Also prevents reconnecting a stale link after account deactivation.
                cur.execute('SELECT id FROM app_users WHERE id=%s AND is_active=TRUE FOR UPDATE', (row[0],))
                if not cur.fetchone():
                    raise HealthError('LINE 使用者帳戶未啟用。')
                cur.execute('SELECT user_id FROM google_health_accounts WHERE health_user_id=%s', (health_id,))
                existing = cur.fetchone()
                if existing and str(existing[0]) != str(row[0]):
                    raise HealthError('此 Google Health 帳戶已連結另一位使用者。')
                cur.execute('SELECT health_user_id FROM google_health_accounts WHERE user_id=%s', (row[0],))
                old = cur.fetchone()
                if old and old[0] != health_id:
                    raise HealthError('如需更換 Google 帳戶，請先在 LINE 解除連結。')
                cur.execute('''INSERT INTO google_health_accounts
                    (user_id,health_user_id,refresh_token_cipher,access_token_cipher,expires_at,scope)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET
                    refresh_token_cipher=EXCLUDED.refresh_token_cipher,
                    access_token_cipher=EXCLUDED.access_token_cipher,
                    expires_at=EXCLUDED.expires_at,scope=EXCLUDED.scope,updated_at=now()''',
                    (row[0], health_id, self.encrypt(tokens['refresh_token']),
                     self.encrypt(tokens['access_token']), datetime.now(timezone.utc)+timedelta(seconds=int(tokens.get('expires_in',3600))), tokens['scope']))
            response = self.page('Google Health 已連結。請回 LINE 私人聊天室輸入「同步健康步數」。')
            response.delete_cookie('gh_browser', path='/google-health', secure=True, httponly=True, samesite='Lax')
            return response
        except HealthError as error:
            return self.page(str(error), 400)
        except Exception:
            # Intentionally omit exception text, OAuth URL, tokens and account IDs.
            self.app.logger.error('Google Health callback failed')
            return self.page('連結未完成，請稍後從 LINE 重新連結。', 500)

    def status(self, user_id):
        with self.transaction() as cur:
            cur.execute('SELECT updated_at FROM google_health_accounts WHERE user_id=%s', (user_id,))
            linked = cur.fetchone()
            cur.execute('SELECT fetched_at,jsonb_array_length(payload) FROM google_health_step_snapshots WHERE user_id=%s', (user_id,))
            snapshot = cur.fetchone()
        if not linked:
            return '尚未連結。請輸入「連結 Google Health」。'
        if not snapshot:
            return '已連結 Google Health，尚未同步步數。'
        return f'已連結；最近同步：{snapshot[0].isoformat()}，{snapshot[1]} 筆區間紀錄。'

    def sync(self, user_id):
        # Row lock serializes refresh/sync against disconnect and reconnect.
        with self.transaction() as cur:
            cur.execute('''SELECT health_user_id,refresh_token_cipher,access_token_cipher,expires_at
                FROM google_health_accounts WHERE user_id=%s FOR UPDATE''', (user_id,))
            row = cur.fetchone()
            if not row:
                raise HealthError('尚未連結。請先輸入「連結 Google Health」。')
            access = self.decrypt(row[2])
            if row[3] <= datetime.now(timezone.utc)+timedelta(seconds=60):
                tokens = self.oauth({'grant_type':'refresh_token', 'refresh_token':self.decrypt(row[1])})
                access = tokens['access_token']
                cur.execute('''UPDATE google_health_accounts SET access_token_cipher=%s,
                    refresh_token_cipher=%s, expires_at=%s,updated_at=now() WHERE user_id=%s''',
                    (self.encrypt(access), self.encrypt(tokens['refresh_token']) if tokens.get('refresh_token') else row[1],
                     datetime.now(timezone.utc)+timedelta(seconds=int(tokens.get('expires_in',3600))),user_id))
            end = datetime.now(timezone.utc)
            start = end-timedelta(days=7)
            params = {'pageSize':1000, 'filter':f'steps.interval.start_time >= "{start.isoformat()}" AND steps.interval.start_time < "{end.isoformat()}"'}
            points, seen = [], set()
            for _ in range(100):
                data = self.get('/dataTypes/steps/dataPoints:reconcile', access, params)
                points.extend(data.get('dataPoints', []))
                token = data.get('nextPageToken')
                if not token:
                    break
                if token in seen:
                    raise HealthError('Google 分頁資料異常，本次同步未儲存。')
                seen.add(token)
                params['pageToken'] = token
            else:
                raise HealthError('資料超過單次同步上限，本次同步未儲存。')
            records = normalize_steps(points, user_id)
            # Replace complete rolling snapshot, avoiding stale reconciled intervals.
            # Empty successful responses replace old snapshots too.
            cur.execute('''INSERT INTO google_health_step_snapshots
                (user_id,health_user_id,window_start,window_end,payload,fetched_at)
                VALUES (%s,%s,%s,%s,%s::jsonb,now()) ON CONFLICT(user_id) DO UPDATE SET
                health_user_id=EXCLUDED.health_user_id,window_start=EXCLUDED.window_start,
                window_end=EXCLUDED.window_end,payload=EXCLUDED.payload,fetched_at=now()''',
                (user_id,row[0],start,end,json.dumps(records)))
        return f'同步完成：最近 7 天查詢範圍取得 {len(records)} 筆步數區間。這是紀錄筆數，並非總步數。'

    def disconnect(self, user_id):
        with self.transaction() as cur:
            cur.execute('SELECT refresh_token_cipher FROM google_health_accounts WHERE user_id=%s FOR UPDATE', (user_id,))
            row = cur.fetchone()
            cur.execute('DELETE FROM google_health_step_snapshots WHERE user_id=%s', (user_id,))
            cur.execute('DELETE FROM google_health_oauth_states WHERE user_id=%s', (user_id,))
            cur.execute('DELETE FROM google_health_oauth_tickets WHERE user_id=%s', (user_id,))
            cur.execute('DELETE FROM google_health_accounts WHERE user_id=%s', (user_id,))
        revoked = True
        if row:
            try:
                response = requests.post('https://oauth2.googleapis.com/revoke',
                    data={'token':self.decrypt(row[0])}, timeout=(5,10))
                revoked = response.status_code == 200
            except Exception:
                revoked = False
        return '已移除本系統的連結與步數快照。' + ('' if revoked else ' Google 端撤銷未確認，請至 Google 帳號的第三方連結手動撤銷。')


def register_google_health(app, db):
    if os.getenv('GOOGLE_HEALTH_ENABLED', '').lower() != 'true':
        return None
    return GoogleHealth(app, db)
