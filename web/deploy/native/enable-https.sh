set -eu
if test -s /etc/letsencrypt/live/wizardlizard.ru/fullchain.pem; then
    systemctl disable --now molvest-https.timer
    exit 0
fi
for domain in wizardlizard.ru www.wizardlizard.ru; do
    for resolver in 1.1.1.1 8.8.8.8; do
        addresses=$(dig +short +time=3 +tries=1 "@$resolver" "$domain" A)
        ipv6_addresses=$(dig +short +time=3 +tries=1 "@$resolver" "$domain" AAAA)
        if test "$addresses" != "46.8.220.47" || test -n "$ipv6_addresses"; then
            printf 'Waiting for DNS: %s via %s\n' "$domain" "$resolver"
            exit 0
        fi
    done
done
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --redirect --cert-name wizardlizard.ru -d wizardlizard.ru -d www.wizardlizard.ru
nginx -t
systemctl disable --now molvest-https.timer
