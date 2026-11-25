import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- إعدادات المظهر العام ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- حدود الأمان (مطابقة لكود الأردوينو ) ---
WARN_TEMP = 29.0
DANGER_TEMP = 30.5
WARN_GAS = 260
DANGER_GAS = 300

class SafeRideDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SafeRide - Smart Vehicle Safety & Telemetry System")
        self.geometry("1150x720")
        self.minsize(1000, 640)

        # متغيرات الاتصال والبيانات
        self.ser = None
        self.is_connected = False
        self.is_demo = False
        self.running = True

        self.max_points = 40
        self.time_data = deque(maxlen=self.max_points)
        self.temp_data = deque(maxlen=self.max_points)
        self.gas_data = deque(maxlen=self.max_points)
        self.log_records = []

        self.current_temp = 0.0
        self.current_gas = 0
        self.current_status = "LOCKED"
        self.last_status = "LOCKED"
        self.current_card = "NONE"
        self.shutdown_reason = "Waiting for Driver Card"

        self.build_ui()
        self.refresh_ports()

        # بدء خيط قراءة البيانات
        self.thread = threading.Thread(target=self.data_loop, daemon=True)
        self.thread.start()

        # تحديث الرسم البياني دورياً
        self.update_plots()

    def build_ui(self):
        # 1. الشريط العلوي (Header & Connection)
        header = ctk.CTkFrame(self, height=65, corner_radius=10)
        header.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header,
            text="🚗 SafeRide Telemetry Dashboard",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#38BDF8"
        )
        title_lbl.pack(side="left", padx=20, pady=12)

        # عناصر الاتصال على اليمين
        conn_frame = ctk.CTkFrame(header, fg_color="transparent")
        conn_frame.pack(side="right", padx=15)

        self.port_combo = ctk.CTkComboBox(conn_frame, width=140, values=["DEMO MODE"])
        self.port_combo.pack(side="left", padx=5)

        refresh_btn = ctk.CTkButton(conn_frame, text="↻", width=35, command=self.refresh_ports)
        refresh_btn.pack(side="left", padx=5)

        self.connect_btn = ctk.CTkButton(
            conn_frame,
            text="Connect",
            width=100,
            fg_color="#10B981",
            hover_color="#059669",
            command=self.toggle_connection
        )
        self.connect_btn.pack(side="left", padx=5)

        export_btn = ctk.CTkButton(
            conn_frame,
            text="Export CSV",
            width=100,
            fg_color="#6366F1",
            hover_color="#4F46E5",
            command=self.export_csv
        )
        export_btn.pack(side="left", padx=5)

        # 2. بطاقات القراءات الحية (KPI Cards)
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=15, pady=5)
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # بطاقة حالة النظام وسبب الفصل
        self.status_val, self.status_sub = self.create_card(
            cards_frame, 0, "SYSTEM STATUS & REASON", "LOCKED", "Waiting for RFID", "#EF4444"
        )

        # بطاقة الحرارة
        self.temp_val, self.temp_sub = self.create_card(
            cards_frame, 1, "CABIN TEMPERATURE", "-- °C", f"Limit: {DANGER_TEMP}°C", "#38BDF8"
        )

        # بطاقة الغاز
        self.gas_val, self.gas_sub = self.create_card(
            cards_frame, 2, "GAS / SMOKE LEVEL", "-- PPM", f"Limit: {DANGER_GAS} PPM", "#F59E0B"
        )

        # بطاقة المصادقة (RFID)
        self.rfid_val, self.rfid_sub = self.create_card(
            cards_frame, 3, "DRIVER AUTH (RFID)", "NONE", "Engine Immobilized", "#A855F7"
        )

        # 3. منطقة الرسوم البيانية الحية (Live Charts)
        charts_frame = ctk.CTkFrame(self, corner_radius=12)
        charts_frame.pack(fill="both", expand=True, padx=15, pady=10)

        plt.style.use("dark_background")
        self.fig, (self.ax_temp, self.ax_gas) = plt.subplots(1, 2, figsize=(10, 4), dpi=100)
        self.fig.patch.set_facecolor("#1E293B")
        self.fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.15, wspace=0.22)

        self.canvas = FigureCanvasTkAgg(self.fig, master=charts_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        # 4. شريط السجل السفلي (Event Log)
        footer = ctk.CTkFrame(self, height=50, corner_radius=8)
        footer.pack(fill="x", padx=15, pady=(0, 15))

        self.log_lbl = ctk.CTkLabel(
            footer,
            text="Ready. Select Arduino COM port and click Connect.",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#94A3B8"
        )
        self.log_lbl.pack(side="left", padx=15, pady=10)

    def create_card(self, parent, col, title, val, sub, color):
        card = ctk.CTkFrame(parent, corner_radius=12, border_width=1, border_color="#334155")
        card.grid(row=0, column=col, padx=6, sticky="nsew")

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(pady=(12, 2))
        val_lbl = ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=24, weight="bold"), text_color=color)
        val_lbl.pack(pady=2)
        sub_lbl = ctk.CTkLabel(card, text=sub, font=ctk.CTkFont(size=13, weight="bold"), text_color="#CBD5E1")
        sub_lbl.pack(pady=(2, 12))
        return val_lbl, sub_lbl

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        ports.append("DEMO MODE")
        self.port_combo.configure(values=ports)
        if len(ports) > 1:
            self.port_combo.set(ports[0])
        else:
            self.port_combo.set("DEMO MODE")

    def toggle_connection(self):
        if not self.is_connected:
            selected = self.port_combo.get()
            if selected == "DEMO MODE":
                self.is_demo = True
                self.is_connected = True
                self.connect_btn.configure(text="Disconnect", fg_color="#EF4444", hover_color="#DC2626")
                self.log_lbl.configure(text="Running in DEMO MODE (Simulated Telemetry).", text_color="#38BDF8")
            else:
                try:
                    self.ser = serial.Serial(selected, 9600, timeout=1)
                    time.sleep(2)
                    self.is_demo = False
                    self.is_connected = True
                    self.connect_btn.configure(text="Disconnect", fg_color="#EF4444", hover_color="#DC2626")
                    self.log_lbl.configure(text=f"Connected to {selected} at 9600 baud.", text_color="#10B981")
                except Exception as e:
                    self.log_lbl.configure(text=f"Connection Error: {e}", text_color="#EF4444")
        else:
            self.is_connected = False
            self.is_demo = False
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.connect_btn.configure(text="Connect", fg_color="#10B981", hover_color="#059669")
            self.log_lbl.configure(text="Disconnected manually by user.", text_color="#F59E0B")

    def data_loop(self):
        while self.running:
            if self.is_connected:
                if self.is_demo:
                    import random
                    t = round(23.0 + random.uniform(-0.3, 0.5), 1)
                    g = random.randint(180, 195)
                    st = "SAFE"
                    cid = "A4F92B1C"
                    self.process_telemetry(t, g, st, cid)
                    time.sleep(0.5)
                elif self.ser and self.ser.is_open:
                    try:
                        line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                        if line.startswith("DATA,"):
                            parts = line.split(",")
                            if len(parts) == 5:
                                t = float(parts[1])
                                g = int(parts[2])
                                st = parts[3]
                                cid = parts[4]
                                self.process_telemetry(t, g, st, cid)
                    except Exception as e:
                        self.after(0, lambda: self.log_lbl.configure(
                            text=f"⚠️ Serial Disconnected! Cable unplugged or port lost.",
                            text_color="#EF4444"
                        ))
                        self.is_connected = False
                        self.after(0, lambda: self.connect_btn.configure(text="Connect", fg_color="#10B981"))
            else:
                time.sleep(0.2)

    def process_telemetry(self, temp, gas, status, card_id):
        self.current_temp = temp
        self.current_gas = gas
        self.current_status = status
        self.current_card = card_id

        # تحديد سبب الفصل بدقة
        if status == "DANGER_TEMP":
            self.shutdown_reason = f"High Temp ({temp}°C > {DANGER_TEMP}°C)"
        elif status == "DANGER_GAS":
            self.shutdown_reason = f"Gas Leak ({gas} PPM > {DANGER_GAS})"
        elif status == "LOCKED":
            self.shutdown_reason = "No RFID Card Scanned"
        elif status == "WARNING":
            if temp >= WARN_TEMP:
                self.shutdown_reason = f"Warning: Temp Rising ({temp}°C)"
            else:
                self.shutdown_reason = f"Warning: Gas Rising ({gas} PPM)"
        else:
            self.shutdown_reason = "All Systems Normal"

        now_str = datetime.now().strftime("%H:%M:%S")
        self.time_data.append(now_str)
        self.temp_data.append(temp)
        self.gas_data.append(gas)
        self.log_records.append([now_str, temp, gas, status, self.shutdown_reason, card_id])

        self.after(0, self.update_cards_ui)

    def update_cards_ui(self):
        self.temp_val.configure(text=f"{self.current_temp:.1f} °C")
        self.gas_val.configure(text=f"{self.current_gas} PPM")
        self.rfid_val.configure(text=self.current_card)

        if self.current_status == "LOCKED":
            self.status_val.configure(text="LOCKED", text_color="#EF4444")
            self.status_sub.configure(text=f"Reason: {self.shutdown_reason}", text_color="#FCA5A5")
            self.rfid_sub.configure(text="Engine Immobilized")
            if self.last_status != "LOCKED":
                self.log_lbl.configure(text="🔒 System Locked: Waiting for authorized RFID card.", text_color="#F59E0B")

        elif self.current_status == "SAFE":
            self.status_val.configure(text="SAFE / RUNNING", text_color="#10B981")
            self.status_sub.configure(text=self.shutdown_reason, text_color="#6EE7B7")
            self.rfid_sub.configure(text="Authorized Driver")
            if self.last_status != "SAFE":
                self.log_lbl.configure(text=f"✅ Engine Started! Driver ID: {self.current_card}", text_color="#10B981")

        elif self.current_status == "WARNING":
            self.status_val.configure(text="WARNING", text_color="#F59E0B")
            self.status_sub.configure(text=self.shutdown_reason, text_color="#FCD34D")
            self.rfid_sub.configure(text="Authorized Driver")
            self.log_lbl.configure(text=f"⚠️ {self.shutdown_reason}", text_color="#F59E0B")

        elif "DANGER" in self.current_status:
            self.status_val.configure(text="EMERGENCY STOP", text_color="#EF4444")
            self.status_sub.configure(text=f"Cause: {self.shutdown_reason}", text_color="#FCA5A5")
            self.rfid_sub.configure(text="Engine Cut-Off Active")
            self.log_lbl.configure(
                text=f"🚨 ENGINE CUT-OFF! Shutdown Cause: {self.shutdown_reason}",
                text_color="#EF4444"
            )

        self.last_status = self.current_status

    def update_plots(self):
        if not self.running:
            return

        self.ax_temp.clear()
        self.ax_gas.clear()

        self.ax_temp.set_facecolor("#0F172A")
        self.ax_gas.set_facecolor("#0F172A")

        x = list(range(len(self.temp_data)))
        if x:
            self.ax_temp.plot(x, list(self.temp_data), color="#38BDF8", linewidth=2.2, label="Temp (°C)")
            self.ax_gas.plot(x, list(self.gas_data), color="#F59E0B", linewidth=2.2, label="Gas (PPM)")

        self.ax_temp.axhline(DANGER_TEMP, color="#EF4444", linestyle="--", linewidth=1.2, label=f"Limit ({DANGER_TEMP}°C)")
        self.ax_gas.axhline(DANGER_GAS, color="#EF4444", linestyle="--", linewidth=1.2, label=f"Limit ({DANGER_GAS} PPM)")

        self.ax_temp.set_title("Real-Time Cabin Temperature (°C)", fontsize=11, fontweight="bold", color="white")
        self.ax_temp.set_ylim(15, 35)
        self.ax_temp.grid(True, linestyle=":", alpha=0.3)
        self.ax_temp.legend(loc="upper left", fontsize=8)

        self.ax_gas.set_title("Real-Time Gas / Smoke Level (PPM)", fontsize=11, fontweight="bold", color="white")
        self.ax_gas.set_ylim(100, 350)
        self.ax_gas.grid(True, linestyle=":", alpha=0.3)
        self.ax_gas.legend(loc="upper left", fontsize=8)

        self.canvas.draw()
        self.after(500, self.update_plots)

    def export_csv(self):
        if not self.log_records:
            self.log_lbl.configure(text="No data recorded yet to export.", text_color="#F59E0B")
            return
        filename = f"SafeRide_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Temperature_C", "Gas_PPM", "System_Status", "Shutdown_Reason", "Driver_Card_ID"])
            writer.writerows(self.log_records)
        self.log_lbl.configure(text=f"📁 Saved telemetry log (with shutdown reasons) to {filename}", text_color="#38BDF8")

    def on_closing(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.destroy()

if __name__ == "__main__":
    app = SafeRideDashboard()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
