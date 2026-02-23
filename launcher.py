"""
VRBOT Agent Launcher - GUI
Simple interface for starting/configuring the VRBOT Agent.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
import json
import time

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "launcher_config.json")
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


class VRBotLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VRBOT Agent v3.0")
        self.root.geometry("620x580")
        self.root.configure(bg="#0b0f1a")
        self.root.resizable(False, False)

        # Try to set icon
        try:
            self.root.iconbitmap(default="")
        except:
            pass

        self.process = None
        self.config = self._load_config()

        self._build_ui()
        self._check_status()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"user_id": "", "hub_url": "wss://ws.vrbot.me/ws", "ldplayer_path": r"C:\LDPlayer\LDPlayer9"}

    def _save_config(self):
        self.config["user_id"] = self.user_id_var.get().strip()
        self.config["hub_url"] = self.hub_url_var.get().strip()
        self.config["ldplayer_path"] = self.ldplayer_var.get().strip()
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def _build_ui(self):
        # Colors
        bg = "#0b0f1a"
        card_bg = "#1a1f2e"
        accent = "#7c3aed"
        green = "#10b981"
        red = "#ef4444"
        text = "#ffffff"
        dim = "#64748b"

        # Header
        header = tk.Frame(self.root, bg="#0f1629", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🤖 VRBOT Agent", font=("Segoe UI", 18, "bold"),
                 bg="#0f1629", fg=text).pack(side="left", padx=20, pady=15)
        tk.Label(header, text="v3.0", font=("Segoe UI", 10),
                 bg="#0f1629", fg=dim).pack(side="left", pady=15)

        # Status indicator
        self.status_frame = tk.Frame(header, bg="#0f1629")
        self.status_frame.pack(side="right", padx=20)
        self.status_dot = tk.Label(self.status_frame, text="●", font=("Segoe UI", 14),
                                    bg="#0f1629", fg=red)
        self.status_dot.pack(side="left")
        self.status_label = tk.Label(self.status_frame, text="Stopped",
                                      font=("Segoe UI", 10), bg="#0f1629", fg=dim)
        self.status_label.pack(side="left", padx=(5, 0))

        # Main content
        main = tk.Frame(self.root, bg=bg, padx=20, pady=15)
        main.pack(fill="both", expand=True)

        # Config card
        config_card = tk.LabelFrame(main, text=" Configuration ", font=("Segoe UI", 10, "bold"),
                                     bg=card_bg, fg=accent, padx=15, pady=10,
                                     relief="flat", borderwidth=1)
        config_card.pack(fill="x", pady=(0, 10))

        # User ID
        tk.Label(config_card, text="User ID (from vrbot.me):", font=("Segoe UI", 9),
                 bg=card_bg, fg=dim).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.user_id_var = tk.StringVar(value=self.config.get("user_id", ""))
        user_entry = tk.Entry(config_card, textvariable=self.user_id_var, width=50,
                              font=("Consolas", 9), bg="#0b0f1a", fg=text,
                              insertbackground=text, relief="flat", borderwidth=1)
        user_entry.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Hub URL
        tk.Label(config_card, text="Hub URL:", font=("Segoe UI", 9),
                 bg=card_bg, fg=dim).grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.hub_url_var = tk.StringVar(value=self.config.get("hub_url", "wss://ws.vrbot.me/ws"))
        hub_entry = tk.Entry(config_card, textvariable=self.hub_url_var, width=50,
                             font=("Consolas", 9), bg="#0b0f1a", fg=text,
                             insertbackground=text, relief="flat", borderwidth=1)
        hub_entry.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        # LDPlayer path
        tk.Label(config_card, text="LDPlayer Path:", font=("Segoe UI", 9),
                 bg=card_bg, fg=dim).grid(row=4, column=0, sticky="w", pady=(0, 5))
        self.ldplayer_var = tk.StringVar(value=self.config.get("ldplayer_path", r"C:\LDPlayer\LDPlayer9"))
        ld_entry = tk.Entry(config_card, textvariable=self.ldplayer_var, width=50,
                            font=("Consolas", 9), bg="#0b0f1a", fg=text,
                            insertbackground=text, relief="flat", borderwidth=1)
        ld_entry.grid(row=5, column=0, sticky="ew")

        config_card.columnconfigure(0, weight=1)

        # Buttons
        btn_frame = tk.Frame(main, bg=bg)
        btn_frame.pack(fill="x", pady=(5, 10))

        self.start_btn = tk.Button(btn_frame, text="▶  Start Agent", font=("Segoe UI", 11, "bold"),
                                    bg=green, fg="white", relief="flat", padx=20, pady=8,
                                    cursor="hand2", command=self._start_agent)
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = tk.Button(btn_frame, text="⏹  Stop", font=("Segoe UI", 11, "bold"),
                                   bg=red, fg="white", relief="flat", padx=20, pady=8,
                                   cursor="hand2", command=self._stop_agent, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 8))

        tk.Button(btn_frame, text="🌐 Dashboard", font=("Segoe UI", 9),
                  bg="#1e293b", fg=dim, relief="flat", padx=12, pady=8,
                  cursor="hand2", command=lambda: os.startfile("https://www.vrbot.me/dashboard")
                  ).pack(side="right")

        # Log area
        log_card = tk.LabelFrame(main, text=" Logs ", font=("Segoe UI", 10, "bold"),
                                  bg=card_bg, fg=accent, padx=10, pady=8,
                                  relief="flat", borderwidth=1)
        log_card.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(log_card, height=12, wrap="word",
                                                   font=("Consolas", 9), bg="#0d1117",
                                                   fg="#8b949e", insertbackground=text,
                                                   relief="flat", borderwidth=0)
        self.log_text.pack(fill="both", expand=True)
        self._log("VRBOT Agent Launcher ready.")
        self._log("Enter your User ID from vrbot.me and click Start.")

    def _log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")

    def _check_status(self):
        """Check system status."""
        # Check Python
        self._log(f"Python: {sys.version.split()[0]}")

        # Check LDPlayer
        ldpath = self.ldplayer_var.get()
        if os.path.exists(os.path.join(ldpath, "ldconsole.exe")):
            self._log("LDPlayer 9: Found ✅")
        else:
            self._log("LDPlayer 9: Not found ⚠️")

        # Check ADB
        try:
            r = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
            self._log("ADB: Found ✅")
        except:
            self._log("ADB: Not in PATH ⚠️")

    def _start_agent(self):
        user_id = self.user_id_var.get().strip()
        if not user_id:
            messagebox.showwarning("Missing User ID",
                                    "Please enter your User ID from vrbot.me dashboard.\n\n"
                                    "Go to vrbot.me → Settings → Copy your User ID")
            return

        self._save_config()

        hub_url = self.hub_url_var.get().strip()
        ldpath = self.ldplayer_var.get().strip()

        cmd = [
            sys.executable, os.path.join(AGENT_DIR, "main.py"),
            "--hub",
            f"--user-id={user_id}",
            f"--hub-url={hub_url}",
            f"--ldplayer={ldpath}",
        ]

        self._log(f"Starting agent...")
        self._log(f"User: {user_id[:20]}...")
        self._log(f"Hub: {hub_url}")

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=AGENT_DIR
            )

            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_dot.config(fg="#10b981")
            self.status_label.config(text="Running")

            # Read output in thread
            thread = threading.Thread(target=self._read_output, daemon=True)
            thread.start()

        except Exception as e:
            self._log(f"Error starting agent: {e}")
            messagebox.showerror("Start Error", str(e))

    def _read_output(self):
        """Read agent stdout and display in log."""
        try:
            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self.root.after(0, self._log, line)

            # Process ended
            self.root.after(0, self._on_agent_stopped)
        except:
            self.root.after(0, self._on_agent_stopped)

    def _stop_agent(self):
        if self.process:
            self._log("Stopping agent...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.process = None
        self._on_agent_stopped()

    def _on_agent_stopped(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_dot.config(fg="#ef4444")
        self.status_label.config(text="Stopped")
        self._log("Agent stopped.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = VRBotLauncher()
    app.run()
