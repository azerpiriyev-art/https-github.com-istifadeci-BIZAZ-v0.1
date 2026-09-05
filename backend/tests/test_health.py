from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'

def test_meta():
    r = client.get('/api/v1/meta')
    assert r.status_code == 200
    assert r.json()['currency'] == 'AZN'
    assert r.json()['vat_rate_default'] == 18
