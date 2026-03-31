# Домашка 1

## Запуск

```bash
./deploy.sh
```

### Проверка API через port-forward

```bash
kubectl -n kuber-practice port-forward svc/custom-app 8080:80
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/status
curl -i -X POST http://127.0.0.1:8080/log -H 'Content-Type: application/json' -d '{"message":"hello"}'
curl -i http://127.0.0.1:8080/logs
```

### Проверка балансировки Service между pod'ами

Сервис `custom-app` распределяет запросы по репликам, а pod добавляет заголовок **`X-Pod-Hostname`**.

```bash
kubectl -n kuber-practice port-forward svc/custom-app 8080:80
for i in $(seq 1 10); do curl -s -D- http://127.0.0.1:8080/status -o /dev/null | grep -i x-pod-hostname; done
```

### Проверка DaemonSet log-agent

`log-agent` (fluent-bit) читает логи контейнеров `custom-app` из `/var/log/containers/*custom-app*.log` и печатает в stdout.

```bash
kubectl -n kuber-practice get pods -l app=log-agent -o wide
kubectl -n kuber-practice logs -l app=log-agent --tail=100
```

### Проверка CronJob архивирования (каждые 10 минут)

CronJob `log-archiver` берёт логи через HTTP `GET /logs`, сохраняет в `/app/logs/app.log`, архивирует:
`tar -czf /tmp/app-logs-<timestamp>.tar.gz /app/logs/`

```bash
kubectl -n kuber-practice get cronjob
kubectl -n kuber-practice get jobs
kubectl -n kuber-practice logs job/$(kubectl -n kuber-practice get jobs -o jsonpath='{.items[-1:].metadata.name}') --tail=200
```

### Манифесты

- `k8s/00-namespace.yaml`
- `k8s/01-configmap.yaml`
- `k8s/02-pod.yaml`
- `k8s/03-deployment.yaml`
- `k8s/04-service.yaml`
- `k8s/05-log-agent-config.yaml`
- `k8s/06-log-agent-daemonset.yaml`
- `k8s/07-cronjob-archive.yaml`
- `k8s/08-statefulset.yaml`
