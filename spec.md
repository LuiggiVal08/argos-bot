# DOCUMENTO DE ESPECIFICACIÓN TÉCNICA (SPEC V4.1)

## PROYECTO: BOT DE TRADING AUTÓNOMO DE GRADO DE PRODUCCIÓNOB
---

## 1. Arquitectura del Sistema e Infraestructura

El sistema se diseña bajo una arquitectura de microservicios orientada a eventos, **agnóstica al modelo de deployment** (contenedores Docker, bare metal en Linux/WSL2/macOS/Windows nativo son todos soportados de primera clase), aislando el procesamiento de alta concurrencia I/O del cómputo intensivo de datos, la IA y el motor de riesgo coercitivo.

### 1.0 Principios de Agnosticismo de Infraestructura

* **Agnosticismo de broker:** el código de aplicación no se acopla a un broker específico. Usa un `MessageBus` port (interface). El adapter concreto (`RedisProtocolBus` u otro) implementa contra cualquier broker compatible con el protocolo RESP. Esto cubre: Redis 7+, Memurai, Dragonfly, Valkey, KeyDB, Garnet, Redict. Cambiar de broker no requiere reescribir lógica de negocio.
* **Agnosticismo de deployment:** `docker-compose.yml` es una de las opciones soportadas, no la única. El stack puede correr bare metal con `node` y `python` nativos, con cualquier broker RESP instalado a nivel de sistema operativo. La elección entre Docker y bare metal es operacional, no arquitectónica.
* **Agnosticismo de OS:** paths via `path.join` (Node) / `os.path.join` (Python); entry points via `npm run` cross-platform; `.gitattributes` normaliza line endings; PowerShell provisto solo donde aporta valor real.
* **Agnosticismo de exchange:** el adaptador de conectividad al exchange es un `ExchangeGateway` port. Cambiar de Binance a Bybit/OKX/etc. es swap de adapter, no reescritura de caso de uso.

### 1.1 Diagrama de Flujo de Datos e Infraestructura

```
[ Exchange WebSockets ] 
        │ (Mensajes Ticks / Libro de Órdenes en tiempo real)
        ▼
 ┌────────────────────────────────────────────────────────┐
 │ NestJS Container (Motor de Conectividad)               │
 │  └─► Infraestructura: WebSockets Gateways (Binance/etc)│
 │  └─► Aplicación: Sanitizar e Inyectar Ticks            │
 └──────┬─────────────────────────────────────────────────┘
        │ 
        ▼ (Inyección en memoria < 2ms)
 ┌──────────────┐
 │ Redis Stream │ (Broker de Mensajería / Buffer de Contención)
 └──────┬───────┘
        │
        ▼ (Consumo Asíncrono No Bloqueante)      
 ┌────────────────────────────────────────┐       
 │ FastAPI Container (Motor Analítico/IA) │       
 │  └─► Infraestructura: Redis Consumers   │       
 │  └─► Aplicación: ProcesarSeñalIA       │       
 │  └─► Dominio: Modelos IA, Reglas Core  │              
 └──────┬─────────────────────────────────┘              
        │                                         
        ▼ (Validación de Capital, ATR, SL/TP, Circuit Breaker)
 [ Exchange REST API (Vía CCXT) ]
        │
        ▼ (Fase Final Postergada)
 ┌────────────────────────────────────────────────────────┐
 │ Módulo de Telemetría (Fase Final / Sujeto a Revisión)  │
 │  └─► Monitoreo de Estados (Webhooks / Posible Front)   │
 └────────────────────────────────────────────────────────┘

```

### 1.2 Stack Tecnológico, Frameworks y Gobierno de Código

| Contenedor / Servicio | Tecnología Base | Framework Core | Librerías Críticas | Propósito y Gobierno |
| --- | --- | --- | --- | --- |
| **Data Engine** | Node.js v20-alpine | **NestJS** (TypeScript) | `ws`, `ioredis`, `@nestjs/microservices` | Mantenimiento de conexiones persistentes con el Exchange. Código modularizado con inyección de dependencias y tipado estricto. |
| **Analytics & IA Engine** | Python 3.11-slim | **FastAPI** + `asyncio` | `ta`, `pandas`, `numpy`, `tensorflow`/`pytorch` | Ingesta asíncrona, procesamiento del DataFrame y ejecución de modelos predictivos (LSTM/Transformers) sin bloquear hilos de cómputo. |
| **Message Broker** | Cualquier implementación RESP-compatibile (Redis 7+, Memurai, Dragonfly, Valkey, KeyDB, Garnet, Redict) | RESP | Streams / Pub-Sub | Buffer inter-proceso ultrarrápido en memoria para mitigar picos de latencia. La elección del broker concreto es operacional, no arquitectónica: el código consume el `MessageBus` port. |
| **Execution & Risk** | Python (Módulo Interno) | Integrado en FastAPI | `ccxt` (CryptoCurrency eXchange Trading) | Abstracción unificada para interactuar con múltiples exchanges, gestión de órdenes de mercado y reintentos. |
| **Telemetría y UI** | *Por determinar* | *En revisión* | *Postergado* | **Última fase de desarrollo.** Se evaluará si se implementa mediante webhooks asíncronos o se integra un panel Frontend dedicado. |

