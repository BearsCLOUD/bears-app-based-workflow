# Yandex 360 DNS API reference notes

Primary docs:

- Yandex 360 API: https://yandex.ru/dev/api360/doc/ru/
- DNS list service page: https://yandex.ru/dev/api360/doc/ref/DomainDNSService/DomainDNSService_List/
- OAuth / Yandex ID: https://yandex.ru/dev/id/doc/ru/
- Manual token flow: https://yandex.ru/dev/id/doc/ru/tokens/debug-token

Base URL: `https://api360.yandex.net`.

Authorization header for Yandex 360 API calls:

```http
Authorization: OAuth <token>
```

Required scopes: `directory:read_organization` to discover `orgId`, and `directory:manage_dns` to read DNS records through the Yandex 360 DNS service.

Active helper endpoints:

```http
GET /directory/v1/org
GET /directory/v1/org/{orgId}/domains/{domain}/dns
```

Mutation endpoints are intentionally not wired in this bundle. The local helper creates review packets only.

Record object fields observed in the API ecosystem:

```json
{
  "recordId": 123,
  "type": "TXT",
  "name": "_acme-challenge",
  "text": "value",
  "ttl": 21600,
  "address": "203.0.113.10",
  "exchange": "mx.yandex.net",
  "preference": 10,
  "target": "example.com.",
  "priority": 0,
  "weight": 5,
  "port": 443,
  "flag": 0,
  "tag": "issue",
  "value": "letsencrypt.org"
}
```

OAuth setup notes:

- The app should be an API-access OAuth application with the needed Yandex 360 permissions selected.
- For manual token retrieval, configure redirect URI `https://oauth.yandex.ru/verification_code` and open `https://oauth.yandex.ru/authorize?response_type=token&client_id=<client_id>`.
- Never paste full redirect URLs into chat; the fragment after `#access_token=` is a secret.
- Store the token directly in Infisical or another operator-approved secret manager. Do not store it in local files.
