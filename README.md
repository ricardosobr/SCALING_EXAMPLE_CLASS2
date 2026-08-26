# Simulador de Clúster: Load Balancer & Auto-Scaling Jerárquico

Simulador interactivo de arquitectura de servidores y computación distribuida con interfaz gráfica en **Tkinter**. Permite visualizar y experimentar en tiempo real el comportamiento de un clúster bajo diferentes cargas de tráfico, con un **Balanceador de Carga (Load Balancer)** y un motor de **Autoescalamiento Automático** con calibración en 2 ticks.

---

## 🚀 Inicio Rápido

### Requisitos
- **Python 3.8+** (Tkinter viene incluido por defecto con Python en Windows, macOS y la mayoría de distribuciones Linux).
- En Linux (Debian/Ubuntu/Arch) si no tienes Tkinter instalado:
  ```bash
  sudo apt install python3-tk    # Ubuntu/Debian
  sudo pacman -S tk              # Arch Linux
  ```

### Ejecución
```bash
git clone https://github.com/ricardosobr/SCALING_EXAMPLE_CLASS2.git
cd SCALING_EXAMPLE_CLASS2
python simulador_cluster.py
```

---

## 🎯 Características Principales

1. **Balanceador de Carga (Load Balancer):**
   - Distribuye el tráfico entrante ($req/s$) equitativamente entre los nodos activos (`nodos_activos()`).
   - Tolera fallos en tiempo real: si un nodo cae por sobrecarga, redirige el tráfico a los nodos vivos.

2. **Autoescalamiento Jerárquico (Vertical primero $\rightarrow$ Horizontal después):**
   - **Scale-Up Vertical:** Si la utilización promedio ($U$) $\ge 75\%$ durante **2 segundos sostenidos**, sube el tipo de instancia (L1 $\rightarrow$ L2 $\rightarrow$ ... $\rightarrow$ L5).
   - **Scale-Out Horizontal:** Si el clúster ya está en **Nivel 5** y la utilización persiste en $U \ge 90\%$ durante **2 segundos sostenidos**, agrega nodos adicionales (hasta un máximo de 8).
   - **Calibración en 2 Ticks:** Permite ver visualmente el pico en el Canvas durante el 1er segundo y escala en el 2º segundo, evitando la caída de servidores (que ocurre al 3er segundo de sobrecarga).

3. **Desescalamiento Continuo (Scale-In Horizontal $\rightarrow$ Scale-Down Vertical):**
   - Cuando la carga baja a $U \le 30\%$ durante **10 segundos continuos**:
     - Retira primero los nodos adicionales hasta llegar a la base de 2 nodos.
     - Reduce gradualmente el nivel vertical (L5 $\rightarrow$ L4 $\rightarrow$ ... $\rightarrow$ L1).

4. **Monitoreo y Métricas en Tiempo Real:**
   - Panel lateral con métricas de utilización ($U$), tiempo de respuesta promedio ($RT$), capacidad activa, costo relativo y estado de cooldowns.
   - Canvas interactivo que muestra las barras de carga por nodo, límites de capacidad y umbrales de escalamiento.
   - Registro de eventos (log) con bitácora detallada de síntomas, caídas, reparaciones y escalamientos.

---

## 📊 Niveles de Instancia y Costos

| Nivel | Instancia | Capacidad individual | Costo relativo |
| :--- | :--- | :--- | :--- |
| **L1** | `m5.large` | $50\text{ req/s}$ | $1\times$ |
| **L2** | `m5.xlarge` | $90\text{ req/s}$ | $2\times$ |
| **L3** | `m5.2xlarge` | $150\text{ req/s}$ | $4\times$ |
| **L4** | `m5.4xlarge` | $210\text{ req/s}$ | $8\times$ |
| **L5** | `m5.8xlarge (máx.)` | $260\text{ req/s}$ | $16\times$ |

---

## 📖 Documentación de Arquitectura y Decisiones

Para consultar el análisis detallado de arquitectura, los diagramas de flujo en Mermaid, la justificación de los tiempos de reacción y el caso de estudio de las pruebas:
👉 **[Ver ARQUITECTURA_Y_DISENO.md](ARQUITECTURA_Y_DISENO.md)**

---

## 👥 Equipo
- Ricardo Soberanis ([@ricardosobr](https://github.com/ricardosobr))