### 1.3 Patrón de Diseño Interno: Arquitectura Hexagonal (Clean Architecture)

Para asegurar que las reglas del trading y la IA no queden amarradas a un proveedor o exchange específico, ambos microservicios se estructuran internamente en 3 capas estrictas y aisladas:

* **Capa de Dominio (El Core Agnóstico):** Aloja las reglas de negocio puras que nunca cambian si se migra de infraestructura.
* *En Python:* Los pesos y lógicas de los modelos de IA, las fórmulas matemáticas de las estrategias financieras (tendencia/reversión) y las reglas del circuito de parada de emergencia (*Circuit Breaker*).
* *En Node.js:* Las entidades de las órdenes de trading, las validaciones de riesgo previas y las estructuras base (interfaces) de las velas de mercado.


* **Capa de Aplicación (Casos de Uso):** Orquesta el flujo de datos y define las acciones del sistema. Ejemplos: `EjecutarCompraCasoUso`, `CalcularMétricasVelaCasoUso`, `ProcesarSeñalIACasoUso`.
* **Capa de Infraestructura (Adaptadores Exteriores Volátiles):** Contiene las implementaciones técnicas propensas a cambiar. Si el exchange o la base de datos cambian, **solo** se modifica esta capa.
* *Adaptadores NestJS:* El cliente WebSocket que conecta a Binance/Bybit, el cliente inyector de Redis Streams y los controladores para futuras conexiones del Gateway.
* *Adaptadores FastAPI:* La librería `ta`, el entorno de ejecución de TensorFlow/PyTorch y el script consumidor que extrae los datos de Redis en memoria.



---

## 2. Motor de Indicadores Técnicos (Librería `ta` en Python)

A través de la capa de infraestructura (adaptador de Redis), FastAPI recibe los ticks, actualiza un DataFrame de Pandas y ejecuta los indicadores de forma vectorizada:

```python
import ta
import pandas as pd

def calcular_indicadores_tecnicos(df: pd.DataFrame) -> pd.DataFrame:
    # A. EMAs (Tendencia)
    df['ema_12'] = ta.trend.ema_indicator(close=df['close'], window=12)
    df['ema_26'] = ta.trend.ema_indicator(close=df['close'], window=26)
    
    # B. MACD (Impulso)
    df['macd'] = ta.trend.macd(close=df['close'], window_fast=12, window_slow=26)
    df['macd_signal'] = ta.trend.macd_signal(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
    df['macd_diff'] = ta.trend.macd_diff(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
    
    # C. RSI (Fuerza)
    df['rsi'] = ta.momentum.rsi(close=df['close'], window=14)
    
    # D. ATR (Volatilidad - Requerido por el Motor de Riesgo)
    df['atr'] = ta.volatility.average_true_range(high=df['high'], low=df['low'], close=df['close'], window=14)
    
    return df

```

---

## 3. Lógica de Decisiones y Estado del Mercado

El núcleo del Dominio evalúa el estado del DataFrame para conmutar la estrategia:

* **Mercado en Tendencia Fuerte (Estrategia de Tendencia):** Activado ante una separación expansiva entre `ema_12` y `ema_26` junto a un histograma de MACD (`macd_diff`) creciente. El bot busca incorporarse al movimiento a favor de la tendencia macro.
* **Mercado en Rango / Lateralización (Estrategia de Reversión):** Activado si las EMAs se cruzan constantemente de forma plana. El control pasa al RSI: compra en sobreventa extrema ($<30$) y vende en sobrecompra extrema ($>70$).

---

## 4. Gestión de Seguridad y Protocolo ante Incidentes (OWASP)

