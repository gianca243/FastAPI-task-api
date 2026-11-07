# Handoff — FastAPI task-api (aprendizaje Docker → K8s → AWS)

Última sesión: 2026-11-06. Último commit: `07d7d69`.

**Forma de trabajo:** en español, paso a paso, primero el concepto y después el código. Yo implemento; Claude revisa y da pistas (no la solución completa). TDD: primero el test en rojo, verificar que falla **por la razón correcta**, y después el verde.

## Roadmap

| Fase | Tema | Estado |
|---|---|---|
| 1 | App lista para la nube (Settings, `/healthz`, fixes, tests, ruff) | 🟡 MVP casi listo: falta el **reintento de conexión a la BD** |
| 2 | Dockerfile + compose (app + db) | ✅ |
| 3 | K8s local con kind (Deployment, Service, ConfigMap, Secret, Ingress, Gateway API, canary) | ✅ (falta solo la parte AWS: ALB) |
| 4 | CI con GitHub Actions | ⏳ **siguiente después del reintento** |
| 5 | Infra AWS con Terraform (EKS, ECR, RDS) | ⏳ (ojo con el costo de EKS: `terraform destroy` al terminar cada sesión) |
| 6 | CD a EKS con GitHub OIDC | ⏳ |
| 7 | Extras (External Secrets, HPA) | ⏳ |

## 👉 Dónde quedamos: reintento de conexión a la BD (TDD)

**Problema:** tras reiniciar la PC, las réplicas arrancaban antes que CoreDNS. `postgres-service` no resolvía, `create_all` (en el `lifespan`) lanzaba `OperationalError`, el proceso moría y el Pod entraba en CrashLoopBackOff. `create_engine` es perezoso: la primera conexión real ocurre en `create_all`. `pool_pre_ping` no ayuda en el arranque: sirve para conexiones que mueren mientras la app corre.

**Diseño acordado:** una función genérica, en `app/db.py` o `app/utils.py`:
```python
def retry(fn, max_attempts=5, base_delay=1.0, sleep=time.sleep): ...
```
- Máximo de intentos; si se agotan, **relanza** la excepción (que el orquestador vea la falla).
- Backoff exponencial (1, 2, 4, 8…) más **jitter**, contra el *thundering herd*.
- Reintenta **solo** `sqlalchemy.exc.OperationalError`.
- Loguea cada intento, por ejemplo "intento 2/5, reintento en 2.3s".
- `sleep` se inyecta para que los tests no esperen de verdad (inyección de dependencias).

**Tarea pendiente (rojo primero):** crear `tests/test_retry.py` con estos tests:
1. Falla 2 veces y a la 3ª funciona: no lanza, y `fn` se llamó 3 veces.
2. Siempre falla: relanza la excepción tras `max_attempts` (`pytest.raises`).
3. Con un `sleep` falso, las esperas crecen.
4. *(opcional)* Un `ValueError` no se reintenta: 1 sola llamada.

Pistas:
- `unittest.mock.Mock(side_effect=[exc, exc, None])`.
- `OperationalError("stmt", {}, Exception("boom"))`.

**Después:** implementar `retry`, conectarlo en el `lifespan` (`retry(create_db_and_tables)`), probarlo de verdad apagando Postgres en compose, y hacer commit. Luego viene la **fase 4 (CI)**: el pipeline correrá `pytest -q && ruff check . && ruff format --check .`.

## Qué hay hecho

