import json
import os
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import requests

API_URL = "https://smmflare.com/api/v2"
REFILL_URL = "https://smmflare.com/addfunds"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smmflare_config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)


class SMMFlareAPI:
    def __init__(self, key):
        self.key = key

    def _post(self, data):
        payload = {"key": self.key}
        payload.update(data)
        resp = requests.post(API_URL, data=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def balance(self):
        return self._post({"action": "balance"})

    def services(self):
        return self._post({"action": "services"})

    def add_order(self, service_id, link, quantity):
        return self._post({
            "action": "add",
            "service": service_id,
            "link": link,
            "quantity": quantity,
        })

    def order_status(self, order_id):
        return self._post({"action": "status", "order": order_id})


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SMMflare Client")
        self.geometry("800x600")

        cfg = load_config()
        self.api_key = cfg.get("api_key", "")
        if not self.api_key:
            self.prompt_for_key()

        self.api = SMMFlareAPI(self.api_key)
        self.services_cache = []

        self.build_ui()
        self.refresh_balance()
        self.refresh_services()

    def prompt_for_key(self):
        key = simpledialog.askstring("API Key", "Enter your SMMflare API key:", show="*")
        if not key:
            messagebox.showerror("Error", "An API key is required.")
            self.destroy()
            raise SystemExit
        self.api_key = key.strip()
        save_config({"api_key": self.api_key})

    def build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        self.balance_var = tk.StringVar(value="Balance: loading...")
        ttk.Label(top, textvariable=self.balance_var, font=("Segoe UI", 12, "bold")).pack(side="left")

        ttk.Button(top, text="Refresh Balance", command=self.refresh_balance).pack(side="left", padx=6)
        ttk.Button(top, text="Refill Balance", command=self.open_refill).pack(side="left", padx=6)
        ttk.Button(top, text="Change API Key", command=self.change_key).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        services_tab = ttk.Frame(nb)
        nb.add(services_tab, text="Services")

        search_row = ttk.Frame(services_tab)
        search_row.pack(fill="x", pady=4)
        ttk.Label(search_row, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.filter_services())
        ttk.Entry(search_row, textvariable=self.search_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(search_row, text="Reload", command=self.refresh_services).pack(side="left")

        columns = ("id", "name", "category", "rate", "min", "max")
        self.tree = ttk.Treeview(services_tab, columns=columns, show="headings")
        for col, label, width in [
            ("id", "ID", 60),
            ("name", "Service", 320),
            ("category", "Category", 160),
            ("rate", "Rate/1000", 90),
            ("min", "Min", 60),
            ("max", "Max", 80),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self.on_service_select)

        order_tab = ttk.Frame(nb)
        nb.add(order_tab, text="Place Order")

        form = ttk.Frame(order_tab, padding=10)
        form.pack(fill="x")

        ttk.Label(form, text="Service ID:").grid(row=0, column=0, sticky="w", pady=4)
        self.order_service_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.order_service_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Link:").grid(row=1, column=0, sticky="w", pady=4)
        self.order_link_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.order_link_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Quantity:").grid(row=2, column=0, sticky="w", pady=4)
        self.order_qty_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.order_qty_var).grid(row=2, column=1, sticky="ew", pady=4)

        form.columnconfigure(1, weight=1)

        ttk.Button(order_tab, text="Place Order", command=self.place_order).pack(pady=10)

        self.order_result_var = tk.StringVar()
        ttk.Label(order_tab, textvariable=self.order_result_var, wraplength=700).pack(pady=4)

        status_tab = ttk.Frame(nb)
        nb.add(status_tab, text="Order Status")

        sform = ttk.Frame(status_tab, padding=10)
        sform.pack(fill="x")
        ttk.Label(sform, text="Order ID:").grid(row=0, column=0, sticky="w")
        self.status_order_var = tk.StringVar()
        ttk.Entry(sform, textvariable=self.status_order_var).grid(row=0, column=1, sticky="ew", padx=6)
        sform.columnconfigure(1, weight=1)
        ttk.Button(sform, text="Check Status", command=self.check_status).grid(row=0, column=2, padx=6)

        self.status_result_var = tk.StringVar()
        ttk.Label(status_tab, textvariable=self.status_result_var, wraplength=700, justify="left").pack(
            padx=10, pady=10, anchor="w"
        )

        self.status_bar = ttk.Label(self, text="Ready", relief="sunken", anchor="w")
        self.status_bar.pack(fill="x", side="bottom")

    def run_async(self, fn, on_done):
        def worker():
            try:
                result = fn()
                self.after(0, lambda: on_done(result, None))
            except Exception as e:
                self.after(0, lambda: on_done(None, e))
        threading.Thread(target=worker, daemon=True).start()

    def refresh_balance(self):
        self.status_bar.config(text="Fetching balance...")

        def done(result, err):
            if err:
                self.balance_var.set("Balance: error")
                self.status_bar.config(text=f"Error: {err}")
                return
            if "error" in result:
                self.balance_var.set("Balance: error")
                self.status_bar.config(text=f"API error: {result['error']}")
                return
            bal = result.get("balance", "?")
            cur = result.get("currency", "")
            self.balance_var.set(f"Balance: {bal} {cur}")
            self.status_bar.config(text="Balance updated")

        self.run_async(self.api.balance, done)

    def refresh_services(self):
        self.status_bar.config(text="Loading services...")

        def done(result, err):
            if err:
                self.status_bar.config(text=f"Error: {err}")
                return
            if isinstance(result, dict) and "error" in result:
                self.status_bar.config(text=f"API error: {result['error']}")
                return
            self.services_cache = result if isinstance(result, list) else []
            self.render_services(self.services_cache)
            self.status_bar.config(text=f"Loaded {len(self.services_cache)} services")

        self.run_async(self.api.services, done)

    def render_services(self, services):
        self.tree.delete(*self.tree.get_children())
        for s in services:
            self.tree.insert("", "end", values=(
                s.get("service", ""),
                s.get("name", ""),
                s.get("category", ""),
                s.get("rate", ""),
                s.get("min", ""),
                s.get("max", ""),
            ))

    def filter_services(self):
        q = self.search_var.get().lower().strip()
        if not q:
            self.render_services(self.services_cache)
            return
        filtered = [
            s for s in self.services_cache
            if q in str(s.get("name", "")).lower() or q in str(s.get("category", "")).lower()
        ]
        self.render_services(filtered)

    def on_service_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        if values:
            self.order_service_var.set(values[0])

    def place_order(self):
        service_id = self.order_service_var.get().strip()
        link = self.order_link_var.get().strip()
        qty = self.order_qty_var.get().strip()

        if not service_id or not link or not qty:
            messagebox.showwarning("Missing info", "Please fill in Service ID, Link, and Quantity.")
            return
        if not qty.isdigit():
            messagebox.showwarning("Invalid quantity", "Quantity must be a number.")
            return

        if not messagebox.askyesno(
            "Confirm order",
            f"Place order?\n\nService: {service_id}\nLink: {link}\nQuantity: {qty}",
        ):
            return

        self.status_bar.config(text="Placing order...")

        def done(result, err):
            if err:
                self.order_result_var.set(f"Error: {err}")
                self.status_bar.config(text="Order failed")
                return
            if "error" in result:
                self.order_result_var.set(f"API error: {result['error']}")
                self.status_bar.config(text="Order failed")
                return
            self.order_result_var.set(f"Order placed. Order ID: {result.get('order')}")
            self.status_bar.config(text="Order placed")

        self.run_async(lambda: self.api.add_order(service_id, link, int(qty)), done)

    def check_status(self):
        order_id = self.status_order_var.get().strip()
        if not order_id:
            messagebox.showwarning("Missing info", "Enter an Order ID.")
            return

        self.status_bar.config(text="Checking status...")

        def done(result, err):
            if err:
                self.status_result_var.set(f"Error: {err}")
                self.status_bar.config(text="Status check failed")
                return
            if "error" in result:
                self.status_result_var.set(f"API error: {result['error']}")
                self.status_bar.config(text="Status check failed")
                return
            lines = [f"{k}: {v}" for k, v in result.items()]
            self.status_result_var.set("\n".join(lines))
            self.status_bar.config(text="Status updated")

        self.run_async(lambda: self.api.order_status(order_id), done)

    def open_refill(self):
        webbrowser.open(REFILL_URL)

    def change_key(self):
        key = simpledialog.askstring("API Key", "Enter new API key:", show="*")
        if key:
            self.api_key = key.strip()
            self.api = SMMFlareAPI(self.api_key)
            save_config({"api_key": self.api_key})
            self.refresh_balance()
            self.refresh_services()


if __name__ == "__main__":
    app = App()
    app.mainloop()
