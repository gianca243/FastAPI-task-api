# Handoff — FastAPI task-api (aprendizaje Docker → K8s → AWS)

Última sesión: 2026-11-12. Último commit: `24ed437` (más los cambios de `app/main.py` y `k8s/app.yml` si ya se commitearon).

**Forma de trabajo:** en español, paso a paso, primero el concepto y después el código. Yo implemento; Claude revisa y da pistas (no la solución completa). TDD: primero el test en rojo, verificar que falla **por la razón correcta**, y después el verde.

## Roadmap

| Fase | Tema | Estado |
|---|---|---|
| 1 | App lista para la nube (Settings, `/healthz`, fixes, tests, ruff, reintento BD) | ✅ MVP terminado (quedan pulidos en Pendientes) |
| 2 | Dockerfile + compose (app + db) | ✅ |
| 3 | K8s local con kind (Deployment, Service, ConfigMap, Secret, Ingress, Gateway API, canary) | ✅ (falta solo la parte AWS: ALB) |
| 4 | CI con GitHub Actions | 👉 **siguiente** |
| 5 | Infra AWS con Terraform (EKS, ECR, RDS) | ⏳ (ojo con el costo de EKS: `terraform destroy` al terminar cada sesión) |
| 6 | CD a EKS con GitHub OIDC | ⏳ |
| 7 | Extras (External Secrets, HPA) | ⏳ |

## 👉 Dónde quedamos: fase 4 (CI con GitHub Actions)

**Antes de empezar, cerrar lo que quedó sin commitear (2026-11-12):**
- `app/main.py`: `lifespan` llama a `retry(create_db_and_tables)` y hace `logging.basicConfig(level=logging.INFO)`. Hay una línea con espacios sobrantes (línea 3): pasar `ruff check --fix . && ruff format .`.
- `k8s/app.yml`: imagen `task-api:0.3` (la que lleva el retry).
- Verificar `pytest -q && ruff check . && ruff format --check .` y hacer commit.

**Siguiente: fase 4, CI.** Un workflow de GitHub Actions (`.github/workflows/ci.yml`) que en cada push / PR:
1. Haga checkout y monte Python 3.12.
2. Instale `requirements-dev.txt` (con caché de pip).
3. Corra `ruff check .`, `ruff format --check .` y `pytest -q`.

Pregunta para pensar al retomar: cuando haces `git push`, ¿qué tendría que pasar en GitHub para que tú o un compañero sepan que no rompiste nada, sin ejecutar nada en la máquina local? (conceptos: workflow, trigger `on:`, job, runner, step, `uses:` vs `run:`, badge, branch protection).

## Reintento de conexión a la BD (hecho, 2026-11-12)

**Problema que resuelve:** tras reiniciar la PC, las réplicas arrancaban antes que CoreDNS/Postgres, `create_all` (en el `lifespan`) lanzaba `OperationalError` y el Pod entraba en CrashLoopBackOff.

**Implementación:** `app/utils/retry.py`
```python
def retry(fn, max_attempts=5, base_delay=1.0, sleep=time.sleep):
    # delay = base_delay * 2 ** (attempt - 1) + random.uniform(0, base_delay)
```
- Reintenta **solo** `OperationalError`; en el último intento relanza la **misma** excepción con `raise` a secas (se ve el error real en los logs).
- No espera después del último intento.
- Backoff exponencial (1, 2, 4, 8 con `base_delay=1`) + jitter contra el *thundering herd*.
- `logger.warning("intento %d/%d fallo, reintento en %0.1fs", ...)` (estilo `%`, no f-string).

**Tests** (`tests/test_retry.py`, 16 tests en total en el repo):
- Éxito a la 3ª: devuelve lo mismo que `fn` (`expected = object()` + `is`), `fn` llamado 3 veces.
- Siempre falla: `pytest.raises(...) as excinfo`, `excinfo.value is exc`, `sleep` llamado 4 veces, `fn` 5.
- Esperas con `@pytest.mark.parametrize` sobre `base_delay` (1.0 y 0.5): cada espera en `[backoff, backoff + base_delay]` recorriendo `sleep.call_args_list`.
- Hueco aceptado conscientemente: el test de rangos pasaría también **sin** jitter. Para cerrarlo: inyectar `jitter=random.uniform` y testear con un `Mock(return_value=0.25)`.

**Lecciones de este paso:**
- Un verde no vale si el test no verifica lo importante (`return "ok"` fijo, excepción inventada, `result == result`).
- Mutation testing manual: romper el código a propósito y ver que el test falla; **una mutación a la vez** (si no, la primera tapa a la segunda).
- Un test que solo prueba valores por defecto deja pasar fórmulas incorrectas (`2 ** ((attempt-1) * base_delay)` coincidía con `base_delay=1`).
- `side_effect` con lista se agota (`StopIteration`); con una excepción sola falla siempre.
- `call_args` es solo la **última** llamada; `call_args_list` son todas.
- `assert` dentro de `with pytest.raises` después de la línea que lanza nunca se ejecuta.
- `TestClient` sin `lifespan` no ejecuta el arranque: el import roto (`from app.utils import retry` → módulo) solo se vio al encender la app.
- `pytest -s` muestra los `print`; `-rP` muestra salida de tests que pasan.

