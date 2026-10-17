"""
Expense Tracker — Tkinter desktop application
Requirements:
    pip install matplotlib
Run:
    python expense_tracker.py

Data files are stored beside this script:
    expenses.csv
    categories.json
"""

import csv
import json
import os
import sys
import logging
import math
from functools import wraps
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# When packaged with PyInstaller, keep user data beside the executable rather than
# inside PyInstaller's temporary extraction directory.
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
LOG_FILE = APP_DIR / "expense_tracker.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")


def log_operation(function):
    """Decorator that logs the start and successful completion of an operation."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        logging.info("Started %s", function.__name__)
        result = function(*args, **kwargs)
        logging.info("Finished %s", function.__name__)
        return result
    return wrapper


def recursive_sum(values):
    """Recursively add numeric values using divide-and-conquer recursion."""
    values = list(values)
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    middle = len(values) // 2
    return recursive_sum(values[:middle]) + recursive_sum(values[middle:])


DATA_FILE = APP_DIR / "expenses.csv"
CATEGORIES_FILE = APP_DIR / "categories.json"
CSV_FIELDS = ["Date", "Category", "Amount", "Method", "Notes"]
DEFAULT_CATEGORIES = [
    "Food", "Transportation", "School", "Bills", "Shopping",
    "Health", "Entertainment", "Groceries", "Other"
]
PAYMENT_METHODS = ["Cash", "GCash", "Maya", "Debit Card", "Credit Card", "Bank Transfer", "Other"]


def parse_date(value):
    """Return a date object for a YYYY-MM-DD string."""
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def money(value):
    return f"₱{value:,.2f}"


class ExpenseTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Expense Tracker")
        self.root.geometry("1150x760")
        self.root.minsize(850, 600)

        self.categories = self.load_categories()
        self.expenses = self.load_expenses()
        self.filtered_expenses = list(self.expenses)
        self.sort_state = {}
        self.dark_mode = False

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.build_ui()
        self.refresh_table()
        self.refresh_analytics()

    # ---------- Local storage ----------
    def load_categories(self):
        if CATEGORIES_FILE.exists():
            try:
                data = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return [str(item) for item in data]
            except (OSError, json.JSONDecodeError):
                pass
        self.save_categories(DEFAULT_CATEGORIES)
        return DEFAULT_CATEGORIES.copy()

    @log_operation
    def save_categories(self, categories=None):
        if categories is not None:
            self.categories = categories
        CATEGORIES_FILE.write_text(
            json.dumps(self.categories, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load_expenses(self):
        records = []
        if not DATA_FILE.exists():
            with DATA_FILE.open("w", newline="", encoding="utf-8") as file:
                csv.DictWriter(file, fieldnames=CSV_FIELDS).writeheader()
            return records

        try:
            with DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        day = parse_date(row.get("Date", ""))
                        amount = float(row.get("Amount", ""))
                        category = (row.get("Category") or "").strip()
                        if math.isfinite(amount) and amount > 0 and category:
                            records.append({
                                "Date": day.isoformat(),
                                "Category": category,
                                "Amount": amount,
                                "Method": (row.get("Method") or "").strip(),
                                "Notes": (row.get("Notes") or "").strip()
                            })
                    except (ValueError, TypeError):
                        continue
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not read expenses.csv:\n{exc}")
        return records

    @log_operation
    def save_expenses(self):
        try:
            with DATA_FILE.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for item in self.expenses:
                    writer.writerow(item)
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not save expenses:\n{exc}")

    # ---------- Main layout ----------
    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, padding=10)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.transactions_tab = ttk.Frame(self.notebook, padding=8)
        self.analytics_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.transactions_tab, text="Transactions")
        self.notebook.add(self.analytics_tab, text="Analytics")

        self.build_transactions_tab()
        self.build_analytics_tab()

        bottom = ttk.Frame(outer)
        bottom.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.status_var, anchor="w").grid(row=0, column=0, sticky="ew")
        ttk.Button(bottom, text="Settings", command=self.open_settings).grid(row=0, column=1, padx=4)
        ttk.Button(bottom, text="Toggle Theme", command=self.toggle_theme).grid(row=0, column=2)

    def build_transactions_tab(self):
        tab = self.transactions_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for text, command in [
            ("Add", self.add_expense),
            ("Edit Selected", self.edit_selected),
            ("Delete Selected", self.delete_selected),
            ("Filter", self.apply_filters),
            ("Clear Filters", self.clear_filters),
            ("Import CSV", self.import_csv),
            ("Export CSV", self.export_csv),
        ]:
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=(0, 5))

        filters = ttk.LabelFrame(tab, text="Filters (date format YYYY-MM-DD)", padding=7)
        filters.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for col in range(8):
            filters.columnconfigure(col, weight=1 if col in (1, 3, 5, 7) else 0)

        self.start_filter = tk.StringVar()
        self.end_filter = tk.StringVar()
        self.category_filter = tk.StringVar(value="All")
        self.min_filter = tk.StringVar()
        self.max_filter = tk.StringVar()
        ttk.Label(filters, text="From").grid(row=0, column=0, sticky="w", padx=3)
        ttk.Entry(filters, textvariable=self.start_filter, width=12).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Label(filters, text="To").grid(row=0, column=2, sticky="w", padx=3)
        ttk.Entry(filters, textvariable=self.end_filter, width=12).grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Label(filters, text="Category").grid(row=0, column=4, sticky="w", padx=3)
        self.category_combo = ttk.Combobox(
            filters, textvariable=self.category_filter,
            values=["All"] + self.categories, state="readonly", width=15
        )
        self.category_combo.grid(row=0, column=5, sticky="ew", padx=3)
        ttk.Label(filters, text="Min ₱").grid(row=0, column=6, sticky="w", padx=3)
        ttk.Entry(filters, textvariable=self.min_filter, width=10).grid(row=0, column=7, sticky="ew", padx=3)
        ttk.Label(filters, text="Max ₱").grid(row=1, column=6, sticky="w", padx=3, pady=(5, 0))
        ttk.Entry(filters, textvariable=self.max_filter, width=10).grid(row=1, column=7, sticky="ew", padx=3, pady=(5, 0))

        table_frame = ttk.Frame(tab)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=CSV_FIELDS, show="headings", selectmode="browse")
        widths = {"Date": 110, "Category": 150, "Amount": 120, "Method": 130, "Notes": 400}
        for col in CSV_FIELDS:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=widths[col], minwidth=70, anchor="w")
        self.tree.column("Amount", anchor="e")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())

    def build_analytics_tab(self):
        tab = self.analytics_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        controls = ttk.Frame(tab)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="Analytics period:").pack(side="left", padx=(0, 8))
        self.period_var = tk.StringVar(value="This Month")
        self.period_combo = ttk.Combobox(
            controls, textvariable=self.period_var,
            values=["This Week", "This Month", "All Time", "Custom…"],
            state="readonly", width=15
        )
        self.period_combo.pack(side="left")
        self.period_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_analytics())
        ttk.Button(controls, text="Choose Custom Dates", command=self.choose_custom_period).pack(side="left", padx=8)

        charts = ttk.Frame(tab)
        charts.grid(row=1, column=0, sticky="nsew")
        charts.columnconfigure(0, weight=1)
        charts.columnconfigure(1, weight=1)
        charts.rowconfigure(0, weight=1)

        self.trend_fig = Figure(figsize=(5, 3.4), dpi=100, tight_layout=True)
        self.trend_ax = self.trend_fig.add_subplot(111)
        self.trend_canvas = FigureCanvasTkAgg(self.trend_fig, master=charts)
        self.trend_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.category_fig = Figure(figsize=(5, 3.4), dpi=100, tight_layout=True)
        self.category_ax = self.category_fig.add_subplot(111)
        self.category_canvas = FigureCanvasTkAgg(self.category_fig, master=charts)
        self.category_canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        kpis = ttk.LabelFrame(tab, text="Spending Summary", padding=12)
        kpis.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for i in range(6):
            kpis.columnconfigure(i, weight=1)
        self.kpi_total = tk.StringVar(value="₱0.00")
        self.kpi_average = tk.StringVar(value="₱0.00")
        self.kpi_largest = tk.StringVar(value="₱0.00")
        self.kpi_today = tk.StringVar(value="₱0.00")
        self.kpi_week = tk.StringVar(value="₱0.00")
        self.kpi_month = tk.StringVar(value="₱0.00")
        kpi_items = [
            ("Period Total", self.kpi_total), ("Average Expense", self.kpi_average),
            ("Largest Expense", self.kpi_largest), ("Today", self.kpi_today),
            ("This Week", self.kpi_week), ("This Month", self.kpi_month)
        ]
        for index, (label, variable) in enumerate(kpi_items):
            ttk.Label(kpis, text=label).grid(row=0, column=index, padx=5, pady=(0, 4))
            ttk.Label(kpis, textvariable=variable, font=("TkDefaultFont", 11, "bold")).grid(row=1, column=index, padx=5)

        self.top_categories_var = tk.StringVar(value="Top categories: —")
        ttk.Label(tab, textvariable=self.top_categories_var, anchor="w").grid(row=3, column=0, sticky="ew", pady=(8, 0))

    # ---------- Expense operations ----------
    def add_expense(self):
        self.expense_dialog()

    def edit_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a record", "Please select an expense to edit.")
            return
        try:
            index = int(selected[0])
            item = self.expenses[index]
        except (ValueError, IndexError):
            return
        self.expense_dialog(item, index)

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a record", "Please select an expense to delete.")
            return
        index = int(selected[0])
        if index < 0 or index >= len(self.expenses):
            return
        item = self.expenses[index]
        if messagebox.askyesno("Confirm Delete", f"Delete {item['Category']} expense of {money(item['Amount'])} on {item['Date']}?"):
            del self.expenses[index]
            self.save_expenses()
            self.refresh_table()
            self.refresh_analytics()

    def expense_dialog(self, item=None, index=None):
        editing = item is not None
        win = tk.Toplevel(self.root)
        win.title("Edit Expense" if editing else "Add Expense")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        date_var = tk.StringVar(value=item["Date"] if editing else date.today().isoformat())
        category_var = tk.StringVar(value=item["Category"] if editing else (self.categories[0] if self.categories else ""))
        amount_var = tk.StringVar(value=f"{item['Amount']:.2f}" if editing else "")
        method_var = tk.StringVar(value=item["Method"] if editing else "")
        notes_var = tk.StringVar(value=item["Notes"] if editing else "")
        error_var = tk.StringVar()

        fields = [
            ("Date (YYYY-MM-DD)", ttk.Entry(frame, textvariable=date_var, width=32)),
            ("Category", ttk.Combobox(frame, textvariable=category_var, values=self.categories, state="readonly", width=29)),
            ("Amount (₱)", ttk.Entry(frame, textvariable=amount_var, width=32)),
            ("Payment Method", ttk.Combobox(frame, textvariable=method_var, values=[""] + PAYMENT_METHODS, width=29)),
            ("Notes", ttk.Entry(frame, textvariable=notes_var, width=32)),
        ]
        for row, (label, widget) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
            widget.grid(row=row, column=1, sticky="ew", pady=6)

        ttk.Label(frame, textvariable=error_var, foreground="red", wraplength=360).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", pady=(4, 8)
        )

        def save():
            try:
                parsed_day = parse_date(date_var.get())
                if parsed_day > date.today():
                    raise ValueError("Date cannot be in the future.")
            except ValueError:
                error_var.set("Enter a valid date in YYYY-MM-DD format (not a future date).")
                return
            category = category_var.get().strip()
            if not category:
                error_var.set("Please choose a category.")
                return
            try:
                amount = float(amount_var.get().strip())
                if amount <= 0 or amount != amount or amount == float("inf"):
                    raise ValueError
            except ValueError:
                error_var.set("Amount must be a positive number, such as 125.50.")
                return

            record = {
                "Date": parsed_day.isoformat(),
                "Category": category,
                "Amount": round(amount, 2),
                "Method": method_var.get().strip(),
                "Notes": notes_var.get().strip()
            }
            if editing:
                self.expenses[index] = record
            else:
                self.expenses.append(record)
            self.save_expenses()
            self.refresh_table()
            self.refresh_analytics()
            win.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(4, 0))
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Save", command=save).pack(side="right")
        win.bind("<Return>", lambda _event: save())
        win.bind("<Escape>", lambda _event: win.destroy())
        win.update_idletasks()
        win.geometry(f"+{self.root.winfo_rootx()+100}+{self.root.winfo_rooty()+80}")

    # ---------- Table, filters and sorting ----------
    def refresh_table(self):
        """Rebuild the table using the currently selected filters."""
        self.apply_filters(show_error=False)

    def apply_filters(self, show_error=True):
        try:
            start = parse_date(self.start_filter.get()) if self.start_filter.get().strip() else None
            end = parse_date(self.end_filter.get()) if self.end_filter.get().strip() else None
            if start and end and start > end:
                raise ValueError("Start date must be on or before end date.")
            min_amount = float(self.min_filter.get()) if self.min_filter.get().strip() else None
            max_amount = float(self.max_filter.get()) if self.max_filter.get().strip() else None
            if min_amount is not None and min_amount < 0:
                raise ValueError("Minimum amount cannot be negative.")
            if max_amount is not None and max_amount < 0:
                raise ValueError("Maximum amount cannot be negative.")
            if min_amount is not None and max_amount is not None and min_amount > max_amount:
                raise ValueError("Minimum amount cannot exceed maximum amount.")
        except ValueError as exc:
            if show_error:
                messagebox.showerror("Invalid Filter", f"Check your filter values.\n{exc}")
            return

        category = self.category_filter.get()
        result = []
        for item in self.expenses:
            day = parse_date(item["Date"])
            if start and day < start:
                continue
            if end and day > end:
                continue
            if category and category != "All" and item["Category"] != category:
                continue
            if min_amount is not None and item["Amount"] < min_amount:
                continue
            if max_amount is not None and item["Amount"] > max_amount:
                continue
            result.append(item)
        self.filtered_expenses = result
        if hasattr(self, "tree"):
            self.tree.delete(*self.tree.get_children())
            # Use original indexes so edit/delete operate on the source list.
            for index, item in enumerate(self.expenses):
                if any(item is candidate for candidate in self.filtered_expenses):
                    self.tree.insert("", "end", iid=str(index), values=(
                        item["Date"], item["Category"], f"{item['Amount']:,.2f}",
                        item["Method"], item["Notes"]
                    ))
            total = recursive_sum([item["Amount"] for item in self.filtered_expenses])
            self.status_var.set(f"Records: {len(self.filtered_expenses)}    Total Spent: {money(total)}")

    def clear_filters(self):
        self.start_filter.set("")
        self.end_filter.set("")
        self.category_filter.set("All")
        self.min_filter.set("")
        self.max_filter.set("")
        self.refresh_table()

    def sort_by(self, column):
        reverse = self.sort_state.get(column, False)
        self.sort_state[column] = not reverse

        def key(item):
            value = item[column]
            if column == "Amount":
                return float(value)
            if column == "Date":
                return parse_date(value)
            return str(value).casefold()

        self.filtered_expenses.sort(key=key, reverse=reverse)
        self.tree.delete(*self.tree.get_children())
        for item in self.filtered_expenses:
            original_index = next(i for i, source in enumerate(self.expenses) if source is item)
            self.tree.insert("", "end", iid=str(original_index), values=(
                item["Date"], item["Category"], f"{item['Amount']:,.2f}",
                item["Method"], item["Notes"]
            ))

    # ---------- Analytics ----------
    def choose_custom_period(self):
        win = tk.Toplevel(self.root)
        win.title("Custom Analytics Period")
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)
        start_var = tk.StringVar(value=getattr(self, "custom_start", date.today().replace(day=1).isoformat()))
        end_var = tk.StringVar(value=getattr(self, "custom_end", date.today().isoformat()))
        ttk.Label(frame, text="Start date (YYYY-MM-DD)").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=start_var, width=18).grid(row=0, column=1, padx=8, pady=5)
        ttk.Label(frame, text="End date (YYYY-MM-DD)").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=end_var, width=18).grid(row=1, column=1, padx=8, pady=5)
        def apply():
            try:
                start, end = parse_date(start_var.get()), parse_date(end_var.get())
                if start > end:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid dates", "Use YYYY-MM-DD dates and ensure start is not after end.", parent=win)
                return
            self.custom_start, self.custom_end = start.isoformat(), end.isoformat()
            self.period_var.set("Custom…")
            self.refresh_analytics()
            win.destroy()
        ttk.Button(frame, text="Apply", command=apply).grid(row=2, column=0, columnspan=2, pady=8)

    def get_analytics_expenses(self):
        today = date.today()
        if self.period_var.get() == "This Week":
            start = today - timedelta(days=today.weekday())
            end = today
        elif self.period_var.get() == "This Month":
            start, end = today.replace(day=1), today
        elif self.period_var.get() == "Custom…":
            start = parse_date(getattr(self, "custom_start", today.replace(day=1).isoformat()))
            end = parse_date(getattr(self, "custom_end", today.isoformat()))
        else:
            start, end = date.min, today
        return [
            item for item in self.expenses
            if start <= parse_date(item["Date"]) <= end
        ]

    def refresh_analytics(self):
        if not hasattr(self, "trend_ax"):
            return
        try:
            records = self.get_analytics_expenses()
        except ValueError:
            records = []
        self.trend_ax.clear()
        self.category_ax.clear()

        by_day = defaultdict(float)
        by_category = defaultdict(float)
        for item in records:
            by_day[parse_date(item["Date"])] += item["Amount"]
            by_category[item["Category"]] += item["Amount"]

        if by_day:
            days = sorted(by_day)
            self.trend_ax.plot(days, [by_day[day] for day in days], marker="o", linewidth=2)
            self.trend_ax.set_title("Spending Trend")
            self.trend_ax.set_xlabel("Date")
            self.trend_ax.set_ylabel("Amount (₱)")
            self.trend_ax.tick_params(axis="x", labelrotation=35)
            self.trend_ax.grid(True, alpha=0.25)
        else:
            self.trend_ax.text(0.5, 0.5, "No expenses for this period", ha="center", va="center", transform=self.trend_ax.transAxes)
            self.trend_ax.set_axis_off()

        if by_category:
            categories = sorted(by_category, key=by_category.get)
            values = [by_category[category] for category in categories]
            self.category_ax.barh(categories, values)
            self.category_ax.set_title("Category Breakdown")
            self.category_ax.set_xlabel("Amount (₱)")
            self.category_ax.grid(axis="x", alpha=0.25)
            self.category_ax.set_axisbelow(True)
        else:
            self.category_ax.text(0.5, 0.5, "No category data", ha="center", va="center", transform=self.category_ax.transAxes)
            self.category_ax.set_axis_off()

        self.trend_fig.tight_layout()
        self.category_fig.tight_layout()
        self.trend_canvas.draw_idle()
        self.category_canvas.draw_idle()

        total = recursive_sum([item["Amount"] for item in records])
        average = total / len(records) if records else 0
        largest = max((item["Amount"] for item in records), default=0)
        self.kpi_total.set(money(total))
        self.kpi_average.set(money(average))
        self.kpi_largest.set(money(largest))

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        today_total = sum(i["Amount"] for i in self.expenses if parse_date(i["Date"]) == today)
        week_total = sum(i["Amount"] for i in self.expenses if week_start <= parse_date(i["Date"]) <= today)
        month_total = sum(i["Amount"] for i in self.expenses if month_start <= parse_date(i["Date"]) <= today)
        self.kpi_today.set(money(today_total))
        self.kpi_week.set(money(week_total))
        self.kpi_month.set(money(month_total))

        top = sorted(by_category.items(), key=lambda pair: pair[1], reverse=True)[:3]
        if top:
            self.top_categories_var.set("Top categories: " + "   •   ".join(f"{name}: {money(value)}" for name, value in top))
        else:
            self.top_categories_var.set("Top categories: —")

    # ---------- Import / export ----------
    @log_operation
    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Export expenses",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="expenses_export.csv"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for item in self.filtered_expenses:
                    writer.writerow(item)
            messagebox.showinfo("Export Complete", f"Exported {len(self.filtered_expenses)} records.")
        except OSError as exc:
            messagebox.showerror("Export Error", str(exc))

    @log_operation
    def import_csv(self):
        path = filedialog.askopenfilename(
            title="Import expenses CSV",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        existing_keys = {
            (item["Date"], round(float(item["Amount"]), 2), item["Category"].strip().casefold())
            for item in self.expenses
        }
        added = 0
        skipped = 0
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                if not reader.fieldnames or not set(CSV_FIELDS).issubset(set(reader.fieldnames)):
                    raise ValueError("CSV must contain these columns: " + ", ".join(CSV_FIELDS))
                for row in reader:
                    try:
                        day = parse_date(row["Date"]).isoformat()
                        amount = float(row["Amount"])
                        category = row["Category"].strip()
                        if not math.isfinite(amount) or amount <= 0 or not category:
                            skipped += 1
                            continue
                        key = (day, round(amount, 2), category.casefold())
                        if key in existing_keys:
                            skipped += 1
                            continue
                        self.expenses.append({
                            "Date": day,
                            "Category": category,
                            "Amount": round(amount, 2),
                            "Method": (row.get("Method") or "").strip(),
                            "Notes": (row.get("Notes") or "").strip()
                        })
                        existing_keys.add(key)
                        added += 1
                    except (ValueError, KeyError, TypeError):
                        skipped += 1
            self.save_expenses()
            self.refresh_table()
            self.refresh_analytics()
            messagebox.showinfo("Import Complete", f"Added: {added}\nSkipped invalid or duplicate rows: {skipped}")
        except (OSError, ValueError, csv.Error) as exc:
            messagebox.showerror("Import Error", str(exc))

    # ---------- Settings ----------
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings — Categories")
        win.transient(self.root)
        win.grab_set()
        win.geometry("420x400")
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        listing = tk.Listbox(frame, height=12, exportselection=False)
        listing.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        for category in self.categories:
            listing.insert("end", category)
        entry_var = tk.StringVar()
        ttk.Entry(frame, textvariable=entry_var).grid(row=1, column=0, sticky="ew", padx=(0, 5))

        def add_category():
            name = entry_var.get().strip()
            if not name:
                messagebox.showerror("Invalid Category", "Category name cannot be empty.", parent=win)
                return
            if any(existing.casefold() == name.casefold() for existing in self.categories):
                messagebox.showerror("Duplicate Category", "That category already exists.", parent=win)
                return
            self.categories.append(name)
            listing.insert("end", name)
            entry_var.set("")
            self.finish_category_settings()

        def rename_category():
            selection = listing.curselection()
            name = entry_var.get().strip()
            if not selection:
                messagebox.showinfo("Select Category", "Select a category to rename.", parent=win)
                return
            if not name:
                messagebox.showerror("Invalid Category", "Enter a new category name.", parent=win)
                return
            old = listing.get(selection[0])
            if any(c.casefold() == name.casefold() and c != old for c in self.categories):
                messagebox.showerror("Duplicate Category", "That category already exists.", parent=win)
                return
            self.categories[self.categories.index(old)] = name
            for expense in self.expenses:
                if expense["Category"] == old:
                    expense["Category"] = name
            listing.delete(selection[0])
            listing.insert(selection[0], name)
            entry_var.set("")
            self.finish_category_settings()

        def delete_category():
            selection = listing.curselection()
            if not selection:
                messagebox.showinfo("Select Category", "Select a category to delete.", parent=win)
                return
            name = listing.get(selection[0])
            used = any(item["Category"] == name for item in self.expenses)
            if used:
                messagebox.showerror("Category In Use", "This category is used by existing expenses. Rename it instead, or edit/delete those expenses first.", parent=win)
                return
            if messagebox.askyesno("Delete Category", f"Delete category '{name}'?", parent=win):
                self.categories.remove(name)
                listing.delete(selection[0])
                self.finish_category_settings()

        ttk.Button(frame, text="Add", command=add_category).grid(row=1, column=1, padx=3)
        ttk.Button(frame, text="Rename", command=rename_category).grid(row=1, column=2, padx=3)
        ttk.Button(frame, text="Delete", command=delete_category).grid(row=2, column=0, sticky="w", pady=8)
        ttk.Button(frame, text="Close", command=win.destroy).grid(row=2, column=2, sticky="e", pady=8)
        listing.bind("<<ListboxSelect>>", lambda _e: entry_var.set(listing.get(listing.curselection()[0])) if listing.curselection() else None)

    def finish_category_settings(self):
        self.save_categories()
        self.category_combo.configure(values=["All"] + self.categories)
        self.refresh_table()
        self.refresh_analytics()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            bg, fg, field = "#222831", "#eeeeee", "#393e46"
        else:
            bg, fg, field = "#f0f0f0", "#111111", "#ffffff"
        self.root.configure(bg=bg)
        self.style.configure(".", background=bg, foreground=fg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg)
        self.style.configure("TButton", background=field, foreground=fg)
        self.style.configure("TEntry", fieldbackground=field, foreground=fg)
        self.style.configure("TCombobox", fieldbackground=field, foreground=fg)
        self.style.configure("Treeview", background=field, fieldbackground=field, foreground=fg)
        self.style.map("Treeview", background=[("selected", "#4169e1")], foreground=[("selected", "#ffffff")])


def main():
    root = tk.Tk()
    ExpenseTracker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
