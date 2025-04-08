

::: {.cell .markdown}

## Launch containers

Inside the SSH session, bring up the Flask, FastAPI, LabelStudio & MinIO services:


```bash
# runs on node-eval-loop
docker compose -f eval-loop-chi/docker/docker-compose-feedback.yaml up -d
```

```bash
# Wait 30 seconds for system to get ready
sleep 30
```
:::

