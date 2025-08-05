# Publish joplin note to readeck for ez read 

You can using eink reader borwser to download epub from readeck, if your eink borwser support.

## Before you can using this script must already have joplin server and readeck server

## Build joplin cli data api server first in joplin-cli-server folder 

## Build joplin2readeck python script k8s cronjob image
docker build . -t joplin2readeck:1.0.0
docker run --env-file=.env --rm -it joplin2readeck:1.0.0 /bin/bash
docker tag joplin2readeck:1.0.0 localhost:32000/joplin2readeck:1.0.0
docker push localhost:32000/joplin2readeck:1.0.0
docker compose build
docker compose up

## Create joplin2readeck cronjob on k8s
kubectl apply -f joplin2readeck-*.yaml
kubectl get cronjob -n joplin-cli
kubectl describe cronjob joplin2readeck-cron -n joplin-cli