**Probado de verdad:**
- Compose: `docker compose -f docker/docker-compose.yml up --build --no-deps fast_api_app` (`--no-deps` salta el `depends_on`). Sin Postgres: 4 WARNING y se rinde con el error real. Levantando `postgres_test_server` a mitad: arranca normal.
- kind: `kubectl scale deployment postgres --replicas=0` → `kubectl rollout restart deployment/task-api` → logs del Pod **nuevo** (`kubectl logs -f <pod>`; `logs deployment/...` elige uno viejo) → `scale --replicas=1`. Conectó en el 5º intento con RESTARTS 0 (ventana justa: ~17 s).
- Visto también: sin Postgres, el Pod nuevo entra en CrashLoopBackOff (backoff de Kubernetes hasta 5 min) y el rolling update mantiene vivos los Pods viejos porque el nuevo nunca está Ready.

## Qué hay hecho

**App / fase 1**
- `GET /healthz` → `{"status": "ok", "version": "0.2"}`, sin consultar la BD (la liveness no depende de nada externo).
- ruff (`E, F, I, B, UP`, línea 100) configurado en `pyproject.toml`. `B008` resuelto con `Annotated`.
- pytest: en `tests/conftest.py` se usa SQLite en memoria con `StaticPool` y se sobrescribe `get_session` con `dependency_overrides`. 12 tests en `tests/test_api.py` + 4 en `tests/test_retry.py` (16 en total).
- Reintento de conexión a la BD al arrancar: `app/utils/retry.py`, usado en el `lifespan` (detalle arriba).
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
- `app.yml` → Deployment `task-api` (2 réplicas, imagen `task-api:0.3` = con retry, readiness + liveness en `/healthz`) + Service `task-api` (80 → 8000).
- `app-v2.yml` → Deployment + Service `task-api-v2` (imagen `task-api:0.2`), para el canary.
- `ingress.yml` → Ingress con clase `cloud-provider-kind`, `/` → `task-api:80`. Pendiente decidir si se borra; la recomendación es quedarse con Gateway API.
- `gateway.yml` → `Gateway task-api-gateway` + `HTTPRoute task-api` con pesos 90/10 entre `task-api` y `task-api-v2` (con 100 curl se midió 88/12).

## 🖥️ Configurar el PC nuevo (desde cero)

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
docker build -t task-api:0.3 . && kind load docker-image task-api:0.3 --name lab   # la que usa app.yml
docker tag task-api:0.3 task-api:0.2 && kind load docker-image task-api:0.2 --name lab   # para el canary (app-v2.yml)
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
# Con la imagen 0.3 (retry) ya no deberían quedar en CrashLoopBackOff tras reiniciar la PC.
# Si Postgres tarda más de ~17 s, igual pueden reiniciarse una vez y recuperarse solos.
# Ojo: Postgres sin volumen → tras reiniciarlo la BD queda vacía; reiniciar la app recrea las tablas.

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
- Logs duplicados de uvicorn (`INFO:uvicorn.error:...`): `basicConfig` configura el logger raíz y los mensajes de uvicorn propagan a él. Configurar solo `logging.getLogger("app")` (nivel + handler) en vez del raíz.
- Quitar los `print("it begins")` / `print("byee!")` del `lifespan` (usar el logger).
- Retry: ventana actual ~17 s, justa para Postgres en kind. Opcional: `max_delay` (tope por espera) + más intentos, con su ciclo TDD; y/o inyectar `jitter` para probar que el azar existe.
- `Task.id` / `User.id` → `int | None = Field(default=None, primary_key=True)`.
- Limpiar respuestas de relleno (`{"omg": 1, ...}` en `create_task`; hay un test que hace assert sobre `"omg"`).
- Restricción `unique=True` en `User.name`. La verificación actual tiene una carrera; requiere migración.
- Alembic para las migraciones, corriéndolas una sola vez (compose: servicio `migrate` + `service_completed_successfully`; K8s: `initContainer` o `Job`).
- Llamadas síncronas a la BD dentro de `async def`.
- `passlib` sin mantenimiento (warning de `crypt`, se rompe en Python 3.13): reemplazar por `bcrypt` directo o `pwdlib`.
- Limpieza: agregar `.gitattributes` (`* text=auto eol=lf`).
- Opcional: `GET /task/{id}` (feature nueva, con su propio ciclo TDD).

**Ideas para más adelante**
- Postgres en K8s → StatefulSet + PVC (o RDS en AWS).
- `/readyz` que consulte la BD: en la prueba, los Pods viejos siguieron `1/1` sin Postgres (porque `/healthz` no mira la BD) pero habrían respondido 500.
- `startupProbe`: si se alargan los reintentos más allá de ~30 s, la liveness actual (10 s × 3) mataría el Pod a mitad del arranque.
- Degradación elegante: `503` claro cuando la BD no está; escrituras encoladas en SQS (fase AWS).
- Canary: ejercicio de promote/rollback cambiando los pesos.
