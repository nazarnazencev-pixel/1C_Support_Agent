# Сертификат GigaChat

`russian_trusted_root_ca.pem` скачан по HTTPS с официального адреса:
https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt

Источник адреса и инструкция по использованию на уровне приложения:
https://developers.sber.ru/docs/ru/gigachat/certificates

SHA-256 скачанного файла:
`936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504`

Сертификат применяется только к клиенту GigaChat через `GIGACHAT_CA_BUNDLE_FILE`. Системное хранилище доверия не изменяется. Проверка TLS остаётся включённой. Для другой цепочки или после обновления сертификатов можно явно задать `GIGACHAT_CA_BUNDLE_FILE` в окружении приложения.
