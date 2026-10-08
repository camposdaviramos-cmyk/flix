// API control-plane rehearsal. Does not download streams or certify playback capacity.
import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { SharedArray } from 'k6/data';

const base = (__ENV.BASE_URL || '').replace(/\/$/, '');
if (!/^https?:\/\/[^/?#]+$/.test(base) || /(?:^|[/.])flix\.devspacey\.com(?::\d+)?$/i.test(base))
  throw new Error('BASE_URL must be an explicit isolated origin, never WorkTV production.');
const vus = Number(__ENV.VUS || 8);
if (!Number.isInteger(vus) || vus < 4 || vus > 25000) throw new Error('VUS must be 4..25000.');
if (vus > 32 && __ENV.DEDICATED_LOAD_ENV !== 'confirmed')
  throw new Error('Above 32 VUs requires a dedicated environment and DEDICATED_LOAD_ENV=confirmed.');
if (!__ENV.FIXTURE_FILE) throw new Error('FIXTURE_FILE with disposable sessions is required.');
const fixture = JSON.parse(open(__ENV.FIXTURE_FILE));
const identity = fixture.identity;
const accounts = new SharedArray('disposable-sessions', () => JSON.parse(open(__ENV.FIXTURE_FILE)).accounts);
if (!identity || accounts.length < vus) throw new Error('Provide a distinct disposable account per VU and fixture identity.');

export const options = {
  discardResponseBodies: true,
  maxRedirects: 0,
  scenarios: { mixed: { executor: 'ramping-vus', startVUs: 0,
    stages: [{ duration: __ENV.RAMP || '10s', target: vus },
      { duration: __ENV.HOLD || '30s', target: vus },
      { duration: __ENV.RAMP || '10s', target: 0 }], gracefulRampDown: '20s' } },
  thresholds: {
    http_req_failed: ['rate<0.001'], checks: ['rate>0.999'],
    http_req_duration: ['p(95)<300', 'p(99)<1000'],
    'http_req_duration{journey:guest}': ['p(95)<300'],
    'http_req_duration{journey:account}': ['p(95)<300'],
    'http_req_duration{journey:playback}': ['p(95)<300'],
    'http_req_duration{journey:social}': ['p(95)<300'],
  },
};
export function setup() {
  // This marker exists only in the disposable runner; staging must explicitly provision it.
  const response = http.get(base + '/__loadtest__/identity', { responseType: 'text', redirects: 0 });
  if (response.status !== 200 || response.body !== identity)
    throw new Error('Origin does not match the disposable fixture. No load started.');
}
export default function () {
  const account = accounts[exec.vu.idInTest - 1];
  const journey = ['guest', 'account', 'playback', 'social'][(exec.vu.idInTest - 1) % 4];
  const params = { headers: { 'X-Requested-With': 'Flix', 'Content-Type': 'application/json' },
    tags: { journey }, timeout: '10s', redirects: 0 };
  if (journey !== 'guest') params.cookies = { vyra_session: account.token };
  function get(path, name = path) {
    const r = http.get(base + path, { ...params, tags: { journey, name } });
    check(r, { 'HTTP 200': r => r.status === 200 }, { journey });
  }
  if (journey === 'guest') { get('/api/bootstrap'); get('/api/catalog'); sleep(5); }
  if (journey === 'account') { get('/api/bootstrap'); get('/api/catalog'); get('/api/library'); sleep(5); }
  if (journey === 'social') { get('/api/hub/inbox'); get('/api/hub/notifications'); sleep(4); }
  if (journey === 'playback') {
    if (exec.vu.iterationInScenario === 0) get('/api/play/' + account.content_id, '/api/play/:id');
    const r = http.put(base + '/api/progress/' + account.content_id,
      JSON.stringify({ position: (exec.vu.iterationInScenario * 15) % 600, duration: 600, client_time: Date.now() }),
      { ...params, tags: { journey, name: '/api/progress/:id' } });
    check(r, { 'progress accepted': r => r.status === 200 }, { journey });
    sleep(15);
  }
}
