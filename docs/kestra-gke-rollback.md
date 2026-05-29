# Kestra GKE Rollback

## Check Helm releases
```bash
helm history kestra -n kestra
```

## Rollback
```bash
helm rollback kestra <REVISION> -n kestra
```

## Check pods
```bash
kubectl get pods -n kestra
kubectl rollout status deployment/kestra-webserver -n kestra
kubectl rollout status deployment/kestra-worker -n kestra
```

## Port-forward UI
```bash
kubectl port-forward deployment/kestra-webserver 8080:8080 -n kestra
```
Open: `http://localhost:8080`

## Re-deploy flows manually
```bash
export KESTRA_SERVER=[http://127.0.0.1:8080](http://127.0.0.1:8080)
export KESTRA_USER=<username>
export KESTRA_PASSWORD=<password>

curl -sFL [https://kestra.io/install.sh](https://kestra.io/install.sh) | bash
./kestra flows deploy ./kestra/flows-gke \
  --server "$KESTRA_SERVER" \
  --user "$KESTRA_USER" \
  --password "$KESTRA_PASSWORD"
```