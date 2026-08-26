"""
Simulador de Escalamiento de Clúster (Vertical vs Horizontal) con Auto-scaling y Load Balancer
==============================================================================================

Interfaz gráfica educativa e interactiva hecha con Tkinter que simula un clúster de servidores
recibiendo tráfico en tiempo real (ej. Preventa de boletos de un concierto masivo en Ticketmaster).

Incluye:
1. Load Balancer (Balanceador de carga Round-Robin con tolerancia a fallos).
2. Motor de Auto-scaling automático jerárquico con reacción en 2 Ticks:
   - Scale-Up Vertical Primero (L1 a L5) ante sobrecarga (U >= 75% por 2s).
   - Scale-Out Horizontal en Nivel 5 ante sobrecarga extrema (U >= 90% por 2s).
   - Desescalamiento Continuo (Scale-In Horizontal primero -> Scale-Down Vertical después) cuando U <= 30% por 10s.
3. Botón de Toggle Visual de Auto-scaling (Automático vs Manual).
4. Escenario temático: "🎟 Simular Preventa de Concierto".

Ejecutar con:
    python simulador_cluster.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random

# ----------------------------------------------------------------------
# Modelo: niveles de instancia (escalamiento vertical)
# Capacidad sublineal y costo exponencial
# ----------------------------------------------------------------------
CAPACIDAD_POR_NIVEL = {1: 50, 2: 90, 3: 150, 4: 210, 5: 260}
COSTO_POR_NIVEL = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
NOMBRE_POR_NIVEL = {
    1: "m5.large",
    2: "m5.xlarge",
    3: "m5.2xlarge",
    4: "m5.4xlarge",
    5: "m5.8xlarge (máx.)",
}

NIVEL_MINIMO = 1
NIVEL_MAXIMO = 5
NODOS_MINIMOS = 2
NODOS_MAXIMOS = 8
LATENCIA_BASE_MS = 35
TICKS_PARA_CAER = 3          # Ticks seguidos sobrecargado (>=100%) antes de caer
INTERVALO_TICK_MS = 1000      # 1 segundo por tick de simulación

# Parámetros y umbrales de Autoescalado
UMBRAL_UP_VERT = 0.75         # U >= 75%
SEGUNDOS_UP_VERT = 2          # Reacción al 2do segundo (permite visualización en el 1er tick)
COOLDOWN_VERT_SEG = 2         # 2 segundos de enfriamiento

UMBRAL_OUT_HORIZ = 0.90       # U >= 90% (cuando ya está en nivel 5)
SEGUNDOS_OUT_HORIZ = 2        # Reacción al 2do segundo en L5
COOLDOWN_HORIZ_SEG = 2        # 2 segundos de enfriamiento

UMBRAL_IN = 0.30              # U <= 30%
SEGUNDOS_IN = 10              # 10 segundos sostenidos para desescalar


class Nodo:
    """Representa un nodo individual del clúster."""

    def __init__(self, id_, nivel=1):
        self.id = id_
        self.nivel = nivel
        self.caido = False
        self.ticks_sobrecargado = 0
        self.carga_actual = 0.0
        self.tiempo_respuesta = LATENCIA_BASE_MS
        self.categoria_previa = "ok"

    def capacidad(self):
        return CAPACIDAD_POR_NIVEL[self.nivel]

    def utilizacion(self):
        cap = self.capacidad()
        return 0.0 if cap == 0 else self.carga_actual / cap

    def categoria(self):
        if self.caido:
            return "caido"
        u = self.utilizacion()
        if u >= 1.0:
            return "critico"
        if u >= 0.6:
            return "advertencia"
        return "ok"


class SimuladorClusterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador de Clúster: Load Balancer & Auto-Scaling Jerárquico")
        self.root.geometry("1140x720")
        self.root.minsize(1040, 660)

        self.contador_ids = 0
        self.nodos = []
        self.corriendo = True
        self.pico_restante = 0

        # Estado del motor de Autoescalado
        self.autoescalado_activo = True
        self.segundos_sobrecarga_75 = 0
        self.segundos_sobrecarga_90 = 0
        self.segundos_subutilizado_30 = 0
        self.cooldown_vertical = 0
        self.cooldown_horizontal = 0
        self._alerta_limite_max_avisada = False

        self._crear_nodos_iniciales(NODOS_MINIMOS)
        self._construir_interfaz()
        self._reiniciar_estado()

        self.tick()

    # ------------------------------------------------------------------
    # Construcción de nodos
    # ------------------------------------------------------------------
    def _crear_nodos_iniciales(self, cantidad):
        self.nodos = []
        self.contador_ids = 0
        for _ in range(cantidad):
            self.contador_ids += 1
            self.nodos.append(Nodo(self.contador_ids, nivel=NIVEL_MINIMO))

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        # --- Panel superior: controles y comandos ---
        panel_controles = ttk.Frame(self.root, padding=10)
        panel_controles.pack(side=tk.TOP, fill=tk.X)

        # Fila 0: Tráfico y Control de Autoescalado
        frame_fila0 = ttk.Frame(panel_controles)
        frame_fila0.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(frame_fila0, text="Tráfico entrante (peticiones/seg):").pack(side=tk.LEFT, padx=(0, 5))
        self.trafico_var = tk.DoubleVar(value=70)
        self.slider_trafico = ttk.Scale(
            frame_fila0,
            from_=0,
            to=1200,
            variable=self.trafico_var,
            orient=tk.HORIZONTAL,
            length=250,
        )
        self.slider_trafico.pack(side=tk.LEFT, padx=5)

        self.label_trafico_valor = ttk.Label(frame_fila0, text="70 req/s", width=9, font=("TkDefaultFont", 9, "bold"))
        self.label_trafico_valor.pack(side=tk.LEFT, padx=(0, 10))
        self.trafico_var.trace_add("write", self._on_trafico_change)

        ttk.Button(
            frame_fila0, text="🎟 Simular Preventa de Concierto (Pico)", command=self.simular_pico_concierto
        ).pack(side=tk.LEFT, padx=5)

        # Botón Toggle Visual de Auto-scaling
        self.btn_toggle_auto = tk.Button(
            frame_fila0,
            text="🟢 Auto-scaling: ACTIVADO",
            command=self.alternar_autoescalado,
            bg="#1b4d2e",
            fg="#7ee787",
            activebackground="#256e42",
            activeforeground="#ffffff",
            font=("TkDefaultFont", 9, "bold"),
            relief=tk.RAISED,
            padx=10,
            pady=2,
        )
        self.btn_toggle_auto.pack(side=tk.LEFT, padx=12)

        # Fila 1: Botones de control manual y operaciones del clúster
        frame_fila1 = ttk.Frame(panel_controles)
        frame_fila1.pack(fill=tk.X, pady=(2, 0))

        ttk.Label(frame_fila1, text="Acciones manuales:").pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(frame_fila1, text="🔼 Escalar V (+1)", command=self.escalar_vertical).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_fila1, text="🔽 Desescalar V (-1)", command=self.desescalar_vertical).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_fila1, text="➕ Escalar H (+1)", command=self.escalar_horizontal).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_fila1, text="➖ Desescalar H (-1)", command=self.desescalar_horizontal).pack(side=tk.LEFT, padx=3)
        ttk.Button(frame_fila1, text="🛠 Reparar caídos", command=self.reparar_nodos).pack(side=tk.LEFT, padx=6)

        self.btn_pausa = ttk.Button(frame_fila1, text="⏸ Pausar", command=self.alternar_pausa)
        self.btn_pausa.pack(side=tk.LEFT, padx=4)

        ttk.Button(frame_fila1, text="🔄 Reiniciar simulación", command=self.reiniciar_todo).pack(side=tk.LEFT, padx=4)

        # --- Panel central: canvas de nodos ---
        panel_central = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        panel_central.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(
            panel_central,
            text="Clúster de Servidores (Load Balancer distribuye la carga entre nodos activos)",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")

        self.canvas = tk.Canvas(panel_central, bg="#101418", height=450)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- Panel lateral derecho: métricas + log ---
        panel_lateral = ttk.Frame(self.root, padding=(0, 0, 10, 10), width=380)
        panel_lateral.pack(side=tk.RIGHT, fill=tk.Y)
        panel_lateral.pack_propagate(False)

        marco_metricas = ttk.LabelFrame(panel_lateral, text="Estado del clúster y métricas", padding=10)
        marco_metricas.pack(fill=tk.X, pady=(0, 8))

        self.label_estado = ttk.Label(
            marco_metricas, text="🟢 SALUDABLE", font=("TkDefaultFont", 11, "bold")
        )
        self.label_estado.pack(anchor="w")

        self.label_utilizacion = ttk.Label(
            marco_metricas, text="Utilización promedio (U): --%", font=("TkDefaultFont", 10, "bold")
        )
        self.label_utilizacion.pack(anchor="w", pady=(3, 0))

        self.label_auto_info = ttk.Label(
            marco_metricas, text="Auto-scaler: Activo · Estable", foreground="#4caf50", font=("TkDefaultFont", 9, "bold")
        )
        self.label_auto_info.pack(anchor="w", pady=(2, 4))

        self.label_rt = ttk.Label(marco_metricas, text="Tiempo de respuesta promedio: -- ms")
        self.label_rt.pack(anchor="w")

        self.label_nivel = ttk.Label(marco_metricas, text="Nivel vertical: L1 (m5.large)")
        self.label_nivel.pack(anchor="w")

        self.label_costo = ttk.Label(marco_metricas, text="Costo relativo: x1")
        self.label_costo.pack(anchor="w")

        self.label_nodos = ttk.Label(marco_metricas, text="Nodos activos: 2 / 2")
        self.label_nodos.pack(anchor="w")

        self.label_capacidad = ttk.Label(marco_metricas, text="Capacidad total: -- req/s")
        self.label_capacidad.pack(anchor="w")

        self.label_perdida = ttk.Label(marco_metricas, text="Tráfico no atendido: 0 req/s")
        self.label_perdida.pack(anchor="w")

        marco_log = ttk.LabelFrame(panel_lateral, text="Bitácora y explicación de eventos", padding=5)
        marco_log.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(marco_log)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.texto_log = tk.Text(
            marco_log,
            wrap="word",
            height=18,
            yscrollcommand=scrollbar.set,
            bg="#1c1f24",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            state="disabled",
        )
        self.texto_log.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.texto_log.yview)

    # ------------------------------------------------------------------
    # Utilidades de estado y log
    # ------------------------------------------------------------------
    def _reiniciar_estado(self):
        self.pico_restante = 0
        self.trafico_var.set(70)
        self.segundos_sobrecarga_75 = 0
        self.segundos_sobrecarga_90 = 0
        self.segundos_subutilizado_30 = 0
        self.cooldown_vertical = 0
        self.cooldown_horizontal = 0
        self._alerta_limite_max_avisada = False
        self._actualizar_boton_toggle()
        self._limpiar_log()
        self.log(f"Simulación iniciada con {NODOS_MINIMOS} servidores en L1 ({NOMBRE_POR_NIVEL[1]}).")
        self.log("Load Balancer y Auto-scaling activados por defecto.")
        self.log("💡 Tip: Presiona '🎟 Simular Preventa' para ver el pico de concierto en vivo.")

    def _on_trafico_change(self, *_):
        try:
            valor = int(float(self.trafico_var.get()))
        except (tk.TclError, ValueError):
            return
        self.label_trafico_valor.config(text=f"{valor} req/s")

    def alternar_autoescalado(self):
        self.autoescalado_activo = not self.autoescalado_activo
        self._actualizar_boton_toggle()
        if self.autoescalado_activo:
            self.log("🟢 Auto-scaling AUTOMÁTICO activado (el sistema escala solo).")
        else:
            self.log("🔴 Auto-scaling APAGADO (Modo manual: tú controlas el clúster con los botones).")
            self.segundos_sobrecarga_75 = 0
            self.segundos_sobrecarga_90 = 0
            self.segundos_subutilizado_30 = 0

    def _actualizar_boton_toggle(self):
        if self.autoescalado_activo:
            self.btn_toggle_auto.config(
                text="🟢 Auto-scaling: ACTIVADO",
                bg="#1b4d2e",
                fg="#7ee787",
                activebackground="#256e42",
                activeforeground="#ffffff",
            )
        else:
            self.btn_toggle_auto.config(
                text="🔴 Auto-scaling: APAGADO (Manual)",
                bg="#4d1b1b",
                fg="#ff7b72",
                activebackground="#6e2525",
                activeforeground="#ffffff",
            )

    def log(self, mensaje):
        self.texto_log.config(state="normal")
        self.texto_log.insert(tk.END, "• " + mensaje + "\n")
        self.texto_log.see(tk.END)
        self.texto_log.config(state="disabled")

    def _limpiar_log(self):
        self.texto_log.config(state="normal")
        self.texto_log.delete("1.0", tk.END)
        self.texto_log.config(state="disabled")

    def nodos_activos(self):
        return [n for n in self.nodos if not n.caido]

    def utilizacion_promedio(self):
        activos = self.nodos_activos()
        if not activos:
            return 0.0
        return sum(n.utilizacion() for n in activos) / len(activos)

    def tiempo_respuesta_promedio(self):
        activos = [n for n in self.nodos_activos() if n.tiempo_respuesta is not None]
        if not activos:
            return None
        return sum(min(n.tiempo_respuesta, 3000) for n in activos) / len(activos)

    # ------------------------------------------------------------------
    # Bucle principal de simulación
    # ------------------------------------------------------------------
    def tick(self):
        if self.corriendo:
            self._avanzar_estado()
        self.root.after(INTERVALO_TICK_MS, self.tick)

    def _trafico_efectivo(self):
        base = float(self.trafico_var.get())
        if self.pico_restante > 0:
            self.pico_restante -= 1
            return base * 2.5
        return base

    def _avanzar_estado(self):
        self._distribuir_carga()       # 1. Load Balancer reparte tráfico
        self._evaluar_nodos()           # 2. Evaluación de métricas y fallos
        self._evaluar_autoescalado()    # 3. Motor de autoescalado evalúa reglas
        self._actualizar_metricas()     # 4. Actualización de interfaz
        self._dibujar()                 # 5. Renderizado en Canvas

    # ------------------------------------------------------------------
    # 1. Load Balancer (Balanceador de carga)
    # ------------------------------------------------------------------
    def _distribuir_carga(self):
        """Distribuye el tráfico entrante equitativamente entre los nodos activos."""
        trafico = self._trafico_efectivo()
        activos = self.nodos_activos()
        if not activos:
            return
        carga_pareja = trafico / len(activos)
        for n in activos:
            ruido = random.uniform(0.95, 1.05)
            n.carga_actual = max(0.0, carga_pareja * ruido)

    # ------------------------------------------------------------------
    # 2. Evaluación de Nodos y Síntomas
    # ------------------------------------------------------------------
    def _evaluar_nodos(self):
        for n in self.nodos:
            if n.caido:
                continue
            u = n.utilizacion()
            if u < 1.0:
                n.tiempo_respuesta = LATENCIA_BASE_MS / max(0.02, (1 - u))
                n.ticks_sobrecargado = 0
            else:
                n.tiempo_respuesta = 3000  # Timeout simbólico
                n.ticks_sobrecargado += 1

            categoria = n.categoria()
            if categoria != n.categoria_previa:
                if categoria == "critico":
                    self.log(
                        f"⚠️ Nodo {n.id} (L{n.nivel}): sobrecargado al "
                        f"{u * 100:.0f}% — latencia crítica / timeouts."
                    )
                elif categoria == "advertencia":
                    self.log(
                        f"🟡 Nodo {n.id} (L{n.nivel}): uso elevado ({u * 100:.0f}%) — "
                        "latencia en aumento."
                    )
                elif categoria == "ok" and n.categoria_previa in ("advertencia", "critico"):
                    self.log(f"🟢 Nodo {n.id} (L{n.nivel}) volvió a niveles normales.")
            n.categoria_previa = categoria

            if n.ticks_sobrecargado >= TICKS_PARA_CAER and not n.caido:
                n.caido = True
                self.log(
                    f"❌ Nodo {n.id} CAYÓ: 3 segundos continuos sobrecargado provocaron caída por timeout."
                )

        # Chequeo de caída total
        if self.nodos and not self.nodos_activos():
            if not getattr(self, "_ya_avise_caida_total", False):
                self.log("🔴 CAÍDA TOTAL DEL SERVICIO: No queda ningún servidor activo para atender la venta de boletos.")
                self._ya_avise_caida_total = True
        else:
            self._ya_avise_caida_total = False

    def _recalcular_nodos_post_escalado(self):
        """Recalcula latencias y categorías post-escalado sin avanzar ticks de sobrecarga."""
        for n in self.nodos:
            if n.caido:
                continue
            u = n.utilizacion()
            if u < 1.0:
                n.tiempo_respuesta = LATENCIA_BASE_MS / max(0.02, (1 - u))
                n.ticks_sobrecargado = 0
            else:
                n.tiempo_respuesta = 3000

    # ------------------------------------------------------------------
    # 3. Motor de Auto-scaling (Jerarquía Estricta en 2 Ticks)
    # ------------------------------------------------------------------
    def _evaluar_autoescalado(self):
        """Evalúa las reglas de decisión de autoescalamiento jerárquico."""
        if not self.autoescalado_activo:
            return

        activos = self.nodos_activos()
        if not activos:
            return

        # Decrementar cooldowns activos
        if self.cooldown_vertical > 0:
            self.cooldown_vertical -= 1
        if self.cooldown_horizontal > 0:
            self.cooldown_horizontal -= 1

        u = self.utilizacion_promedio()
        nivel_actual = self.nodos[0].nivel if self.nodos else 1
        num_nodos = len(self.nodos)

        # 1. Monitoreo y acumulación de tiempo sostenido
        if u >= UMBRAL_UP_VERT:
            self.segundos_sobrecarga_75 += 1
            self.segundos_subutilizado_30 = 0
            if nivel_actual >= NIVEL_MAXIMO and u >= UMBRAL_OUT_HORIZ:
                self.segundos_sobrecarga_90 += 1
            else:
                self.segundos_sobrecarga_90 = 0
        elif u <= UMBRAL_IN:
            self.segundos_subutilizado_30 += 1
            self.segundos_sobrecarga_75 = 0
            self.segundos_sobrecarga_90 = 0
        else:
            # Zona estable (30% < U < 75%)
            self.segundos_sobrecarga_75 = 0
            self.segundos_sobrecarga_90 = 0
            self.segundos_subutilizado_30 = 0

        # --- A. REGLA SCALE-UP VERTICAL PRIMERO (al 2do tick sostenido >= 75%) ---
        if self.segundos_sobrecarga_75 >= SEGUNDOS_UP_VERT:
            if nivel_actual < NIVEL_MAXIMO:
                if self.cooldown_vertical == 0:
                    self.escalar_vertical(automatico=True)
                    self.cooldown_vertical = COOLDOWN_VERT_SEG
                    self.segundos_sobrecarga_75 = 0
                    self.segundos_sobrecarga_90 = 0
            else:
                # Ya en Nivel 5: evaluar escalamiento HORIZONTAL (al 2do tick sostenido >= 90%)
                if self.segundos_sobrecarga_90 >= SEGUNDOS_OUT_HORIZ:
                    if num_nodos < NODOS_MAXIMOS:
                        if self.cooldown_horizontal == 0:
                            self.escalar_horizontal(automatico=True)
                            self.cooldown_horizontal = COOLDOWN_HORIZ_SEG
                            self.segundos_sobrecarga_75 = 0
                            self.segundos_sobrecarga_90 = 0
                    else:
                        if not self._alerta_limite_max_avisada:
                            self.log("🚨 LÍMITE MÁXIMO ALCANZADO: Nivel 5 con 8 servidores y U >= 90%. Clúster al tope.")
                            self._alerta_limite_max_avisada = True

        # --- B. REGLA DESESCALAMIENTO CONTINUO HACIA ABAJO (al 10mo tick sostenido <= 30%) ---
        if self.segundos_subutilizado_30 >= SEGUNDOS_IN:
            if num_nodos > NODOS_MINIMOS:
                if self.cooldown_horizontal == 0:
                    self.desescalar_horizontal(automatico=True)
                    self.cooldown_horizontal = COOLDOWN_HORIZ_SEG
                    self.segundos_subutilizado_30 = 0
            else:
                # Nodos == 2 (mínimo de redundancia): desescalar verticalmente hacia L1
                if nivel_actual > NIVEL_MINIMO:
                    if self.cooldown_vertical == 0:
                        self.desescalar_vertical(automatico=True)
                        self.cooldown_vertical = COOLDOWN_VERT_SEG
                        self.segundos_subutilizado_30 = 0

    # ------------------------------------------------------------------
    # Métricas y actualización de UI
    # ------------------------------------------------------------------
    def _actualizar_metricas(self):
        activos = self.nodos_activos()
        rt = self.tiempo_respuesta_promedio()
        u = self.utilizacion_promedio()

        if not self.nodos or not activos:
            estado_txt, color = "🔴 CAÍDA TOTAL", "#ff5555"
        elif any(n.caido for n in self.nodos):
            estado_txt, color = "🟠 DEGRADADO (servidor caído)", "#ffb454"
        elif u >= 1.0 or any(n.utilizacion() >= 1.0 for n in activos):
            estado_txt, color = "🔴 CRÍTICO (Sobrecarga)", "#ff5555"
        elif u >= 0.75:
            estado_txt, color = "🟡 ADVERTENCIA (Alta carga)", "#ffd54f"
        else:
            estado_txt, color = "🟢 SALUDABLE", "#7ee787"

        self.label_estado.config(text=estado_txt, foreground=color)
        self.label_utilizacion.config(text=f"Utilización promedio (U): {u * 100:.1f}%")

        # Texto informativo del auto-scaler
        if not self.autoescalado_activo:
            info_auto = "Auto-scaler: 🔴 APAGADO (Modo Manual)"
            color_auto = "#ff7b72"
        elif self.cooldown_vertical > 0:
            info_auto = f"Auto-scaler: ❄ Cooldown Vertical ({self.cooldown_vertical}s)"
            color_auto = "#64b5f6"
        elif self.cooldown_horizontal > 0:
            info_auto = f"Auto-scaler: ❄ Cooldown Horizontal ({self.cooldown_horizontal}s)"
            color_auto = "#64b5f6"
        elif self.segundos_sobrecarga_90 > 0:
            info_auto = f"Auto-scaler: 🔼 Evaluando Scale-Out L5 ({self.segundos_sobrecarga_90}/{SEGUNDOS_OUT_HORIZ}s)"
            color_auto = "#ffb74d"
        elif self.segundos_sobrecarga_75 > 0:
            info_auto = f"Auto-scaler: 🔼 Evaluando Scale-Up V ({self.segundos_sobrecarga_75}/{SEGUNDOS_UP_VERT}s)"
            color_auto = "#ffb74d"
        elif self.segundos_subutilizado_30 > 0:
            info_auto = f"Auto-scaler: 🔽 Evaluando Desescalado ({self.segundos_subutilizado_30}/{SEGUNDOS_IN}s)"
            color_auto = "#81c784"
        else:
            info_auto = "Auto-scaler: 🟢 Activo · Monitoreando"
            color_auto = "#7ee787"

        self.label_auto_info.config(text=info_auto, foreground=color_auto)

        self.label_rt.config(
            text=f"Tiempo de respuesta promedio: {'SIN SERVICIO' if rt is None else f'{rt:.0f} ms'}"
        )

        nivel_actual = self.nodos[0].nivel if self.nodos else 0
        self.label_nivel.config(
            text=f"Nivel vertical: L{nivel_actual} ({NOMBRE_POR_NIVEL.get(nivel_actual, '?')})"
        )
        self.label_costo.config(text=f"Costo relativo: x{COSTO_POR_NIVEL.get(nivel_actual, '?')}")
        self.label_nodos.config(text=f"Servidores activos: {len(activos)} / {len(self.nodos)}")

        capacidad_total = sum(n.capacidad() for n in activos)
        self.label_capacidad.config(text=f"Capacidad total activa: {capacidad_total:.0f} req/s")

        trafico_solicitado = float(self.trafico_var.get())
        perdida = max(0.0, trafico_solicitado - capacidad_total)
        self.label_perdida.config(text=f"Tráfico no atendido: {perdida:.0f} req/s")

    # ------------------------------------------------------------------
    # Dibujo del canvas
    # ------------------------------------------------------------------
    def _dibujar(self):
        self.canvas.delete("all")
        ancho = max(self.canvas.winfo_width(), 400)
        alto = max(self.canvas.winfo_height(), 380)

        margen_inferior = 70
        margen_superior = 30
        base_y = alto - margen_inferior
        tope_y = margen_superior + 20
        area_altura = base_y - tope_y

        # Línea de "tope" (100% de capacidad del nivel actual)
        self.canvas.create_line(
            10, tope_y, ancho - 10, tope_y, fill="#e05252", dash=(4, 3), width=2
        )
        self.canvas.create_text(
            ancho - 90, tope_y - 12, text="TOPE (100%)", fill="#e05252", font=("TkDefaultFont", 9, "bold")
        )

        # Líneas de referencia de umbrales
        y_75 = base_y - (0.75 * area_altura)
        y_30 = base_y - (0.30 * area_altura)

        self.canvas.create_line(10, y_75, ancho - 10, y_75, fill="#ffb74d", dash=(2, 4), width=1)
        self.canvas.create_text(65, y_75 - 8, text="Umbral Subida (75%)", fill="#ffb74d", font=("TkDefaultFont", 8))

        self.canvas.create_line(10, y_30, ancho - 10, y_30, fill="#81c784", dash=(2, 4), width=1)
        self.canvas.create_text(65, y_30 - 8, text="Umbral Ahorro (30%)", fill="#81c784", font=("TkDefaultFont", 8))

        n = max(len(self.nodos), 1)
        ancho_disponible = ancho - 20
        ancho_barra = min(90, (ancho_disponible / n) - 20)
        espacio = ancho_disponible / n

        for i, nodo in enumerate(self.nodos):
            centro_x = 10 + espacio * i + espacio / 2
            x0 = centro_x - ancho_barra / 2
            x1 = centro_x + ancho_barra / 2

            u = nodo.utilizacion()
            u_dibujo = min(u, 1.35)
            altura_barra = u_dibujo * area_altura
            y0 = base_y - altura_barra

            if nodo.caido:
                color = "#555c66"
            elif u >= 1.0:
                color = "#e04b4b"
            elif u >= 0.75:
                color = "#e0b23c"
            elif u <= 0.30:
                color = "#4ba3e0"
            else:
                color = "#3ca66b"

            self.canvas.create_rectangle(x0, base_y, x1, y0, fill=color, outline="#0d0f12", width=2)

            if u > 1.0 and not nodo.caido:
                self.canvas.create_rectangle(
                    x0, tope_y, x1, max(tope_y, y0), fill="#8f1d1d", outline="", stipple="gray50"
                )

            if nodo.caido:
                self.canvas.create_line(x0, base_y, x1, y0, fill="#ff5555", width=3)
                self.canvas.create_line(x0, y0, x1, base_y, fill="#ff5555", width=3)

            rt_txt = "TIMEOUT" if nodo.tiempo_respuesta and nodo.tiempo_respuesta >= 3000 else f"{nodo.tiempo_respuesta:.0f} ms"
            estado_txt = "CAÍDO" if nodo.caido else f"{min(u, 9.99) * 100:.0f}%"

            self.canvas.create_text(
                centro_x,
                base_y + 16,
                text=f"Servidor {nodo.id}",
                fill="#e6e6e6",
                font=("TkDefaultFont", 9, "bold"),
            )
            self.canvas.create_text(
                centro_x,
                base_y + 32,
                text=f"L{nodo.nivel} · {estado_txt}",
                fill="#c9c9c9",
                font=("TkDefaultFont", 8),
            )
            self.canvas.create_text(
                centro_x,
                base_y + 47,
                text=rt_txt,
                fill="#c9c9c9",
                font=("TkDefaultFont", 8),
            )

    # ------------------------------------------------------------------
    # Acciones de escalamiento y operaciones
    # ------------------------------------------------------------------
    def simular_pico_concierto(self):
        self.pico_restante = 6
        self.log("🎟 [VENTA DE CONCIERTO]: ¡Inició la preventa! Miles de fans entran a la fila virtual (~2.5x tráfico por 6 segundos).")

    def alternar_pausa(self):
        self.corriendo = not self.corriendo
        self.btn_pausa.config(text="▶ Reanudar" if not self.corriendo else "⏸ Pausar")

    def reparar_nodos(self):
        reparados = 0
        for n in self.nodos:
            if n.caido:
                n.caido = False
                n.ticks_sobrecargado = 0
                n.categoria_previa = "ok"
                reparados += 1
        if reparados:
            self.log(f"🛠 Se repararon {reparados} servidor(es) caído(s).")
        else:
            self.log("🛠 No había servidores caídos que reparar.")

    def reiniciar_todo(self):
        self._crear_nodos_iniciales(NODOS_MINIMOS)
        self._reiniciar_estado()
        self._actualizar_metricas()
        self._dibujar()

    def escalar_vertical(self, automatico=False):
        if all(n.nivel >= NIVEL_MAXIMO for n in self.nodos):
            if not automatico:
                self._avisar_tope_vertical(silencioso=False)
            return

        antes = self.tiempo_respuesta_promedio()
        for n in self.nodos:
            if n.nivel < NIVEL_MAXIMO:
                n.nivel += 1
            n.ticks_sobrecargado = 0
            n.categoria_previa = "ok"

        self._distribuir_carga()
        self._recalcular_nodos_post_escalado()
        self._actualizar_metricas()
        self._dibujar()
        despues = self.tiempo_respuesta_promedio()

        nivel_actual = self.nodos[0].nivel
        origen = "🤖 Auto-scaling [Scale-Up]" if automatico else "🔼 Escalamiento VERTICAL (manual)"
        self.log(
            f"{origen} → Todos los servidores suben a L{nivel_actual} "
            f"({NOMBRE_POR_NIVEL[nivel_actual]}), costo x{COSTO_POR_NIVEL[nivel_actual]}."
        )
        self._log_comparacion_rt(antes, despues)

    def desescalar_vertical(self, automatico=False):
        if all(n.nivel <= NIVEL_MINIMO for n in self.nodos):
            if not automatico:
                messagebox.showinfo("Límite mínimo", f"El clúster ya está en el nivel vertical mínimo L{NIVEL_MINIMO}.")
            return

        antes = self.tiempo_respuesta_promedio()
        for n in self.nodos:
            if n.nivel > NIVEL_MINIMO:
                n.nivel -= 1
            n.ticks_sobrecargado = 0
            n.categoria_previa = "ok"

        self._distribuir_carga()
        self._recalcular_nodos_post_escalado()
        self._actualizar_metricas()
        self._dibujar()
        despues = self.tiempo_respuesta_promedio()

        nivel_actual = self.nodos[0].nivel
        origen = "🤖 Auto-scaling [Scale-Down]" if automatico else "🔽 Desescalamiento VERTICAL (manual)"
        self.log(
            f"{origen} → Nivel reducido a L{nivel_actual} "
            f"({NOMBRE_POR_NIVEL[nivel_actual]}), costo x{COSTO_POR_NIVEL[nivel_actual]}."
        )
        self._log_comparacion_rt(antes, despues)

    def escalar_horizontal(self, automatico=False):
        if len(self.nodos) >= NODOS_MAXIMOS:
            if not automatico:
                messagebox.showinfo(
                    "Límite alcanzado",
                    f"Ya tienes el máximo simulado de {NODOS_MAXIMOS} servidores en el clúster.",
                )
            return

        antes = self.tiempo_respuesta_promedio()
        nivel_nuevo_nodo = self.nodos[0].nivel if self.nodos else NIVEL_MINIMO
        self.contador_ids += 1
        self.nodos.append(Nodo(self.contador_ids, nivel=nivel_nuevo_nodo))

        for n in self.nodos:
            n.ticks_sobrecargado = 0
            n.categoria_previa = "ok"

        self._distribuir_carga()
        self._recalcular_nodos_post_escalado()
        self._actualizar_metricas()
        self._dibujar()
        despues = self.tiempo_respuesta_promedio()

        origen = "🤖 Auto-scaling [Scale-Out]" if automatico else "➕ Escalamiento HORIZONTAL (manual)"
        self.log(f"{origen} → Servidor {self.contador_ids} añadido. Servidores en el clúster: {len(self.nodos)}.")
        self._log_comparacion_rt(antes, despues)

    def desescalar_horizontal(self, automatico=False):
        if len(self.nodos) <= NODOS_MINIMOS:
            if not automatico:
                messagebox.showinfo(
                    "Límite mínimo",
                    f"El clúster ya está en el mínimo seguro de {NODOS_MINIMOS} servidores.",
                )
            return

        antes = self.tiempo_respuesta_promedio()
        nodo_removido = self.nodos.pop()

        self._distribuir_carga()
        self._recalcular_nodos_post_escalado()
        self._actualizar_metricas()
        self._dibujar()
        despues = self.tiempo_respuesta_promedio()

        origen = "🤖 Auto-scaling [Scale-In]" if automatico else "➖ Desescalamiento HORIZONTAL (manual)"
        self.log(f"{origen} → Retirado Servidor {nodo_removido.id}. Servidores restantes: {len(self.nodos)}.")
        self._log_comparacion_rt(antes, despues)

    def _log_comparacion_rt(self, antes, despues):
        txt_antes = "SIN SERVICIO" if antes is None else f"{antes:.0f} ms"
        txt_despues = "SIN SERVICIO" if despues is None else f"{despues:.0f} ms"
        self.log(f"   Tiempo de respuesta: {txt_antes} → {txt_despues}")

    def _avisar_tope_vertical(self, silencioso):
        clave = "_tope_avisado"
        if silencioso and getattr(self, clave, False):
            return
        setattr(self, clave, True)

        mensaje = (
            "Señales de que llegaste al límite de escalamiento vertical:\n\n"
            "1. Ya estás en el tipo de servidor más potente disponible (L5 - m5.8xlarge).\n"
            "2. El costo crece más rápido que el rendimiento.\n"
            "3. Se activa el escalamiento HORIZONTAL para agregar más servidores si la carga >= 90%."
        )
        if not silencioso:
            messagebox.showwarning("Tope de escalamiento vertical alcanzado", mensaje)
        self.log("🚫 TOPE VERTICAL: " + mensaje.replace("\n", " "))


def main():
    root = tk.Tk()
    app = SimuladorClusterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
