# 🎟 Caso de Estudio: Preventa de Boletos de un Concierto Masivo
### *Simulación de Tráfico, Decisiones de Auto-scaling y Métricas de Rendimiento en Tiempo Real*

---

## 1. Contexto del Problema y Escenario de Negocio

Imagina que administras la plataforma web de venta de boletos para un concierto masivo (ej. *Coldplay, Taylor Swift o Bad Bunny* en Ticketmaster / Superboletos).

En un día normal, el sitio web recibe visitas casuales de personas revisando horarios o precios. Sin embargo, a las **10:00 AM en punto**, se abre la **preventa exclusiva**:
- Cientos de miles de fanáticos ingresan al mismo segundo a la página web y a la fila virtual.
- El tráfico se multiplica de forma instantánea entre **$2.5\times$ y $8\times$**.
- Si los servidores no reaccionan a tiempo, la página colapsa (*"Error 504 Gateway Timeout"*), los fanáticos no pueden comprar sus boletos y la empresa sufre pérdidas millonarias y daño a su reputación.

El objetivo de este caso de estudio es demostrar cómo el **Load Balancer** y el motor de **Autoescalamiento Jerárquico** protegen el servicio de forma $100\%$ automática.

---

## 2. ¿Qué Tráfico se Simuló? (Fases de la Prueba)

La simulación se dividió en tres fases consecutivas:

```
Tráfico (req/s)
   ▲
800│                                    ┌────────────────┐ (Pico Extremo: Fila Masiva)
   │                                    │                │
250│                 ┌────────────────┐ │                │ (Pico Preventa Inicial)
   │                 │                │ │                │
 70│ ────────────────┘ (Tráfico Base) └─┘                └───────────────── (Fin de Venta)
 20│                                                                       └─── (Madrugada)
   └─────────────────────────────────────────────────────────────────────────────► Tiempo
     [ Fase 1: Base ]   [ Fase 2: Preventa ]     [ Fase 3: Fila Masiva ]   [ Fase 4: Retorno ]
```

1. **Fase 1 · Tráfico Base Pre-Venta ($70\text{ req/s}$):**
   - Navegación habitual antes de las 10:00 AM.
   - El clúster opera con su capacidad mínima: **2 servidores en Nivel 1 (L1 - m5.large)**.
   - Capacidad total: $100\text{ req/s}$. Utilización promedio: $U \approx 70\%$.

2. **Fase 2 · Inicio de la Preventa ($175 - 250\text{ req/s}$):**
   - Se abre la venta a las 10:00 AM. El tráfico sube repentinamente $2.5\times$ durante varios segundos.
   - La carga sobrepasa la capacidad del clúster ($U = 175\% - 250\%$).

3. **Fase 3 · Saturación Extrema ($600 - 800\text{ req/s}$):**
   - Concurrencia masiva de usuarios en cola virtual que supera la capacidad de servidores individuales.

4. **Fase 4 · Boletos Agotados / Fin de Preventa ($20\text{ req/s}$):**
   - Los boletos se terminan, los usuarios abandonan el sitio y el tráfico cae a niveles mínimos.

---

## 3. ¿Qué Decisiones Tomó el Sistema Automáticamente?

El motor de autoescalamiento aplicó la **jerarquía de 2 Ticks**:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                  SECUENCIA DE DECISIONES DEL AUTO-SCALER                   │
└────────────────────────────────────────────────────────────────────────────┘

 1. TICK 1 (Percepción Visual):
    • El pico entra. La barra sube a >100% (rojo). Latencia sube a >250 ms.
    • El sistema detecta U >= 75% pero ESPERA 1 segundo para confirmar carga real.

 2. TICK 2 (Scale-Up Vertical 1):
    • 2 segundos continuos confirmados.
    • DECISIÓN: Escalar Verticalmente (+1 nivel).
    • ACCIÓN: Nodos suben de L1 a L2 (m5.xlarge). Capacidad sube de 100 a 180 req/s.
    • RESULTADO: Carga baja inmediatamente de 175% a 84%. 0 caídas.

 3. TICK 4 (Scale-Up Vertical 2 - si la carga sigue alta):
    • Si el tráfico sigue en 250 req/s, al siguiente ciclo sube a L3 (m5.2xlarge).
    • Capacidad sube a 300 req/s (U baja al 50%).

 4. TICK 8-12 (Scale-Out Horizontal - ante tráfico masivo > 600 req/s):
    • El clúster alcanza el tope vertical (L5 - m5.8xlarge, 520 req/s).
    • Como U >= 90% en L5 por 2s:
    • DECISIÓN: Escalar Horizontalmente (+1 servidor réplica).
    • ACCIÓN: Añade Servidor 3, Servidor 4, Servidor 5... (hasta 8 servidores).

 5. FASE DE RETORNO (Scale-In Continuo tras fin de preventa):
    • El tráfico cae a 20 req/s (U <= 30% sostenido por 10s).
    • DECISIÓN: Desescalar ordenadamente para ahorrar costos.
    • ACCIÓN 1: Retira servidores adicionales (5 -> 4 -> 3 -> 2 servidores).
    • ACCIÓN 2: Reduce nivel vertical en los 2 servidores base (L5 -> L4 -> L3 -> L2 -> L1).
```

---

## 4. Resultados Medibles: Tiempos de Respuesta y Costos

### Tabla Comparativa de Rendimiento

| Métrica | 🔴 SIN Auto-scaling (Modo Manual fijo en L1) | 🟢 CON Auto-scaling Jerárquico |
| :--- | :--- | :--- |
| **Tiempo de respuesta en el pico** | **`3000 ms (TIMEOUT)`** | **`55 - 75 ms (Saludable)`** |
| **Estado de los servidores** | **`CAÍDA TOTAL (Servidores muertos)`** | **`100% Vivos (0 caídas)`** |
| **Tráfico no atendido (pérdidas)** | **`150+ req/s perdidas`** | **`0 req/s (100% atendido)`** |
| **Costo en horas de poco tráfico** | $1\times$ (pero el sistema colapsa en picos) | **$1\times$ (Optimizado automáticamente)** |
| **Costo durante el concierto** | Incalculable (pérdida de ventas) | **$2\times - 8\times$ (solo mientras dura el pico)** |

---

## 5. Conclusiones y Lecciones de Arquitectura

1. **La regla de los 2 ticks es el punto óptimo:**
   - Si se escala en el **segundo 1**, la UI no permite ver el pico.
   - Si se espera al **segundo 5**, los servidores colapsan al segundo 3 por timeouts acumulados.
   - Reaccionar en el **segundo 2** garantiza visibilidad y salva los servidores antes del colapso.
2. **Escalar Vertical primero ahorra complejidad:**
   - Mantener 2 servidores más potentes (L2, L3) es más eficiente y rápido que gestionar 6 o 7 IPs distintas en la red.
3. **Desescalar en 10 segundos evita el "Efecto Flapping":**
   - Si un usuario refresca la página, el sistema no se vuelve loco subiendo y bajando; espera 10 segundos continuos de tranquilidad antes de apagar servidores para ahorrar dinero.
