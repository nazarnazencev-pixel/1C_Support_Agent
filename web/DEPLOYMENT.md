# Развёртывание на Cloud4box

Проверено 14 сентября 2026 года. VPS: `46.8.220.47`, Ubuntu 24.04.4 LTS. Домен: `wizardlizard.ru`, дополнительное имя: `www.wizardlizard.ru`.

## Доступ

До обновления DNS сайт работает по адресу http://46.8.220.47/. На момент проверки публичные DNS-серверы возвращали прежний адрес `31.31.196.165` для обоих имён.

Логин оператора: `admin`. Сгенерированный пароль сохранён только в локальном файле `web/.local/deployment/server-access.txt` и в закрытом окружении на VPS. Каталог `.local` исключён из Git и релизного архива. Административный API через публичный HTTP возвращает 403; вход оператора будет доступен через HTTPS после выпуска сертификата.

## Установленная конфигурация

- Код: `/opt/molvest-support`, бэкенд: `1C_Support_Agent`, фронтенд: `web/dist`.
- Окружение Python: `/opt/molvest-support/.venv`, зависимости из `web/server/requirements.lock`.
- API работает от системного пользователя `molvest`, один процесс Uvicorn на `127.0.0.1:8000`.
- Служба `molvest-support.service` включена в автозагрузку, перезапускается при сбое.
- Nginx раздаёт готовый фронтенд и проксирует `/api`. Node.js на VPS не требуется: сборка выполнена локально.
- SQLite: `/var/lib/molvest-support/support_agent.db`, ссылка из каталога бэкенда.
- Настройки и ключ GigaChat: `/etc/molvest-support/environment`, права `600`, владелец `root`. Ключ передан с явного разрешения пользователя.
- База знаний: `/opt/molvest-support/1C_Support_Agent/data/knowledge`, режим `keyword` с доступным редактором.
- UFW включён; разрешены SSH, HTTP и HTTPS. Порт API доступен только локально.

## HTTPS

Служба `molvest-https.service` проверяет A и AAAA обоих доменных имён через `1.1.1.1` и `8.8.8.8`. Сертификат запрашивается только если A возвращают ровно `46.8.220.47`, а AAAA отсутствуют, поскольку IPv6 для сайта не настроен.

Таймер `molvest-https.timer` запускает проверку ежечасно и после загрузки сервера. Пока DNS не готов, служба завершается успешно с сообщением `Waiting for DNS`. После готовности запускается Certbot с плагином Nginx для обоих имён и перенаправлением HTTP на HTTPS. При успешном выпуске таймер первичной настройки отключается. Дальнейшее обновление сертификата выполняет штатный `certbot.timer`.

Сертификат на момент развёртывания ещё не получен: проверена ветка ожидания DNS. Выпуск также зависит от доступности порта 80 извне и успешной проверки домена центром сертификации. Учётная запись Certbot создаётся без адреса электронной почты.

## Управление через SSH

```sh
systemctl status molvest-support nginx
journalctl -u molvest-support -n 100 --no-pager
systemctl restart molvest-support
systemctl start molvest-https.service
journalctl -u molvest-https.service -n 30 --no-pager
systemctl list-timers molvest-https.timer certbot.timer
nginx -t
```

Для изменения ключа или пароля отредактируйте `/etc/molvest-support/environment` на сервере и перезапустите `molvest-support`. Не публикуйте этот файл вместе с исходниками.

## Проверки

- `npm run build` завершился успешно; `npm test`: 5 тестов прошли, включая создание UUID без `crypto.randomUUID()` при HTTP-доступе.
- В настоящем Chrome через публичный IP отправлено сообщение «Привет, что ты умеешь?». Получен HTTP 200 и содержательный ответ GigaChat, ошибок JavaScript нет.
- Диалог сохранился после перезагрузки браузера. При ширине 390 пикселей горизонтального переполнения нет, скриншот проверен визуально.
- `/api/health` возвращает `status: ok`, `knowledge_editable: true`, в том числе после перезапуска службы.
- Локальная проверка административного API: без пароля 401, с настроенным паролем 200.
- Проверка SQLite `PRAGMA quick_check` вернула `ok`.
- После перезапуска в таблице `requests` осталось одно тестовое обращение с успешным ответом; в `users` — один тестовый пользователь. Исходный бэкенд не записал этот обмен в отдельную таблицу `messages`.
- API и Nginx активны, их автозапуск включён; таймеры первичной настройки HTTPS и обновления сертификата включены.

Исходные файлы настройки: [systemd API](deploy/native/molvest-support.service), [Nginx](deploy/native/nginx.conf), [установка](deploy/native/install.sh), [проверка DNS и выпуск сертификата](deploy/native/enable-https.sh), [служба HTTPS](deploy/native/molvest-https.service), [таймер HTTPS](deploy/native/molvest-https.timer).

Документация поставщиков: [установка Nginx на Ubuntu](https://ubuntu.com/server/docs/how-to/web-services/install-nginx/), [Certbot: использование и обновление сертификатов](https://eff-certbot.readthedocs.io/en/stable/using.html).