**App / fase 1**
- `GET /healthz` → `{"status": "ok", "version": "0.2"}`, sin consultar la BD (la liveness no depende de nada externo).
- ruff (`E, F, I, B, UP`, línea 100) configurado en `pyproject.toml`. `B008` resuelto con `Annotated`.
- pytest: en `tests/conftest.py` se usa SQLite en memoria con `StaticPool` y se sobrescribe `get_session` con `dependency_overrides`. 12 tests en `tests/test_api.py`.
- Bugs arreglados con TDD:
  - `/signup` ya no devuelve el hash, y responde `409` si el usuario está duplicado.
  - `check_jwt` captura `jwt.InvalidTokenError` (antes, un token malformado daba 500).
  - Task `PUT`/`DELETE`: `404` si la tarea no existe **o es de otro usuario**. Se eligió `404` y no `403` para no revelar qué ids existen (IDOR).
  - `PUT /task` recibe `TaskPutModel` (`id`, `name`, `duration`) en vez del modelo de tabla. Evita el *mass assignment* de `user_id`.
  - `TaskModel` ya no pide `user_id`: se toma del token.
- Lecciones de testing:
  - Un test que pasa a la primera es sospechoso.
  - Cada paso del setup se verifica con `assert`.
  - Un test debe fallar por una sola razón.
  - Si arreglaste antes de escribir el test, verifica el rojo con `git stash push <archivo>` → `pytest` → `git stash pop`.

**Docker (fase 2)**
- `Dockerfile` (raíz): `python:3.12-slim`, requirements antes que el código (caché), usuario `appuser`, `fastapi run`.
- `.dockerignore`: excluye `.env`, `.venv`, `.git`, `docker/database`, `local_run`, `**/__pycache__`, `**/*.pyc`.
- `docker/docker-compose.yml`:
  - `fast_api_app`: build `..`, `POSTGRES_HOST=postgres_test_server`, puerto 5432.
  - `postgres_test_server`: puerto 8081 en el host.
  - Ambos con healthcheck; la app espera con `condition: service_healthy`.

**Kubernetes (`k8s/`)**, clúster kind `lab`, namespace `default`
- `configmap.yml` → `task-api-config`.
- Secret `task-api-secret` (`POSTGRES_PASSWORD`, `SECRET`): **creado por comando, no está en git** (a propósito).
- `postgres.yml` → Deployment `postgres` + Service `postgres-service`. ⚠️ Sin volumen: los datos se pierden si el Pod se recrea.
- `app.yml` → Deployment `task-api` (2 réplicas, imagen `task-api:0.1`, readiness + liveness en `/healthz`) + Service `task-api` (80 → 8000).
- `app-v2.yml` → Deployment + Service `task-api-v2` (imagen `task-api:0.2`), para el canary.
- `ingress.yml` → Ingress con clase `cloud-provider-kind`, `/` → `task-api:80`. Pendiente decidir si se borra; la recomendación es quedarse con Gateway API.
- `gateway.yml` → `Gateway task-api-gateway` + `HTTPRoute task-api` con pesos 90/10 entre `task-api` y `task-api-v2` (con 100 curl se midió 88/12).

## 🖥️ Configurar el PC nuevo (desde cero)

> ⚠️ **Este `handoff.md` no está en git** (está untracked). Cópialo a mano al otro PC o haz commit (decisión pendiente).

```bash
# En WSL (Ubuntu), NO en la carpeta de Windows
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/gianca243/FastAPI-task-api.git
cd FastAPI-task-api

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest -q && ruff check . && ruff format --check .   # todo debe estar en verde
```

**`.env` (no está en git; hay que crearlo a mano en la raíz).** Variables:
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_HOST=localhost
POSTGRES_PORT=8081
POSTGRES_DB=postgres
ACCESS_TOKEN_EXPIRE_MINUTES=30
SECRET=...
```
Los tests **no** necesitan `.env`: `conftest.py` pone valores de prueba. El `.env` es necesario para compose y para correr la app localmente.

**Herramientas** (solo para compose y K8s, no para el reintento ni los tests):
- Docker Desktop con integración WSL activada.
- `kind` y `kubectl` instalados **en WSL** (binarios Linux en `/usr/local/bin`), no las versiones de Windows.

**Recrear el clúster kind** (si se va a usar K8s en el PC nuevo):
```bash
kind create cluster --name lab
docker build -t task-api:0.1 . && kind load docker-image task-api:0.1 --name lab
docker build -t task-api:0.2 . && kind load docker-image task-api:0.2 --name lab   # para el canary
kubectl apply -f k8s/configmap.yml
kubectl create secret generic task-api-secret \
  --from-literal=POSTGRES_PASSWORD='...' --from-literal=SECRET='...'
