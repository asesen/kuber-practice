# Домашка 1

## Запуск

Предполагается, что на устройстве установлен kind, kubectl и все для них необзходимое

Также предполагается, что поднят кластер lab

При запуске на Codespace достаточно сделать так:

```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

kind create cluster --name lab
```



```bash
./deploy.sh
```

Мы запускаем кластер kind, в итоге я проверял работу в github codespace (у меня на ноуте случился какой-то прикол и кубер никак не пожелал запускаться после обновления докера)


### Проверка API через port-forward

```bash
kubectl -n kuber-practice port-forward svc/custom-app 8080:80
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/status
curl -i -X POST http://127.0.0.1:8080/log -H 'Content-Type: application/json' -d '{"message":"hello"}'
curl -i http://127.0.0.1:8080/logs
```

Далее предполагаем, что порт прокинут

### Проверка балансировки Service между pod'ами

Сервис `custom-app` распределяет запросы по репликам, а pod добавляет заголовок **`X-Pod-Hostname`**.

```bash
kubectl -n kuber-practice run -it --rm curl --image=curlimages/curl:8.10.1 --restart=Never -- \
sh -lc 'for i in $(seq 1 10); do curl -s -D- http://custom-app/status -o /dev/null | grep -i x-pod-hostname; done'
```

Видим тут разные поды и радуемся

### Проверка DaemonSet log-agent

`log-agent` (fluent-bit) читает логи контейнеров `custom-app` из `/var/log/containers/*custom-app*.log` и печатает в stdout.

```bash
kubectl -n kuber-practice get pods -l app=log-agent -o wide
kubectl -n kuber-practice logs -l app=log-agent --tail=100
```

Тут будет список наших запросов, так что логи пишутся, все ок

### Проверка CronJob архивирования (каждые 10 минут)

CronJob `log-archiver` берёт логи через HTTP `GET /logs`, сохраняет в `/app/logs/app.log`, архивирует:
`tar -czf /tmp/app-logs-<timestamp>.tar.gz /app/logs/`

```bash
kubectl -n kuber-practice get cronjob
kubectl -n kuber-practice get jobs
kubectl -n kuber-practice logs job/$(kubectl -n kuber-practice get jobs -o jsonpath='{.items[-1:].metadata.name}') --tail=200
```

Тут файлик создается, типо все ок