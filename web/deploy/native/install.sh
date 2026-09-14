set -eu
project_root=/opt/molvest-support
id molvest >/dev/null 2>&1 || useradd --system --home-dir /var/lib/molvest-support --shell /usr/sbin/nologin molvest
install -d -m 0750 -o molvest -g molvest /var/lib/molvest-support
install -d -m 0700 /etc/molvest-support
if test -f /root/molvest-production.env; then
    install -m 0600 /root/molvest-production.env /etc/molvest-support/environment
    rm /root/molvest-production.env
fi
test -s /etc/molvest-support/environment
python3 -m venv "$project_root/.venv"
"$project_root/.venv/bin/pip" install --no-cache-dir --only-binary=:all: -r "$project_root/web/server/requirements.lock"
if ! test -e "$project_root/1C_Support_Agent/support_agent.db" && ! test -L "$project_root/1C_Support_Agent/support_agent.db"; then
    ln -s /var/lib/molvest-support/support_agent.db "$project_root/1C_Support_Agent/support_agent.db"
fi
chown -R molvest:molvest "$project_root/1C_Support_Agent/data/knowledge"
install -m 0644 "$project_root/web/deploy/native/molvest-support.service" /etc/systemd/system/molvest-support.service
if ! test -e /etc/nginx/sites-available/molvest-support; then
    install -m 0644 "$project_root/web/deploy/native/nginx.conf" /etc/nginx/sites-available/molvest-support
fi
if test -L /etc/nginx/sites-enabled/default; then
    unlink /etc/nginx/sites-enabled/default
fi
ln -sfn /etc/nginx/sites-available/molvest-support /etc/nginx/sites-enabled/molvest-support
nginx -t
install -m 0644 "$project_root/web/deploy/native/molvest-https.service" /etc/systemd/system/molvest-https.service
install -m 0644 "$project_root/web/deploy/native/molvest-https.timer" /etc/systemd/system/molvest-https.timer
systemctl daemon-reload
systemctl enable --now molvest-support nginx certbot.timer
systemctl reload nginx
if ! test -s /etc/letsencrypt/live/wizardlizard.ru/fullchain.pem; then
    systemctl enable --now molvest-https.timer
fi
systemctl is-active molvest-support nginx
