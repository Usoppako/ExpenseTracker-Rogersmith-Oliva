PERSONAL EXPENSE TRACKER & VISUALIZER
Prepared for: Rogersmith Oliva

FEATURES
- Add, edit, and delete expenses with date/category/amount validation.
- Save records locally in expenses.csv.
- Scrollable, sortable transaction table and date/category/amount filters.
- Today, this week, and this month totals; period total, average, and largest expense.
- Analytics tab with monthly/period spending line chart and category breakdown chart.
- CSV export and CSV import/merge, skipping duplicate date + amount + category records.
- Add, rename, and delete custom categories in Settings.
- Optional light/dark theme toggle.
- Operation logging decorator and recursive_sum() example.

RUN FROM SOURCE (requires Python)
1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run: python -m pip install -r requirements.txt
4. Run: python expense_tracker.py

BUILD A WINDOWS APP (the build computer needs Python and internet for installation)
1. On Windows, install Python 3.10 or newer and select "Add Python to PATH".
2. Double-click build_exe.bat.
3. The packaged app will be created at dist\expense_tracker.exe.
4. Copy dist\expense_tracker.exe to a folder you can write to. The target computer does not need Python.
   Keep expenses.csv and categories.json beside the EXE (the app creates them as needed).

DATA / PRIVACY
The app stores data locally in expenses.csv and categories.json beside the source script or EXE.
It does not require an account or send expense data to a server. Back up these files yourself.

KNOWN LIMITATIONS
- Charts summarize the selected analytics period; there is no cloud sync.
- The app stores currency amounts as Philippine pesos (₱).
- Windows EXE packaging must be built on Windows; PyInstaller does not cross-compile Windows EXEs from Linux/macOS.
