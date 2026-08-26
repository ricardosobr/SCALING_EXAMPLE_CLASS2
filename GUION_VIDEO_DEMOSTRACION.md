# 🎬 Guion de Demostración en Video (2 a 4 Minutos)
### *Proyecto: Simulador de Clúster con Load Balancer y Auto-scaling Jerárquico*
**Participantes:** Ricardo Soberanis y Kevin

---

## ⏱ Estructura del Video (Resumen de Tiempos)

| Minuto | Sección | Acción en Pantalla | Quién habla |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:40** | Introducción y Estado Base | Mostrar simulador con 2 servidores L1 a 70 req/s | Ricardo |
| **0:40 - 1:40** | Simulación del Pico (Preventa de Concierto) | Presionar botón `🎟 Simular Preventa de Concierto` | Kevin |
| **1:40 - 2:40** | Tráfico Masivo y Límite Vertical | Mover slider a 600–800 req/s (Llegar a L5 y +nodos) | Ricardo |
| **2:40 - 3:30** | Fin de la Venta y Desescalado Continuo | Bajar slider a 20 req/s (Ver cómo bajan servidores y niveles) | Kevin |
| **3:30 - 4:00** | Conclusiones y Cierre | Resumen de métricas y despedida | Ambos |

---

## 🎙 Guion Detallado Segundo a Segundo

### [0:00 - 0:40] 1. Introducción y Estado Normal del Clúster
- **Acción en pantalla:** Abrir el simulador con `python simulador_cluster.py`. Mostrar la ventana completa. El tráfico está en **70 req/s**, hay **2 servidores en L1 (m5.large)** y el botón verde dice `🟢 Auto-scaling: ACTIVADO`.
- **Ricardo dice:**
  > *"Hola, buenos días/tardes. En este video vamos a presentar nuestro simulador de clúster con balanceador de carga y autoescalamiento automático. Para esta demostración, tomamos el caso real de una plataforma de venta de boletos como Ticketmaster antes y durante la preventa de un concierto masivo.*
  > *Como pueden ver en la pantalla, en este momento el tráfico es de 70 peticiones por segundo, atendido por dos servidores en Nivel 1. El clúster está en estado verde y saludable, con un tiempo de respuesta de unos 60 milisegundos y costo mínimo."*

---

### [0:40 - 1:40] 2. ¡Inicia la Preventa del Concierto! (Reacción en el 2º Tick)
- **Acción en pantalla:** Kevin presiona el botón **`🎟 Simular Preventa de Concierto (Pico)`**.
- **Kevin dice:**
  > *"Ahora son las 10:00 AM y se abre la preventa de boletos. Presionamos el botón de preventa...*
  > *(Señalar el canvas)* *Miren cómo en el **primer segundo** la carga sube al 150%, las barras se ponen rojas y sube la latencia. Esto le permite al operador ver claramente que entró el pico de tráfico.*
  > *Pero en el **segundo tick**, el autoescalador reacciona automáticamente y sube todos los servidores a **Nivel 2 (m5.xlarge)**. La utilización vuelve a caer a zona segura y el tiempo de respuesta se estabiliza de inmediato en 50 milisegundos.*
  > *Si hubiéramos esperado 5 segundos, los servidores se habrían caído al tercer segundo por timeout, pero al reaccionar en el segundo 2, **cero servidores colapsaron**."*

---

### [1:40 - 2:40] 3. Fila Virtual Masiva (Escalamiento Horizontal en L5)
- **Acción en pantalla:** Ricardo mueve el deslizador de tráfico hacia **700 req/s**.
- **Ricardo dice:**
  > *"¿Pero qué pasa si la demanda es monstruosa y la fila virtual supera la capacidad de una sola máquina?*
  > *Subimos el tráfico a 700 peticiones por segundo. El sistema sigue nuestra regla de decisión estricta:*
  > *1. Primero escala verticalmente agotando las instancias: sube a L3, luego L4 y llega al tope máximo que es **L5 (m5.8xlarge)**.*
  > *2. Una vez que ya está en L5 y la utilización sigue por encima del 90%, el sistema activa el **escalamiento horizontal**, agregando automáticamente un 3er servidor, un 4to y un 5to servidor.*
  > *El Load Balancer distribuye la carga entre todos los nodos activos y la página de boletos sigue funcionando sin caerse."*

---

### [2:40 - 3:30] 4. Boletos Agotados y Desescalamiento Continuo (Ahorro de Costos)
- **Acción en pantalla:** Kevin baja el deslizador de tráfico a **20 req/s**.
- **Kevin dice:**
  > *"Finalmente, los boletos se agotan y la gente abandona la página web. El tráfico cae a 20 peticiones por segundo.*
  > *Aquí entra la regla de **desescalamiento continuo**: para evitar apagar servidores por fluctuaciones cortas, el sistema espera **10 segundos continuos** con menos del 30% de carga.*
  > *Miren la bitácora:*
  > *1. Primero retira los servidores adicionales uno a uno hasta quedar en la base de 2 servidores.*
  > *2. Y una vez que quedan 2 servidores, empieza a bajar el nivel vertical de L5 a L4, luego L3, L2, hasta regresar a L1.*
  > *De esta manera, el costo del servidor regresa a $1\times$, optimizando el presupuesto en la nube."*

---

### [3:30 - 4:00] 5. Conclusiones y Cierre
- **Acción en pantalla:** Mostrar el estado final (2 servidores L1, 🟢 Saludable, log completo).
- **Ricardo dice:**
  > *"En conclusión, logramos un sistema que reacciona con la rapidez suficiente para evitar caídas por timeout en 3 segundos, mantiene una jerarquía limpia de escalamiento vertical antes de horizontal, y optimiza los costos desescalando de regreso automáticamente."*
- **Kevin dice:**
  > *"Todo el código, la arquitectura y este caso de estudio están documentados y disponibles en nuestro repositorio público de GitHub. Muchas gracias."*

---

## 💡 Tips para la Grabación
1. **Resolución recomendada:** 1080p en pantalla completa.
2. **Audio:** Usar micrófono cerca para voz clara.
3. **Cursor del mouse:** Mover el cursor despacio apuntando a:
   - Las barras rojas y verdes del Canvas.
   - El estado del Auto-scaler en el panel derecho.
   - Las líneas de la bitácora cuando dice `Auto-scaling [Scale-Up]` o `Auto-scaling [Scale-Down]`.
