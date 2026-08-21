"""
Simulador de Escalamiento de Clúster (Vertical vs Horizontal)
==============================================================

Interfaz gráfica hecha con Tkinter (viene incluido con Python, no requiere
instalar nada) que simula un clúster de nodos recibiendo tráfico/peticiones.

Qué puedes hacer:
- Ajustar el tráfico entrante (peticiones/seg) con el deslizador.
- Simular un "pico" de tráfico repentino.
- Ver en un panel lateral cómo "crecen" verticalmente los nodos (barras)
  hasta tocar el techo (tope) de capacidad, y qué síntomas aparecen
  (latencia alta, timeouts, caídas de nodo).
- Escalar VERTICALMENTE (subir el tipo de instancia de todos los nodos)
  hasta llegar al tope máximo simulado, momento en el cual se muestran
  las 3 señales de "llegaste al límite vertical".
- Escalar HORIZONTALMENTE (agregar nodos al clúster) y comparar cómo
  cambia el tiempo de respuesta y la tolerancia a fallos.
- Revisar un log de eventos (fallos, escalamientos, recuperaciones).

Ejecutar con:
    python simulador_cluster.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random

# ----------------------------------------------------------------------
# Modelo: niveles de instancia (escalamiento vertical)
# La capacidad crece de forma SUBLINEAL mientras el costo crece de forma
# EXPONENCIAL -> representa la señal #2 de "el costo crece más rápido
# que el rendimiento ganado".
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
NIVEL_MAXIMO = 5
NODOS_MAXIMOS = 8
LATENCIA_BASE_MS = 35
TICKS_PARA_CAER = 3          # ticks seguidos sobrecargado antes de "caer"
INTERVALO_TICK_MS = 900


class Nodo:
    """Representa un nodo del clúster."""

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
        self.root.title("Simulador de Escalamiento de Clúster")
        self.root.geometry("1050x650")
        self.root.minsize(950, 600)

        self.contador_ids = 0
        self.nodos = []
        self.corriendo = True
        self.pico_restante = 0

        self._crear_nodos_iniciales(3)
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
            self.nodos.append(Nodo(self.contador_ids, nivel=1))

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        # --- Panel superior: controles ---
        panel_controles = ttk.Frame(self.root, padding=10)
        panel_controles.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(panel_controles, text="Tráfico entrante (peticiones/seg):").grid(
            row=0, column=0, sticky="w"
        )
        self.trafico_var = tk.DoubleVar(value=60)
        self.slider_trafico = ttk.Scale(
            panel_controles,
            from_=0,
            to=1000,
            variable=self.trafico_var,
            orient=tk.HORIZONTAL,
            length=260,
        )
        self.slider_trafico.grid(row=0, column=1, padx=8)

        self.label_trafico_valor = ttk.Label(panel_controles, text="60 req/s", width=10)
        self.label_trafico_valor.grid(row=0, column=2, sticky="w")
        self.trafico_var.trace_add("write", self._on_trafico_change)

        ttk.Button(
            panel_controles, text="⚡ Simular pico de tráfico", command=self.simular_pico
        ).grid(row=0, column=3, padx=10)

        ttk.Button(
            panel_controles, text="🔼 Escalar verticalmente", command=self.escalar_vertical
        ).grid(row=0, column=4, padx=6)

        ttk.Button(
            panel_controles, text="➕ Escalar horizontalmente", command=self.escalar_horizontal
        ).grid(row=0, column=5, padx=6)

        ttk.Button(
            panel_controles, text="🛠 Reparar nodos caídos", command=self.reparar_nodos
        ).grid(row=0, column=6, padx=6)

        self.btn_pausa = ttk.Button(
            panel_controles, text="⏸ Pausar", command=self.alternar_pausa
        )
        self.btn_pausa.grid(row=0, column=7, padx=6)

        ttk.Button(
            panel_controles, text="🔄 Reiniciar simulación", command=self.reiniciar_todo
        ).grid(row=0, column=8, padx=6)

        # --- Panel central: canvas de nodos (crecimiento vertical) ---
        panel_central = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        panel_central.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(
            panel_central,
            text="Crecimiento vertical de los nodos (barra = % de capacidad usada)",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")

        self.canvas = tk.Canvas(panel_central, bg="#101418", height=430)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- Panel lateral derecho: métricas + log ---
        panel_lateral = ttk.Frame(self.root, padding=(0, 0, 10, 10), width=340)
        panel_lateral.pack(side=tk.RIGHT, fill=tk.Y)
        panel_lateral.pack_propagate(False)

        marco_metricas = ttk.LabelFrame(panel_lateral, text="Estado del clúster", padding=10)
        marco_metricas.pack(fill=tk.X, pady=(0, 8))

        self.label_estado = ttk.Label(
            marco_metricas, text="🟢 SALUDABLE", font=("TkDefaultFont", 11, "bold")
        )
        self.label_estado.pack(anchor="w")

        self.label_rt = ttk.Label(marco_metricas, text="Tiempo de respuesta promedio: -- ms")
        self.label_rt.pack(anchor="w", pady=(4, 0))

        self.label_nivel = ttk.Label(marco_metricas, text="Nivel vertical: L1 (m5.large)")
        self.label_nivel.pack(anchor="w")

        self.label_costo = ttk.Label(marco_metricas, text="Costo relativo: x1")
        self.label_costo.pack(anchor="w")

        self.label_nodos = ttk.Label(marco_metricas, text="Nodos activos: 3 / 3")
        self.label_nodos.pack(anchor="w")

        self.label_capacidad = ttk.Label(marco_metricas, text="Capacidad total: -- req/s")
        self.label_capacidad.pack(anchor="w")

        self.label_perdida = ttk.Label(marco_metricas, text="Tráfico no atendido: 0 req/s")
        self.label_perdida.pack(anchor="w")

        marco_log = ttk.LabelFrame(panel_lateral, text="Registro de eventos y síntomas", padding=5)
        marco_log.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(marco_log)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.texto_log = tk.Text(
            marco_log,
            wrap="word",
            height=20,
            yscrollcommand=scrollbar.set,
            bg="#1c1f24",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            state="disabled",
        )
        self.texto_log.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.texto_log.yview)

    # ------------------------------------------------------------------
    # Utilidades de estado
    # ------------------------------------------------------------------
    def _reiniciar_estado(self):
        self.pico_restante = 0
        self.trafico_var.set(60)
        self._limpiar_log()
        self.log("Simulación iniciada con 3 nodos, nivel L1 (m5.large).")

    def _on_trafico_change(self, *_):
        try:
            valor = int(float(self.trafico_var.get()))
        except (tk.TclError, ValueError):
            return
        self.label_trafico_valor.config(text=f"{valor} req/s")

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
            return base * 2.6
        return base

    def _avanzar_estado(self):
        self._distribuir_carga()
        self._evaluar_nodos()
        self._actualizar_metricas()
        self._dibujar()

    def _distribuir_carga(self):
        trafico = self._trafico_efectivo()
        activos = self.nodos_activos()
        if not activos:
            return
        carga_pareja = trafico / len(activos)
        for n in activos:
            ruido = random.uniform(0.9, 1.1)
            n.carga_actual = max(0.0, carga_pareja * ruido)

    def _evaluar_nodos(self):
        for n in self.nodos:
            if n.caido:
                continue
            u = n.utilizacion()
            if u < 1.0:
                n.tiempo_respuesta = LATENCIA_BASE_MS / max(0.02, (1 - u))
                n.ticks_sobrecargado = 0
            else:
                n.tiempo_respuesta = 3000  # timeout simbólico
                n.ticks_sobrecargado += 1

            categoria = n.categoria()
            if categoria != n.categoria_previa:
                if categoria == "critico":
                    self.log(
                        f"⚠️ Nodo {n.id} (L{n.nivel}): sobrecargado al "
                        f"{u * 100:.0f}% de su capacidad — latencia crítica / posibles timeouts."
                    )
                elif categoria == "advertencia":
                    self.log(
                        f"🟡 Nodo {n.id} (L{n.nivel}): uso elevado ({u * 100:.0f}%) — "
                        "latencia empieza a subir."
                    )
                elif categoria == "ok" and n.categoria_previa in ("advertencia", "critico"):
                    self.log(f"🟢 Nodo {n.id} (L{n.nivel}) volvió a niveles normales.")
            n.categoria_previa = categoria

            if n.ticks_sobrecargado >= TICKS_PARA_CAER and not n.caido:
                n.caido = True
                self.log(
                    f"❌ Nodo {n.id} CAYÓ: sobrecarga sostenida provocó timeouts repetidos "
                    "y el nodo dejó de responder."
                )

        # Chequeo de tope vertical
        if (
            self.nodos
            and all(n.nivel >= NIVEL_MAXIMO for n in self.nodos)
            and any(n.utilizacion() >= 1.0 for n in self.nodos_activos() or self.nodos)
        ):
            self._avisar_tope_vertical(silencioso=True)

        # Chequeo de caída total (punto único de falla si solo hay 1 nodo)
        if self.nodos and not self.nodos_activos():
            if not getattr(self, "_ya_avise_caida_total", False):
                self.log("🔴 CAÍDA TOTAL DEL SERVICIO: no queda ningún nodo activo.")
                if len(self.nodos) == 1:
                    self.log(
                        "   → Con un solo nodo, su caída tumba TODO el servicio "
                        "(punto único de falla, señal #3 del límite vertical)."
                    )
                self._ya_avise_caida_total = True
        else:
            self._ya_avise_caida_total = False

    def _actualizar_metricas(self):
        activos = self.nodos_activos()
        rt = self.tiempo_respuesta_promedio()

        if not self.nodos or not activos:
            estado_txt, color = "🔴 CAÍDA TOTAL", "#ff5555"
        elif any(n.caido for n in self.nodos):
            estado_txt, color = "🟠 DEGRADADO (nodo caído)", "#ffb454"
        elif any(n.utilizacion() >= 1.0 for n in activos):
            estado_txt, color = "🔴 CRÍTICO", "#ff5555"
        elif any(n.utilizacion() >= 0.6 for n in activos):
            estado_txt, color = "🟡 ADVERTENCIA", "#ffd54f"
        else:
            estado_txt, color = "🟢 SALUDABLE", "#7ee787"

        self.label_estado.config(text=estado_txt, foreground=color)
        self.label_rt.config(
            text=f"Tiempo de respuesta promedio: {'SIN SERVICIO' if rt is None else f'{rt:.0f} ms'}"
        )

        nivel_actual = self.nodos[0].nivel if self.nodos else 0
        self.label_nivel.config(
            text=f"Nivel vertical: L{nivel_actual} ({NOMBRE_POR_NIVEL.get(nivel_actual, '?')})"
        )
        self.label_costo.config(text=f"Costo relativo: x{COSTO_POR_NIVEL.get(nivel_actual, '?')}")
        self.label_nodos.config(text=f"Nodos activos: {len(activos)} / {len(self.nodos)}")

        capacidad_total = sum(n.capacidad() for n in activos)
        self.label_capacidad.config(text=f"Capacidad total activa: {capacidad_total:.0f} req/s")

        trafico_solicitado = float(self.trafico_var.get())
        atendido = min(trafico_solicitado, capacidad_total)
        perdida = max(0.0, trafico_solicitado - capacidad_total)
        self.label_perdida.config(text=f"Tráfico no atendido: {perdida:.0f} req/s")

    # ------------------------------------------------------------------
    # Dibujo del canvas (crecimiento vertical de nodos)
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

        n = max(len(self.nodos), 1)
        ancho_disponible = ancho - 20
        ancho_barra = min(90, (ancho_disponible / n) - 20)
        espacio = ancho_disponible / n

        for i, nodo in enumerate(self.nodos):
            centro_x = 10 + espacio * i + espacio / 2
            x0 = centro_x - ancho_barra / 2
            x1 = centro_x + ancho_barra / 2

            u = nodo.utilizacion()
            u_dibujo = min(u, 1.35)  # permite ver "desborde" sobre el tope
            altura_barra = u_dibujo * area_altura
            y0 = base_y - altura_barra

            if nodo.caido:
                color = "#555c66"
            elif u >= 1.0:
                color = "#e04b4b"
            elif u >= 0.6:
                color = "#e0b23c"
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
                text=f"Nodo {nodo.id}",
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
    # Acciones de usuario
    # ------------------------------------------------------------------
    def simular_pico(self):
        self.pico_restante = 6
        self.log("⚡ Pico de tráfico simulado (~2.6x durante unos segundos).")

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
            self.log(f"🛠 Se repararon {reparados} nodo(s) caído(s) manualmente.")
        else:
            self.log("🛠 No había nodos caídos que reparar.")

    def reiniciar_todo(self):
        self._crear_nodos_iniciales(3)
        self._reiniciar_estado()
        self._actualizar_metricas()
        self._dibujar()

    def escalar_vertical(self):
        if all(n.nivel >= NIVEL_MAXIMO for n in self.nodos):
            self._avisar_tope_vertical(silencioso=False)
            return

        antes = self.tiempo_respuesta_promedio()
        for n in self.nodos:
            if n.nivel < NIVEL_MAXIMO:
                n.nivel += 1
            n.caido = False
            n.ticks_sobrecargado = 0
            n.categoria_previa = "ok"

        self._distribuir_carga()
        self._evaluar_nodos()
        self._actualizar_metricas()
        self._dibujar()
        despues = self.tiempo_respuesta_promedio()

        nivel_actual = self.nodos[0].nivel
        self.log(
            f"🔼 Escalamiento VERTICAL aplicado → todos los nodos ahora en "
            f"L{nivel_actual} ({NOMBRE_POR_NIVEL[nivel_actual]}), "
            f"costo relativo x{COSTO_POR_NIVEL[nivel_actual]}."
        )
        self._log_comparacion_rt(antes, despues)

        if nivel_actual >= NIVEL_MAXIMO:
            self.log("🟠 Llegaste al tipo de instancia más grande disponible en este clúster.")

    def escalar_horizontal(self):
        if len(self.nodos) >= NODOS_MAXIMOS:
            messagebox.showinfo(
                "Límite alcanzado",
                f"Ya tienes el máximo simulado de {NODOS_MAXIMOS} nodos en el clúster.",
            )
            return

        antes = self.tiempo_respuesta_promedio()
        nivel_nuevo_nodo = self.nodos[0].nivel if self.nodos else 1
        self.contador_ids += 1
        self.nodos.append(Nodo(self.contador_ids, nivel=nivel_nuevo_nodo))

        self._distribuir_carga()
        self._evaluar_nodos()
        self._actualizar_metricas()
        self._dibujar()
        despues = self.tiempo_respuesta_promedio()

        self.log(f"➕ Escalamiento HORIZONTAL aplicado → nodos en el clúster: {len(self.nodos)}.")
        self._log_comparacion_rt(antes, despues)
        if len(self.nodos) >= 2:
            self.log(
                "✅ Mayor tolerancia a fallos: si un nodo cae, los demás siguen "
                "atendiendo peticiones."
            )

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
            "1. Ya estás en el tipo de instancia más grande disponible.\n"
            "2. El costo empieza a crecer más rápido que el rendimiento que ganas "
            "(no es lineal).\n"
            "3. Un solo servidor caído tumba todo el servicio (sigues teniendo un "
            "único punto de falla).\n\n"
            "Considera escalar HORIZONTALMENTE para seguir creciendo."
        )
        if not silencioso:
            messagebox.showwarning("Tope de escalamiento vertical alcanzado", mensaje)
        self.log("🚫 TOPE VERTICAL ALCANZADO: " + mensaje.replace("\n", " "))


def main():
    root = tk.Tk()
    app = SimuladorClusterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