kubectl apply -f k8s/postgres.yml -f k8s/app.yml

# Ingress / Gateway API: cloud-provider-kind como contenedor en la red kind
docker run -d --name cloud-provider-kind --restart unless-stopped --network kind \
  -v /var/run/docker.sock:/var/run/docker.sock \
  registry.k8s.io/cloud-provider-kind/cloud-controller-manager:v0.12.0
kubectl apply -f k8s/app-v2.yml -f k8s/gateway.yml
docker ps | grep kindccm-gw        # el Envoy del Gateway
docker port <contenedor-kindccm-gw> 80   # puerto aleatorio en localhost
```

## Cómo retomar (en el PC original, con el clúster ya creado)

```bash
kubectl config current-context        # kind-lab
kubectl get pods                      # postgres + task-api en 1/1
# Si están en CrashLoopBackOff tras reiniciar la PC, esperar: se recuperan solos (es justo lo que arregla el reintento).

kubectl port-forward --address 0.0.0.0 svc/task-api 8080:80   # → http://localhost:8080/docs
```
Compose (fuera de K8s): `docker compose -f docker/docker-compose.yml up --build` (el `-f` va **antes** de `up`).

## Particularidades del entorno (WSL)

- Trabajar **solo** en WSL (`~/projects/FastAPI-task-api`).
- `kubectl port-forward` sin `--address 0.0.0.0` no es accesible desde el navegador de Windows (con curl desde WSL sí funciona).
- Desde la terminal de Claude no hay acceso al socket de Docker ni contexto de kubectl: hay que pegarle la salida de los comandos. Sí puede correr `pytest` y `ruff` con `.venv/bin/...`.
- Cada vez que cambie el código: nueva etiqueta (`0.3`, …), `kind load ... --name lab` (es el nombre del **clúster**, no del nodo) y actualizar `image:`. Nunca usar `:latest`.
- cloud-provider-kind: el binario de WSL no funciona (Envoy no llega a su xDS); usar el contenedor. El error repetido `failed to set up tunnels ... Operation not permitted` se puede ignorar.
- ingress-nginx se retiró en marzo de 2026: no usarlo.

## Pendientes

**Fase 1**
- 👉 Reintento de conexión a la BD (en curso, ver arriba).
- `Task.id` / `User.id` → `int | None = Field(default=None, primary_key=True)`.
- Limpiar respuestas de relleno (`{"omg": 1, ...}` en `create_task`; hay un test que hace assert sobre `"omg"`).
- Restricción `unique=True` en `User.name`. La verificación actual tiene una carrera; requiere migración.
- Alembic para las migraciones, corriéndolas una sola vez (compose: servicio `migrate` + `service_completed_successfully`; K8s: `initContainer` o `Job`).
- Llamadas síncronas a la BD dentro de `async def`.
- `passlib` sin mantenimiento (warning de `crypt`, se rompe en Python 3.13): reemplazar por `bcrypt` directo o `pwdlib`.
- Limpieza: `# import uvicorn` en `app/main.py`; usar `logging` en vez de `print`; agregar `.gitattributes` (`* text=auto eol=lf`).
- Opcional: `GET /task/{id}` (feature nueva, con su propio ciclo TDD).

**Ideas para más adelante**
- Postgres en K8s → StatefulSet + PVC (o RDS en AWS).
- Readiness vs liveness: decidir si hace falta un `/readyz`. Evaluar un `startupProbe` junto con el reintento.
- Degradación elegante: `503` claro cuando la BD no está; escrituras encoladas en SQS (fase AWS).
- Canary: ejercicio de promote/rollback cambiando los pesos.
