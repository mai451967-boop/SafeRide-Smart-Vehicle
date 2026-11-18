import customtkinter as ctk
from tkinter import filedialog, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import random
import csv
from datetime import datetime
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class SafeRideDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SafeRide - Smart Vehicle Safety & Telemetry Dashboard")
        self.geometry("1280x820")
        self.minsize(1100, 720)

        self.serial_conn = None
        self.is_running = False
        self.demo_mode = False
        self.last_status = None
        self.last_card = "NONE"

        self.max_points = 50
        self.time_data = deque(maxlen=self.max_points)
        self.temp_data = deque(maxlen=self.max_points)
        self.gas_data = deque(maxlen=self.max_points)
        self.sample_counter = 0

        self.event_records = []

        self.demo_step = 0
        self.demo_temp = 26.0
        self.demo_gas = 180

        self.build_ui()
        self.refresh_ports()
        self.log_event("SYSTEM", "SafeRide Dashboard initialized and ready.")

    def build_ui(self):
        top_frame = ctk.CTkFrame(self, height=65, corner_radius=10)
        top_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            top_frame,
            text="SafeRide",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#38BDF8"
        )
        title_lbl.pack(side="left", padx=20, pady=12)

        subtitle_lbl = ctk.CTkLabel(
            top_frame,
            text="Vehicle Telemetry & Predictive Safety System",
            font=ctk.CTkFont(size=13),
            text_color="#94A3B8"
        )
        subtitle_lbl.pack(side="left", padx=5)

        self.connect_btn = ctk.CTkButton(
            top_frame,
            text="Connect / Start",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            width=160,
            height=38,
            command=self.toggle_connection
        )
        self.connect_btn.pack(side="right", padx=15, pady=12)

        refresh_btn = ctk.CTkButton(
            top_frame,
            text="Refresh",
            width=75,
            height=38,
            fg_color="#334155",
            hover_color="#475569",
            command=self.refresh_ports
        )
        refresh_btn.pack(side="right", padx=(0, 8), pady=12)

        self.port_var = ctk.StringVar(value="DEMO MODE")
        self.port_menu = ctk.CTkOptionMenu(
            top_frame,
            variable=self.port_var,
            values=["DEMO MODE"],
            width=180,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.port_menu.pack(side="right", padx=8, pady=12)

        port_lbl = ctk.CTkLabel(
            top_frame,
            text="Connection Port:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        port_lbl.pack(side="right", padx=5)

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=15, pady=5)
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.status_card = ctk.CTkFrame(cards_frame, corner_radius=12, fg_color="#1E293B", border_width=2, border_color="#64748B")
        self.status_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        ctk.CTkLabel(self.status_card, text="VEHICLE STATUS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(pady=(12, 2))
        self.status_val_lbl = ctk.CTkLabel(self.status_card, text="LOCKED", font=ctk.CTkFont(size=22, weight="bold"), text_color="#F8FAFC")
        self.status_val_lbl.pack(pady=(2, 4))
        self.card_id_lbl = ctk.CTkLabel(self.status_card, text="RFID Card: NONE", font=ctk.CTkFont(size=12), text_color="#CBD5E1")
        self.card_id_lbl.pack(pady=(0, 12))

        self.temp_card = ctk.CTkFrame(cards_frame, corner_radius=12, fg_color="#1E293B")
        self.temp_card.grid(row=0, column=1, padx=8, sticky="nsew")
        ctk.CTkLabel(self.temp_card, text="CABIN TEMPERATURE", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(pady=(12, 2))
        self.temp_val_lbl = ctk.CTkLabel(self.temp_card, text="-- C", font=ctk.CTkFont(size=26, weight="bold"), text_color="#38BDF8")
        self.temp_val_lbl.pack(pady=(2, 4))
        ctk.CTkLabel(self.temp_card, text="Safe < 35C | Danger > 40C", font=ctk.CTkFont(size=11), text_color="#64748B").pack(pady=(0, 12))

        self.gas_card = ctk.CTkFrame(cards_frame, corner_radius=12, fg_color="#1E293B")
        self.gas_card.grid(row=0, column=2, padx=8, sticky="nsew")
        ctk.CTkLabel(self.gas_card, text="GAS / SMOKE LEVEL (MQ-2)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(pady=(12, 2))
        self.gas_val_lbl = ctk.CTkLabel(self.gas_card, text="-- PPM", font=ctk.CTkFont(size=26, weight="bold"), text_color="#A78BFA")
        self.gas_val_lbl.pack(pady=(2, 4))
        ctk.CTkLabel(self.gas_card, text="Safe < 350 | Danger > 500", font=ctk.CTkFont(size=11), text_color="#64748B").pack(pady=(0, 12))

        self.ai_card = ctk.CTkFrame(cards_frame, corner_radius=12, fg_color="#1E293B", border_width=2, border_color="#334155")
        self.ai_card.grid(row=0, column=3, padx=(8, 0), sticky="nsew")
        ctk.CTkLabel(self.ai_card, text="SMART RATE ALERT", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38BDF8").pack(pady=(12, 2))
        self.ai_status_lbl = ctk.CTkLabel(self.ai_card, text="Normal Thermal Rate", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10B981")
        self.ai_status_lbl.pack(pady=(6, 4))
        self.ai_detail_lbl = ctk.CTkLabel(self.ai_card, text="Monitoring rate of change...", font=ctk.CTkFont(size=11), text_color="#94A3B8")
        self.ai_detail_lbl.pack(pady=(0, 12))

        graph_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B")
        graph_frame.pack(fill="both", expand=True, padx=15, pady=10)

        plt.style.use("dark_background")
        self.fig, (self.ax_temp, self.ax_gas) = plt.subplots(1, 2, figsize=(11, 3.4), dpi=100)
        self.fig.patch.set_facecolor("#1E293B")
        self.fig.subplots_adjust(left=0.06, right=0.97, top=0.84, bottom=0.18, wspace=0.22)

        self.ax_temp.set_facecolor("#0F172A")
        self.ax_temp.set_title("Live Cabin Temperature (C)", fontsize=11, fontweight="bold", color="#38BDF8")
        self.ax_temp.set_ylabel("Temp (C)", fontsize=9)
        self.ax_temp.grid(True, linestyle="--", alpha=0.25)
        self.temp_line, = self.ax_temp.plot([], [], color="#38BDF8", linewidth=2.5, marker="o", markersize=3)
        self.ax_temp.axhline(y=40, color="#EF4444", linestyle="--", linewidth=1, label="Danger (40C)")
        self.ax_temp.axhline(y=35, color="#F59E0B", linestyle=":", linewidth=1, label="Warning (35C)")
        self.ax_temp.legend(loc="upper left", fontsize=8)

        self.ax_gas.set_facecolor("#0F172A")
        self.ax_gas.set_title("Live Gas Sensor Level (MQ-2)", fontsize=11, fontweight="bold", color="#A78BFA")
        self.ax_gas.set_ylabel("Analog Value", fontsize=9)
        self.ax_gas.grid(True, linestyle="--", alpha=0.25)
        self.gas_line, = self.ax_gas.plot([], [], color="#A78BFA", linewidth=2.5, marker="o", markersize=3)
        self.ax_gas.axhline(y=500, color="#EF4444", linestyle="--", linewidth=1, label="Danger (500)")
        self.ax_gas.axhline(y=350, color="#F59E0B", linestyle=":", linewidth=1, label="Warning (350)")
        self.ax_gas.legend(loc="upper left", fontsize=8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        log_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B", height=180)
        log_frame.pack(fill="x", padx=15, pady=(0, 15))

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            log_header,
            text="Real-Time System Event Log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F8FAFC"
        ).pack(side="left")

        export_btn = ctk.CTkButton(
            log_header,
            text="Export Log to CSV",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=30,
            width=150,
            command=self.export_csv
        )
        export_btn.pack(side="right")

        clear_btn = ctk.CTkButton(
            log_header,
            text="Clear Log",
            font=ctk.CTkFont(size=12),
            fg_color="#475569",
            hover_color="#64748B",
            height=30,
            width=90,
            command=self.clear_log
        )
        clear_btn.pack(side="right", padx=8)

        self.log_textbox = ctk.CTkTextbox(
            log_frame,
            height=120,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0F172A",
            text_color="#E2E8F0"
        )
        self.log_textbox.pack(fill="x", padx=12, pady=(0, 10))
        self.log_textbox.configure(state="disabled")

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        options = ["DEMO MODE"] + ports
        self.port_menu.configure(values=options)
        if len(ports) > 0:
            self.port_var.set(ports[0])
        else:
            self.port_var.set("DEMO MODE")

    def toggle_connection(self):
        if not self.is_running:
            selected = self.port_var.get()
            if selected == "DEMO MODE":
                self.demo_mode = True
                self.is_running = True
                self.demo_step = 0
                self.demo_temp = 26.0
                self.demo_gas = 180
                self.connect_btn.configure(text="Stop Demo", fg_color="#EF4444", hover_color="#DC2626")
                self.log_event("DEMO", "Started DEMO MODE simulation.")
                threading.Thread(target=self.demo_loop, daemon=True).start()
            else:
                try:
                    self.serial_conn = serial.Serial(selected, 9600, timeout=1)
                    time.sleep(2)
                    self.demo_mode = False
                    self.is_running = True
                    self.connect_btn.configure(text="Disconnect", fg_color="#EF4444", hover_color="#DC2626")
                    self.log_event("CONNECT", f"Connected to Arduino on {selected} at 9600 baud.")
                    threading.Thread(target=self.serial_loop, daemon=True).start()
                except Exception as e:
                    messagebox.showerror("Connection Error", f"Could not open {selected}:\n{e}")
        else:
            self.is_running = False
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.connect_btn.configure(text="Connect / Start", fg_color="#10B981", hover_color="#059669")
            self.log_event("DISCONNECT", "Stopped telemetry connection.")

    def serial_loop(self):
        while self.is_running and self.serial_conn and self.serial_conn.is_open:
            try:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("DATA,"):
                        parts = line.split(",")
                        if len(parts) == 5:
                            temp = float(parts[1])
                            gas = int(parts[2])
                            status = parts[3].strip()
                            card_id = parts[4].strip()
                            self.after(0, self.process_incoming_data, temp, gas, status, card_id)
            except Exception as e:
                self.after(0, self.log_event, "ERROR", f"Serial read error: {e}")
                break
            time.sleep(0.05)

    def demo_loop(self):
        while self.is_running and self.demo_mode:
            self.demo_step += 1

            if self.demo_step <= 4:
                status = "LOCKED"
                card_id = "NONE"
                self.demo_temp = round(25.0 + random.uniform(-0.2, 0.3), 1)
                self.demo_gas = random.randint(150, 175)
            elif self.demo_step <= 14:
                status = "SAFE"
                card_id = "A3F91B2C"
                self.demo_temp = round(27.0 + random.uniform(-0.3, 0.4), 1)
                self.demo_gas = random.randint(180, 220)
            elif self.demo_step <= 22:
                card_id = "A3F91B2C"
                self.demo_temp = round(self.demo_temp + random.uniform(1.3, 1.8), 1)
                self.demo_gas = random.randint(360, 440)
                status = "WARNING" if self.demo_temp <= 40.0 else "DANGER_TEMP"
            elif self.demo_step <= 26:
                card_id = "A3F91B2C"
                self.demo_temp = 41.5
                self.demo_gas = 530
                status = "DANGER_TEMP"
            else:
                self.demo_step = 0
                continue

            self.after(0, self.process_incoming_data, self.demo_temp, self.demo_gas, status, card_id)
            time.sleep(0.5)

    def process_incoming_data(self, temp, gas, status, card_id):
        self.sample_counter += 1
        self.time_data.append(self.sample_counter)
        self.temp_data.append(temp)
        self.gas_data.append(gas)

        self.temp_val_lbl.configure(text=f"{temp:.1f} C")
        self.gas_val_lbl.configure(text=f"{gas} PPM")
        self.card_id_lbl.configure(text=f"RFID Card: {card_id}")

        if status == "LOCKED":
            self.status_card.configure(fg_color="#1E293B", border_color="#64748B")
            self.status_val_lbl.configure(text="LOCKED", text_color="#CBD5E1")
        elif status == "SAFE":
            self.status_card.configure(fg_color="#064E3B", border_color="#10B981")
            self.status_val_lbl.configure(text="SAFE / DRIVING", text_color="#34D399")
        elif status == "WARNING":
            self.status_card.configure(fg_color="#78350F", border_color="#F59E0B")
            self.status_val_lbl.configure(text="EARLY WARNING", text_color="#FBBF24")
        elif status == "DANGER_GAS":
            self.status_card.configure(fg_color="#7F1D1D", border_color="#EF4444")
            self.status_val_lbl.configure(text="DANGER: GAS LEAK", text_color="#FCA5A5")
        elif status == "DANGER_TEMP":
            self.status_card.configure(fg_color="#7F1D1D", border_color="#EF4444")
            self.status_val_lbl.configure(text="DANGER: HIGH TEMP", text_color="#FCA5A5")

        if card_id != "NONE" and card_id != self.last_card:
            self.log_event("RFID_UNLOCK", f"Vehicle unlocked with RFID Card UID: {card_id}")
            self.last_card = card_id

        if status != self.last_status:
            if status == "WARNING":
                self.log_event("WARNING", f"Early warning triggered! Temp={temp}C, Gas={gas}")
            elif status == "DANGER_TEMP":
                self.log_event("CRITICAL_TEMP", f"EMERGENCY! High temperature ({temp}C). Engine stopped!")
            elif status == "DANGER_GAS":
                self.log_event("CRITICAL_GAS", f"EMERGENCY! Gas leak detected ({gas}). Engine stopped!")
            elif status == "SAFE" and self.last_status in ["WARNING", "DANGER_TEMP", "DANGER_GAS"]:
                self.log_event("SAFE", "Vehicle parameters returned to normal safe range.")
            self.last_status = status

        self.run_rate_prediction(temp)
        self.update_charts()

    def run_rate_prediction(self, current_temp):
        if len(self.temp_data) >= 5:
            past_temp = self.temp_data[-5]
            rate_of_rise = current_temp - past_temp

            if rate_of_rise >= 2.5 and current_temp < 40.0:
                predicted_temp = current_temp + (rate_of_rise * 1.5)
                self.ai_card.configure(fg_color="#451A03", border_color="#F97316")
                self.ai_status_lbl.configure(text="RAPID HEAT SURGE!", text_color="#FB923C")
                self.ai_detail_lbl.configure(
                    text=f"+{rate_of_rise:.1f}C/2s | Predicted: {predicted_temp:.1f}C soon!",
                    text_color="#FDBA74"
                )
                if self.sample_counter % 4 == 0:
                    self.log_event("RATE_ALERT", f"Rapid temp rise (+{rate_of_rise:.1f}C). Danger threshold approaching!")
            else:
                self.ai_card.configure(fg_color="#1E293B", border_color="#334155")
                self.ai_status_lbl.configure(text="Normal Thermal Rate", text_color="#10B981")
                self.ai_detail_lbl.configure(
                    text=f"Rate: {rate_of_rise:+.1f}C / 2s (Stable)",
                    text_color="#94A3B8"
                )

    def update_charts(self):
        x_vals = list(self.time_data)
        y_temp = list(self.temp_data)
        y_gas = list(self.gas_data)

        self.temp_line.set_data(x_vals, y_temp)
        self.ax_temp.set_xlim(max(0, self.sample_counter - self.max_points), max(self.max_points, self.sample_counter + 2))
        self.ax_temp.set_ylim(15, max(50, max(y_temp) + 5))

        self.gas_line.set_data(x_vals, y_gas)
        self.ax_gas.set_xlim(max(0, self.sample_counter - self.max_points), max(self.max_points, self.sample_counter + 2))
        self.ax_gas.set_ylim(0, max(650, max(y_gas) + 50))

        self.canvas.draw_idle()

    def log_event(self, event_type, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_line = f"[{timestamp}] [{event_type}] {message}\n"

        self.event_records.append([timestamp, event_type, message])

        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", formatted_line)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def clear_log(self):
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.event_records.clear()

    def export_csv(self):
        if not self.event_records:
            messagebox.showinfo("Export CSV", "No events recorded yet to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"SafeRide_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if file_path:
            try:
                with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "Event Type", "Description"])
                    writer.writerows(self.event_records)
                messagebox.showinfo("Success", f"Log saved successfully to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to save CSV:\n{e}")


if __name__ == "__main__":
    app = SafeRideDashboard()
    app.mainloop()