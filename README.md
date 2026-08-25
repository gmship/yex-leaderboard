# Yex Leaderboard

A small, self-hosted leaderboard for launches, products, tools, or whatever you want to rank.

> **Live example:** [yex.lol](https://yex.lol) — see how a running board looks before installing your own.

> **在线示例：** [yex.lol](https://yex.lol) — 安装前可以先查看实际运行效果。

The repository starts with ten fictional `example.com` listings. It contains no production database, visitor records, payment records, server credentials, or deployment configuration from yex.lol.

## Features

- Public leaderboard ranked by bid.
- Anonymous public submissions with exactly one **Mainly built with** tool.
- Bid-only **Help bid** flow for existing listings; public users cannot rewrite listing details.
- Shareable product detail pages with spend, rank, clicks, build time, visit, and sharing actions.
- New listings and Top clicks panels with click counts.
- Direct tracked links or `/go/` redirects with configurable tracking codes.
- Password-protected link manager with search, pagination, add, full listing edits, two categories, build time, hide, and restore actions.
- Stats dashboard for visits, listings, clicks, bids, payments, categories, and tools.
- Settings for SEO title and description, URL behavior, admin password, categories, and Built with options.
- SQLite storage and optional Stripe Checkout.
- Dark and light themes with a responsive layout.
- Docker support and GitHub Actions tests.

## Requirements

Choose one installation method:

- Python 3.11 or newer, plus `pip`; or
- Docker Engine with Docker Compose.

Git is needed only when cloning or updating the repository.

## 中文安装说明

下面任选一种方式安装。首次安装建议使用 Docker；如果服务器已经配置好 Python，也可以直接运行。

### 使用 Docker 安装（推荐）

Linux 或 macOS：

```bash
git clone https://github.com/gmship/yex-leaderboard.git
cd yex-leaderboard
cp .env.example .env
docker compose up -d --build
```

Windows PowerShell：

```powershell
git clone https://github.com/gmship/yex-leaderboard.git
Set-Location yex-leaderboard
Copy-Item .env.example .env
docker compose up -d --build
```

启动后访问 `http://127.0.0.1:5000`，后台地址为 `http://127.0.0.1:5000/admin`。Docker 数据保存在项目目录的 `data` 文件夹中。

常用命令：

```bash
docker compose logs -f leaderboard
docker compose restart leaderboard
docker compose down
docker compose up -d --build
```

`docker compose down` 不会删除 `data` 目录。除非确定要删除数据，否则不要使用 `docker compose down -v`。

### 使用 Python 安装

macOS 或 Linux：

```bash
git clone https://github.com/gmship/yex-leaderboard.git
cd yex-leaderboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Windows PowerShell：

```powershell
git clone https://github.com/gmship/yex-leaderboard.git
Set-Location yex-leaderboard
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

如果 PowerShell 禁止激活虚拟环境，可先在当前窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 首次登录和必要设置

- 后台地址：`http://127.0.0.1:5000/admin`
- 默认用户名：`admin`
- 默认密码：`admin`

上线前请立即进入 **Admin → Settings → Administrator password** 修改管理员密码，并在 `.env` 中设置新的 `FLASK_SECRET_KEY`。Settings 页面还可以修改 SEO 标题与描述、链接跳转方式、跟踪参数、分类以及 Built with 选项。

应用会自动读取项目根目录的 `.env`。至少建议检查以下配置：

```dotenv
SITE_NAME=Whatever Board
BASE_URL=https://your-domain.example
HOST=127.0.0.1
PORT=5000
DATABASE_PATH=./data/leaderboard.db
FLASK_SECRET_KEY=replace-with-a-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-this-password
SEED_DEMO_DATA=1
```

可以使用下面的命令生成随机密钥：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

如果需要一个完全空白的排行榜，请在**首次启动前**设置 `SEED_DEMO_DATA=0`。不要把 `.env`、数据库、Stripe 密钥或真实密码提交到 Git。

### Ubuntu/Debian 生产环境部署

以下示例使用 Gunicorn、systemd 和 Nginx，假设代码目录为 `/srv/yex-leaderboard`：

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv
sudo useradd --system --create-home --shell /usr/sbin/nologin yexboard
sudo git clone https://github.com/gmship/yex-leaderboard.git /srv/yex-leaderboard
sudo chown -R yexboard:yexboard /srv/yex-leaderboard
sudo -u yexboard python3 -m venv /srv/yex-leaderboard/.venv
sudo -u yexboard /srv/yex-leaderboard/.venv/bin/pip install -r /srv/yex-leaderboard/requirements.txt
sudo -u yexboard cp /srv/yex-leaderboard/.env.example /srv/yex-leaderboard/.env
```

编辑 `/srv/yex-leaderboard/.env`，正确填写域名、管理员密码和随机密钥，然后限制文件权限：

```bash
sudo chown yexboard:yexboard /srv/yex-leaderboard/.env
sudo chmod 600 /srv/yex-leaderboard/.env
```

创建 `/etc/systemd/system/yex-leaderboard.service`：

```ini
[Unit]
Description=Yex Leaderboard
After=network.target

[Service]
Type=simple
User=yexboard
Group=yexboard
WorkingDirectory=/srv/yex-leaderboard
EnvironmentFile=/srv/yex-leaderboard/.env
ExecStart=/srv/yex-leaderboard/.venv/bin/gunicorn --workers 2 --threads 2 --timeout 30 --bind 127.0.0.1:8000 app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yex-leaderboard
sudo systemctl status yex-leaderboard --no-pager
curl http://127.0.0.1:8000/health
```

创建 `/etc/nginx/sites-available/yex-leaderboard`，把示例域名替换成自己的域名：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

启用站点并检查 Nginx 配置：

```bash
sudo ln -s /etc/nginx/sites-available/yex-leaderboard /etc/nginx/sites-enabled/yex-leaderboard
sudo nginx -t
sudo systemctl reload nginx
```

最后使用自己的 TLS/HTTPS 方案为域名启用证书，把 `.env` 中的 `BASE_URL` 改为最终的 `https://` 地址，再执行 `sudo systemctl restart yex-leaderboard`。

### 更新、测试和备份

更新 Python/systemd 部署：

```bash
cd /srv/yex-leaderboard
sudo -u yexboard git pull --ff-only
sudo -u yexboard .venv/bin/pip install -r requirements.txt
sudo systemctl restart yex-leaderboard
```

更新 Docker 部署：

```bash
git pull --ff-only
docker compose up -d --build
docker compose logs --tail=100 leaderboard
```

运行测试：

```bash
python -m unittest discover -s tests -v
```

数据库默认位于 `data/leaderboard.db`。升级前请先停止写入并备份该文件；恢复时先停止应用，保留当前数据库副本，再用备份文件替换并重启服务。

## Install with Docker

```bash
git clone https://github.com/gmship/yex-leaderboard.git
cd yex-leaderboard
cp .env.example .env
docker compose up -d --build
```

Windows PowerShell equivalent:

```powershell
git clone https://github.com/gmship/yex-leaderboard.git
Set-Location yex-leaderboard
Copy-Item .env.example .env
docker compose up -d --build
```

Open `http://127.0.0.1:5000`. Application data is persisted in `./data` on the host.

Useful Docker commands:

```bash
docker compose logs -f leaderboard
docker compose restart leaderboard
docker compose down
docker compose up -d --build
```

`docker compose down` stops the container but keeps `./data`. Do not add `-v` unless you intentionally want to remove Docker-managed volumes.

## Install with Python on macOS or Linux

```bash
git clone https://github.com/gmship/yex-leaderboard.git
cd yex-leaderboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

## Install with Python on Windows PowerShell

```powershell
git clone https://github.com/gmship/yex-leaderboard.git
Set-Location yex-leaderboard
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

If PowerShell blocks virtual-environment activation, run the following for the current terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## First login

Open `http://127.0.0.1:5000/admin`.

- Username: `admin`
- Password: `admin`

Change the password immediately in **Admin → Settings → Administrator password** before publishing the site. The changed password is stored as a one-way hash in SQLite.

The same Settings page controls:

- Homepage SEO title and meta description.
- Direct tracked URLs versus `/go/` redirects.
- Tracking parameter and value; the defaults are `utm_source=yex`.
- Categories and Built with options.

## Environment configuration

The app loads `.env` automatically. Copy `.env.example` to `.env`, then edit it:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SITE_NAME` | `Whatever Board` | Site name shown in the header and admin pages. |
| `BASE_URL` | `http://127.0.0.1:5000` | Public origin used for checkout callbacks and sitemap links. Do not include a trailing slash. |
| `HOST` | `127.0.0.1` | Development-server bind address. Use `0.0.0.0` only when you understand the network exposure. |
| `PORT` | `5000` | Development-server port. |
| `DATABASE_PATH` | `./data/leaderboard.db` | SQLite database location. Docker Compose overrides this with `/data/leaderboard.db`. |
| `FLASK_SECRET_KEY` | placeholder | Persistent secret used to sign sessions and form tokens. Replace it in production. |
| `FLASK_SECRET_KEY_FILE` | empty | Optional path to a file containing the Flask secret instead of putting it in the environment. |
| `ADMIN_USERNAME` | `admin` | Administrator username. |
| `ADMIN_PASSWORD` | `admin` | Initial administrator password. A password changed in Settings takes precedence. |
| `SUBMISSION_MIN_CENTS` | `100` | Minimum initial bid in cents. Values below 100 are raised to 100. |
| `SEED_DEMO_DATA` | `1` | Adds ten fictional examples only when the projects table is empty. |
| `STRIPE_SECRET_KEY` | empty | Enables Stripe Checkout when configured. |
| `STRIPE_WEBHOOK_SECRET` | empty | Verifies Stripe webhook events. |

Generate a production Flask secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit `.env`, the SQLite database, Stripe keys, or real passwords. They are excluded by `.gitignore`.

## Start with an empty board

Before the first start, set this in `.env`:

```dotenv
SEED_DEMO_DATA=0
```

If the ten examples were already created and you do not need any existing local data:

1. Stop the app.
2. Back up `data/leaderboard.db` if necessary.
3. Delete that database file.
4. Set `SEED_DEMO_DATA=0`.
5. Start the app again.

Never delete a production database merely to remove examples; hide or edit individual listings from the admin manager instead.

## Optional Stripe setup

The public board and admin manager work without Stripe. Paid public submissions require Stripe:

1. Create or select a Stripe account.
2. Add the server-side secret key as `STRIPE_SECRET_KEY`.
3. Create a webhook endpoint pointing to `https://your-domain.example/stripe/webhook`.
4. Subscribe the endpoint to `checkout.session.completed`.
5. Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`.
6. Set `BASE_URL=https://your-domain.example`.
7. Restart the app and check `/health`; `payments` should be `true`.

Stripe secrets must remain server-side. Review the bundled Rules, Terms, and Privacy pages for your business and jurisdiction before accepting payments.

## Run tests

```bash
python -m unittest discover -s tests -v
```

The same test command runs automatically on pushes and pull requests through GitHub Actions.

## Production deployment with Gunicorn and Nginx

The commands below assume Ubuntu/Debian, the app in `/srv/yex-leaderboard`, and a dedicated `yexboard` system user. Replace the domain and paths for your server.

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv
sudo useradd --system --create-home --shell /usr/sbin/nologin yexboard
sudo git clone https://github.com/gmship/yex-leaderboard.git /srv/yex-leaderboard
sudo chown -R yexboard:yexboard /srv/yex-leaderboard
sudo -u yexboard python3 -m venv /srv/yex-leaderboard/.venv
sudo -u yexboard /srv/yex-leaderboard/.venv/bin/pip install -r /srv/yex-leaderboard/requirements.txt
sudo -u yexboard cp /srv/yex-leaderboard/.env.example /srv/yex-leaderboard/.env
```

Edit `/srv/yex-leaderboard/.env` and set at least `SITE_NAME`, `BASE_URL`, `FLASK_SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`. Restrict it:

```bash
sudo chown yexboard:yexboard /srv/yex-leaderboard/.env
sudo chmod 600 /srv/yex-leaderboard/.env
```

Create `/etc/systemd/system/yex-leaderboard.service`:

```ini
[Unit]
Description=Yex Leaderboard
After=network.target

[Service]
Type=simple
User=yexboard
Group=yexboard
WorkingDirectory=/srv/yex-leaderboard
EnvironmentFile=/srv/yex-leaderboard/.env
ExecStart=/srv/yex-leaderboard/.venv/bin/gunicorn --workers 2 --threads 2 --timeout 30 --bind 127.0.0.1:8000 app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yex-leaderboard
sudo systemctl status yex-leaderboard --no-pager
curl http://127.0.0.1:8000/health
```

Create `/etc/nginx/sites-available/yex-leaderboard`:

```nginx
server {
    listen 80;
    server_name your-domain.example;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Enable the site and validate Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/yex-leaderboard /etc/nginx/sites-enabled/yex-leaderboard
sudo nginx -t
sudo systemctl reload nginx
```

Add HTTPS with your preferred TLS provider, then change `BASE_URL` to the final `https://` URL and restart the service.

## Back up and restore

Stop writes briefly for a simple SQLite backup:

```bash
sqlite3 data/leaderboard.db ".backup 'leaderboard-backup.db'"
```

For Docker Compose:

```bash
docker compose exec leaderboard python -c "import sqlite3; source=sqlite3.connect('/data/leaderboard.db'); backup=sqlite3.connect('/data/leaderboard-backup.db'); source.backup(backup); backup.close(); source.close()"
```

To restore, stop the app, keep a copy of the current database, replace `leaderboard.db` with the backup, preserve file ownership, and restart.

## Update an installation

Python/systemd deployment:

```bash
cd /srv/yex-leaderboard
sudo -u yexboard git pull --ff-only
sudo -u yexboard .venv/bin/pip install -r requirements.txt
sudo systemctl restart yex-leaderboard
curl https://your-domain.example/health
```

Docker Compose deployment:

```bash
git pull --ff-only
docker compose up -d --build
docker compose logs --tail=100 leaderboard
```

Back up the database before upgrades. Source updates do not intentionally remove listing data, but backups remain essential.

## License

MIT. The footer attribution “Made with Yex” links back to [yex.lol](https://yex.lol).
