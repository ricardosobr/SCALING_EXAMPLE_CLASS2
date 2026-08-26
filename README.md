# 💻 Simulador de Clúster: Load Balancer & Auto-Scaling Jerárquico

> **Simulador interactivo y didáctico de computación en la nube y arquitectura de servidores.**  
> Diseñado para experimentar y visualizar en tiempo real cómo funcionan los sistemas distribuidos y las políticas de autoescalamiento.

---

## 🍕 ¿Cómo entender esto de forma simple? (La Analogía de la Pizzería)

Imagina una pizzería que atiende pedidos en línea:

```
🍕 Tráfico (req/s)          = Clientes pidiendo pizzas por segundo
👨‍🍳 Load Balancer (Cajero)  = Quien reparte las comandas de forma pareja entre los hornos
🔥 Servidores (Nodos)       = Los hornos de pizza disponibles
⚡ Nivel de Instancia (L1-L5)= El tamaño y potencia del horno
```

- **Escalamiento Vertical (Subir de nivel L1 $\rightarrow$ L5):**  
  *Cambias tu horno pequeño por un superhorno industrial.* Ocupa el mismo espacio en tu cocina, pero llega un punto en que no existe un horno más grande en el mercado (Tope Nivel 5).
- **Escalamiento Horizontal (Añadir servidores 2 $\rightarrow$ 8):**  
  *Compras más hornos y los pones en batería.* Puedes crecer casi sin límite, pero necesitas que el cajero (**Load Balancer**) reparta los pedidos para que ningún horno se queme solo.
- **Desescalamiento Continuo (Scale-In $\rightarrow$ Scale-Down):**  
  *Cuando los clientes se van:* primero apagas y guardas los hornos extras que gastan gas innecesariamente (**Scale-In**), y cuando solo te quedan tus 2 hornos base, los bajas a fuego mínimo (**Scale-Down**) para no pagar de más en el recibo de energía.

---

## 🚀 Inicio Rápido (Cómo Ejecutarlo)

### Requisitos
- **Python 3.8 o superior** (Tkinter ya viene incluido por defecto en Windows, macOS y la mayoría de distribuciones Linux).
- En Linux (si no tienes Tkinter instalado):
  ```bash
  sudo apt install python3-tk    # Ubuntu/Debian
  sudo pacman -S tk              # Arch Linux
  ```

### Clonar y Ejecutar
```bash
# 1. Clonar el repositorio
git clone https://github.com/ricardosobr/SCALING_EXAMPLE_CLASS2.git

# 2. Entrar a la carpeta
cd SCALING_EXAMPLE_CLASS2

# 3. Iniciar el simulador
python simulador_cluster.py
```

---

## 🎮 Controles y Elementos del Simulador

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [ Slider de Tráfico ]  [ 🎟 Simular Preventa ]  [ 🟢 Auto-scaling: ACTIVADO (Toggle) ] │
├────────────────────────────────────────┬───────────────────────────────────────────────┤
│                                        │ 📊 Panel de Métricas:                         │
│   CANVAS VISUAL DE SERVIDORES          │ • Estado: 🟢 Saludable / 🔴 Crítico           │
│                                        │ • Utilización Promedio (U): 65%               │
│   [ Servidor 1 ]      [ Servidor 2 ]   │ • Nivel: L1 (m5.large) | Costo: x1            │
│   ┌────────────┐      ┌────────────┐   │ • Tiempo de respuesta: 55 ms                  │
│   │    70%     │      │    70%     │   ├───────────────────────────────────────────────┤
│   │   Verde    │      │   Verde    │   │ 📝 Bitácora en Vivo:                          │
│   └────────────┘      └────────────┘   │ • [10:00:02] Auto-scaling [Scale-Up] -> L2    │
└────────────────────────────────────────┴───────────────────────────────────────────────┘
```

1. **Botón de Auto-scaling (`🟢 ACTIVADO` / `🔴 APAGADO`):**  
   Permite alternar entre el modo automático (el robot toma decisiones de escalado) y el modo manual (tú controlas el clúster con los botones).
2. **Botón `🎟 Simular Preventa de Concierto`:**  
   Inyecta un pico masivo repentino ($2.5\times$) para ver en vivo cómo el sistema rescata la plataforma web antes de que se caiga.
3. **La Regla de los 2 Ticks (Calibración Óptima):**
   - **Tick 1 (Segundo 1):** Las barras de los servidores suben a rojo ($U > 100\%$) y la latencia aumenta. Esto permite al usuario ver con claridad que el tráfico aumentó.
   - **Tick 2 (Segundo 2):** El autoescalador reacciona y sube de nivel automáticamente, rescatando los servidores **antes del 3er segundo** (que es cuando colapsan por timeout).

---

## 📊 Niveles de Servidor y Costos

| Nivel | Tipo de Instancia | Capacidad por Servidor | Costo Relativo |
| :--- | :--- | :--- | :--- |
| **L1** | `m5.large` | $50\text{ peticiones/seg}$ | $1\times$ |
| **L2** | `m5.xlarge` | $90\text{ peticiones/seg}$ | $2\times$ |
| **L3** | `m5.2xlarge` | $150\text{ peticiones/seg}$ | $4\times$ |
| **L4** | `m5.4xlarge` | $210\text{ peticiones/seg}$ | $8\times$ |
| **L5** | `m5.8xlarge (Tope)` | $260\text{ peticiones/seg}$ | $16\times$ |

---

## 📚 Documentación Técnica del Proyecto

- 📖 **[ARQUITECTURA_Y_DISENO.md](ARQUITECTURA_Y_DISENO.md):** Diagramas de flujo en Mermaid, diseño de la máquina de estados, calibración temporal en 2 ticks y justificación técnica.
- 🎟 **[CASO_DE_ESTUDIO_CONCIERTO.md](CASO_DE_ESTUDIO_CONCIERTO.md):** Caso de estudio completo de preventa de boletos (tráfico simulado, decisiones automáticas y tablas de métricas de rendimiento).
