# Docker images

The blind runner uses three images. The host dsh package is mounted read-only at runtime, so the
images do not install or build dsh.

| Image | Dockerfile | Contents | Used for |
|---|---|---|---|
| `ale-blind-dsh` | `blind-dsh/Dockerfile` | `node:24-bookworm-slim` | text/Node tasks |
| `ale-blind-dsh-py` | `blind-dsh-py/Dockerfile` | `python:3.12-slim-bookworm` + Node 24.22.0 | Python/SQLite tasks |
| `ale-blind-dsh-data` | `blind-dsh-data/Dockerfile` | `ale-blind-dsh-py` + pandas/pyarrow/numpy/scipy/openpyxl | data-analysis tasks and the seed scorer |

## Build

`ale-blind-dsh-data` extends `ale-blind-dsh-py`, so build in this order. The helper script does it
for you:

```bash
cd ~/ale-task-factory
docker/build.sh

# or with sudo-docker / proxy:
DOCKER_CMD='sudo docker' docker/build.sh
HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 docker/build.sh
```

Equivalent manual commands:

```bash
docker build -t ale-blind-dsh docker/blind-dsh
docker build -t ale-blind-dsh-py docker/blind-dsh-py
docker build -t ale-blind-dsh-data docker/blind-dsh-data
```

The runner builds the selected image automatically when it is missing:

```bash
scripts/blind_docker.sh <candidate-id> --build --preflight
scripts/blind_docker.sh --seed <anchor> --data --build
```

If Docker needs the host proxy for base-image pulls:

```ini
# /etc/systemd/system/docker.service.d/http-proxy.conf
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,::1"
```

Then restart Docker. The runner also passes `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` as build args.

## Runtime mounts

Solver container:

```
~/ale-blind/<id>       -> /workspace       rw
host dsh package       -> /opt/dsh         ro
```

The container never mounts the factory, the seed root, `base/reference`, `evidence/`, `verify/`,
`review/`, `exports/`, or `~/.dsh`.

Seed scoring container (`blind_seed_score.py`):

```
<seed root>/<anchor>   -> /seed            ro
~/ale-blind/seed-<anchor> -> /blind        ro
--network none
```

## Image selection

```bash
# text/Node
scripts/blind_docker.sh <id>

# Python/SQLite
scripts/blind_docker.sh <id> --python

# pandas/scipy/openpyxl
scripts/blind_docker.sh <id> --data
```

The seed solver can use the default or `--python` image depending on the seed's software, but the
seed scorer always runs in `ale-blind-dsh-data`.

## Security notes

- `--read-only` root filesystem; `/tmp` is a tmpfs with `exec` (native addons need it).
- `--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit 512`, `--memory 8g`.
- `DEEPSEEK_API_KEY` is passed as an environment variable, not baked into the image or workspace.
- `--network host` is used so the container can reach the host proxy. This also allows external
  `curl` from the model's bash tool; for strict closed-book runs, add an egress allowlist that only
  permits `api.deepseek.com`.
