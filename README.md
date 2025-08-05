docker build . -t joplin2readeck:1.0.0
docker run --env-file=.env --rm -it joplin2readeck:1.0.0 /bin/bash
docker tag joplin2readeck:1.0.0 localhost:32000/joplin2readeck:1.0.0
docker push localhost:32000/joplin2readeck:1.0.0
docker compose build
docker compose up

kubectl apply -f joplin2readeck-config.yaml
kubectl get cronjob -n joplin-cli
kubectl describe cronjob joplin2readeck-cron -n joplin-cli