* **Protección de Datos:** Las credenciales de API y firmas privadas de los exchanges se inyectan en runtime como variables de entorno seguras (`.env` o variables del sistema operativo en deployments bare metal). Está estrictamente prohibido su almacenamiento en duro (*hardcode*) en el código fuente.
* **Estrategia de Reacción (4 Fases de OWASP):**
1. **Identificación:** Monitoreo automatizado con logs estructurados (`winston` en NestJS / `logging` en FastAPI) para detectar anomalías de red o respuestas erróneas del exchange.
2. **Contención:** Ante comportamientos inusuales, el bot cambia su estado de forma inmediata a pasivo, aislando los procesos afectados mediante reglas de red o revocando tokens de acceso.
3. **Erradicación:** Parcheo en caliente del adaptador de infraestructura afectado en el entorno de desarrollo y actualización automática de dependencias vulnerables.
4. **Recuperación:** Despliegue seguro reactivando las operaciones comerciales de manera escalonada. Cuando el deployment es Docker, se aprovechan los `healthchecks` nativos; cuando es bare metal, se usan health endpoints HTTP equivalentes.



---

## 5. Tarjetas de Usuario para Desarrollo (User Stories con Enfoque Hexagonal)

### Épica 1: Arquitectura de Datos y Mensajería en Tiempo Real

#### **Historia de Usuario 1: Canalización de Ticks Asíncrona (NestJS + Redis + FastAPI)**

> **Como** desarrollador del bot,
> **Quiero** implementar un flujo desacoplado donde un Gateway de NestJS envíe datos a Redis Streams y FastAPI los consuma de manera asíncrona,
> **Para** asegurar que el cómputo analítico no degrade la captura de datos del WebSocket.

* **Criterios de Aceptación:**
* **Happy Path:** NestJS (`Infraestructura`) se conecta al WebSocket externo $\rightarrow$ recibe un tick $\rightarrow$ delega al Caso de Uso (`Aplicación`) la sanitización del objeto $\rightarrow$ el adaptador de Redis inyecta la trama en el stream en $<2\text{ ms}$. FastAPI consume el stream usando `asyncio`, actualiza el DataFrame y dispara la lógica de trading sin bloquear la recepción de NestJS.
* **Sad Path:** Si Redis se desconecta, NestJS intercepta la falla en su capa de infraestructura, almacena temporalmente los ticks en un búfer en memoria (máximo 100) y registra el error de forma local. Si la caída persiste por más de 10 segundos, NestJS cierra el WebSocket del exchange ordenadamente para prevenir incoherencias en el histórico de velas.



---

### Épica 2: Motor de Gestión de Riesgo Coercitivo

#### **Historia de Usuario 2: Cálculo Automatizado del Tamaño de la Posición (Dominio de Riesgo)**

> **Como** gestor de riesgo,
> **Quiero** que la capa de Dominio calcule el tamaño de la posición basándose en el balance libre y el ATR,
> **Para** que la pérdida máxima potencial nunca supere el $1\%$ por operación.

* **Criterios de Aceptación:**
* **Happy Path:** Una señal de trading llega al Caso de Uso de FastAPI. El Caso de Uso invoca la entidad del Dominio `CalculadorRiesgo`, pasándole el balance libre (recuperado por el adaptador CCXT) y el ATR actual. El Dominio devuelve la cantidad exacta de unidades a comprar situando el Stop Loss dinámico a una distancia proporcional al ATR.
* **Sad Path:** Si el adaptador de CCXT falla por Timeout de red o devuelve un balance inválido de $0, el Caso de Uso aborta la operación de forma inmediata antes de tocar el exchange y registra un error crítico. Si el tamaño de la posición calculado es inferior al lote mínimo permitido por las reglas de la API de mercado, la señal es descartada con un log de advertencia.



#### **Historia de Usuario 3: Circuito de Parada de Emergencia (Circuit Breaker)**

> **Como** propietario de la cuenta,
> **Quiero** un mecanismo coercitivo que apague el bot si el Drawdown diario alcanza el límite establecido,
> **Para** evitar pérdidas catastróficas en días de alta manipulación de mercado.

* **Criterios de Aceptación:**
* **Happy Path:** El bot opera con normalidad. Al cierre de la jornada UTC, el Caso de Uso verifica que el Drawdown acumulado está en rangos seguros y reinicia los contadores diarios a cero.
* **Sad Path:** Si una operación cierra con pérdidas y el acumulado diario cruza el umbral del $5\%$ (parámetro de Dominio), se dispara el `CircuitBreaker`. El bot invoca de inmediato al adaptador de infraestructura de CCXT, cancela de forma masiva todas las órdenes abiertas, cierra cualquier posición spot/futuro activa a precio de mercado (`Market Order`), reescribe `ENVIRONMENT_MODE=PASIVO` y detiene la marcha comercial registrando el bloqueo.



---

### Épica 3: Ejecución de Órdenes y Resiliencia Financiera

#### **Historia de Usuario 4: Colocación Resiliente de Órdenes con CCXT**

> **Como** motor de ejecución,
> **Quiero** canalizar las órdenes a través de los adaptadores de CCXT utilizando lógica de reintento exponencial,
> **Para** mitigar fallas parciales de red durante ejecuciones críticas de Stop Loss.

