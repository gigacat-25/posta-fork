# SOP: Deploy Posta & Postfix SMTP Stack

This directive details the procedure to deploy the complete Posta delivery stack (API server, Background Worker, PostgreSQL, Redis, and Postfix SMTP) in a single command, ensuring zero hardcoded variables and fully automated SMTP configuration.

---

## 1. Goal & Architecture
To enable reproducible, multi-tenant/multi-user deployments for any client domain or server.
When `docker compose up -d --build` runs:
1. **`posta-db`** and **`posta-redis`** spin up and initialize healthchecks.
2. **`posta-smtp`** (Postfix) boots configured with `MAIL_DOMAIN`, `MAIL_HOSTNAME`, and SASL users.
3. **`posta`** API boots, applies DB migrations, creates the initial admin user from `POSTA_ADMIN_EMAIL`/`POSTA_ADMIN_PASSWORD`, and reads `POSTA_SYSTEM_SMTP_*` to **automatically provision and enable the System SMTP server** in the database.
4. **`worker`** boots and attaches to the database and Redis queue to process outbound emails.

---

## 2. Inputs & Environment Configuration (`.env`)
The stack relies strictly on `.env`. No values are hardcoded in `compose.yml`.

| Variable | Description | Example |
| :--- | :--- | :--- |
| `POSTA_PORT` | HTTP port exposed on the host | `9000` |
| `POSTA_ENV` | Application environment (`production` or `dev`) | `production` |
| `POSTA_JWT_SECRET` | 32+ character JWT secret (`openssl rand -hex 32`) | Random string |
| `POSTA_ADMIN_EMAIL` | Initial admin email address | `admin@clientdomain.com` |
| `POSTA_ADMIN_PASSWORD` | Initial admin password (min 12 chars) | Secure password |
| `MAIL_DOMAIN` | Domain for outbound email sending | `clientdomain.com` |
| `MAIL_HOSTNAME` | Hostname for Postfix HELO / rDNS | `mail.clientdomain.com` |
| `POSTA_DEFAULT_FROM` | Default From address for notifications | `notifications@clientdomain.com` |
| `POSTFIX_SMTP_USER` | SMTP username used by Posta | `posta` |
| `POSTFIX_SMTP_PASSWORD` | SMTP password used by Posta | Secure password |
| `REMOTE_HOST` | *(Optional)* Remote VPS IP for remote deployment | `109.122.56.27` |
| `REMOTE_USER` | *(Optional)* SSH username on remote server | `root` |
| `REMOTE_PASSWORD` | *(Optional)* SSH password on remote server | Secure password |
| `REMOTE_DIR` | *(Optional)* Directory on remote server | `/opt/posta` |

---

## 3. One-Command Execution

### Local or Direct Server Execution:
```bash
docker compose up -d --build
```
Or via Makefile:
```bash
make up
```

### Automated Remote VPS Deployment:
To deploy from your workstation to the remote VPS specified in `.env`:
```bash
python execution/deploy.py --remote
```

---

## 4. Post-Deployment Verification
1. Check health endpoint:
   `curl http://<HOST>:<POSTA_PORT>/healthz` (should return HTTP 200)
2. Verify all containers are running:
   `docker compose ps`
3. Check Postfix logs:
   `docker compose logs smtp`
4. Log in to the Posta web dashboard at `http://<HOST>:<POSTA_PORT>` with your admin credentials.
   Under **SMTP Servers**, the **System SMTP** server will already be present and in `enabled` state.

---

## 5. Required External DNS Configuration
For emails to be accepted by recipient mail providers (Gmail, Outlook, Yahoo):
1. **A Record**: `mail.<MAIL_DOMAIN>` ➔ `<SERVER_IP>` *(DNS-only, not proxied)*
2. **MX Record**: `@` ➔ `mail.<MAIL_DOMAIN>` (Priority: `10`)
3. **SPF (TXT)**: `v=spf1 ip4:<SERVER_IP> ~all`
4. **DMARC (TXT)**: Name `_dmarc`, Value `v=DMARC1; p=none;`
5. **rDNS / PTR Record**: Configure in VPS hosting provider panel so `<SERVER_IP>` resolves to `mail.<MAIL_DOMAIN>`.
