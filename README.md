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

## Проверка Istio (SECOND_TASK)

### Проверка установки Istio

```bash
kubectl get ns istio-system
kubectl -n istio-system get pods
kubectl -n istio-system get svc
```

Должны быть `istiod`, `istio-ingressgateway`, `istio-egressgateway`.

### Проверка Gateway и VirtualService

```bash
kubectl -n kuber-practice get gateway,virtualservice
kubectl -n kuber-practice describe gateway kuber-gateway
kubectl -n kuber-practice describe vs kuber-routes
```

Должны быть:
- `kuber-gateway` на порту 80
- `kuber-routes` подключен к Gateway

### Проверка DestinationRule

```bash
kubectl -n kuber-practice get destinationrule
kubectl -n kuber-practice describe dr app-service-dr
kubectl -n kuber-practice describe dr log-service-dr
```

Должны быть настроены:
- `LEAST_CONN` балансировка
- максимум 3 TCP соединения
- максимум 5 pending HTTP запросов
- `ISTIO_MUTUAL` TLS режим

### Проверка Sidecar injection

```bash
kubectl -n kuber-practice get pods -o wide
```

У каждого пода должно быть 2 контейнера (app + Envoy sidecar).

### Проверка маршрутизации через Ingress Gateway

```bash
kubectl -n istio-system port-forward svc/istio-ingressgateway 8080:80 &
sleep 2

# GET запросы
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/status
curl -i http://127.0.0.1:8080/logs

# 404 для неизвестного маршрута
curl -i http://127.0.0.1:8080/wrong
```

Все GET запросы должны работать, `/wrong` должен вернуть 404.

### Проверка POST /log с таймаутом (задержка 2s, таймаут 1s)

```bash
time curl -i -X POST http://127.0.0.1:8080/log \
  -H 'Content-Type: application/json' \
  -d '{"message":"test"}'
```

### Проверка TLS между сервисами

```bash
kubectl -n kuber-practice logs -l app=custom-app --tail=10
```

В логах должны быть обработанные запросы. Трафик между pod'ами идет через Envoy с mTLS шифрованием.

### Проверка балансировки соединений (LEAST_CONN)

```bash
# Несколько параллельных запросов
for i in {1..5}; do
  curl -s http://127.0.0.1:8080/status | grep -i x-pod-hostname &
done
wait
```

Запросы должны распределяться между разными pod'ами в зависимости от количества текущих соединений.