* **Criterios de Aceptación:**
* **Happy Path:** El Caso de Uso de ejecución despacha una orden compuesta (Orden de Mercado + Stop Loss/Take Profit vinculados) al adaptador de CCXT. El exchange procesa la solicitud y retorna confirmación con su correspondiente ID de orden en milisegundos.
* **Sad Path:** Si la API del exchange retorna un error de timeout de red al intentar colocar el Stop Loss, el adaptador de infraestructura ejecuta de forma autónoma una política de reintento exponencial (máximo 3 reintentos en una ventana estricta de 500ms). Si todos los reintentos fallan, la capa de aplicación toma el control y envía una orden de emergencia a mercado para liquidar toda la posición inmediatamente y evitar pérdidas descontroladas.



---

### Épica 4: Modos de Operación del Sistema

#### **Historia de Usuario 5: Control de Entornos Seguro (`ENVIRONMENT_MODE`)**

> **Como** analista cuantitativo,
> **Quiero** asegurar que el bot reconfigure sus adaptadores de infraestructura según el entorno de ejecución inyectado,
> **Para** prevenir operaciones reales accidentales.

* **Criterios de Aceptación:**
* **Happy Path:** * `BACKTESTING`: El adaptador de datos de FastAPI conmuta para leer data histórica desde archivos CSV/BD locales, desactiva la red externa y genera métricas de simulación (*Sharpe Ratio*).
* `PAPER_TRADING`: El bot activa los WebSockets reales de NestJS y los streams de Redis, pero el adaptador de ejecución escribe los trades en una base de datos local simulada.
* `LIVE`: Se activan todas las conexiones productivas reales y flujo monetario real.


* **Sad Path:** Si `ENVIRONMENT_MODE=LIVE` pero el módulo de infraestructura detecta que faltan las credenciales cifradas en las variables de entorno o que son cadenas vacías, NestJS and FastAPI abortan el ciclo de inicialización lanzando una excepción fatal y deteniendo el contenedor Docker con un código de salida `1`.



---

### Épica 5: Telemetría y Monitoreo del Sistema (Fase Final Postergada)

#### **Historia de Usuario 6: Integración del Módulo de Monitoreo Operativo**

> **Como** operador,
> **Quiero** que este componente sea el último en construirse dentro del ciclo del proyecto,
> **Para** adaptarlo correctamente dependiendo de si se aprueba el desarrollo de un Frontend o si se opta definitivamente por Webhooks asíncronos (Telegram/Discord).

* **Criterios de Aceptación:**
* **Happy Path:** Una vez consolidados los motores de datos, riesgo y ejecución, se define la vía de salida de telemetría. Si se aprueba el Frontend, NestJS habilitará Gateways internos estructurados para transmitir el estado del balance y operaciones en tiempo real a la UI. Si se descarta, se construirán adaptadores ligeros para despachar eventos estructurados directos hacia APIs de mensajería externa.
* **Sad Path:** Durante su construcción, fallas en la entrega o consumo de payloads de telemetría (sea por caída del Front o saturación de webhooks externos) jamás deberán interferir, bloquear o agregar latencia de hilos al bucle principal del Core de trading e IA de FastAPI.

---

## 6. Invariantes Arquitectónicas (Resumen)

Las siguientes invariantes son **no negociables** y se verifican automáticamente en pre-merge (ver `AGENTS.md` §2 para el detalle completo y las 14 invariantes):

* **#8 HEXAGONAL — Domain:** el Dominio no importa de Application ni Infrastructure.
* **#9 HEXAGONAL — Application:** Application solo importa ports (interfaces), nunca adapters concretos.
* **#10 HEXAGONAL — data-engine ↔ analytics-engine:** la comunicación entre los dos servicios ocurre **únicamente** vía el `MessageBus` (broker RESP-compatibile). Nunca imports directos.
* **#11 STACK LEAKAGE:** `ioredis`/`ws`/`ccxt` solo dentro de `apps/data-engine/src/infrastructure/`. `pandas`/`ta`/`tensorflow` solo dentro de `apps/analytics-engine/app/infrastructure/`.
* **#12 TICK PIPELINE:** inyección al broker en `<2ms` p99 (spec §5 Historia 1).
* **#14 DEPLOYMENT AGNOSTICISM:** el código de aplicación no asume Docker. Hostnames via env vars (`ARGOS_BROKER_URL`, `EXCHANGE_*`), paths via `path.join` / `os.path.join`, broker via `MessageBus` port (no hardcoded a Redis). `docker-compose.yml` es una opción de deploy, no la única. El sistema corre bare metal con el mismo binario.
