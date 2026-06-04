import sys
import os
import tempfile
import subprocess
import time
import ctypes
from ctypes import wintypes
from typing import List
import threading

# Try to import PyQt5 (if not installed, inform the user)
try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QCursor
    from PyQt5.QtWidgets import QMessageBox, QInputDialog
except Exception as e:
    print("PyQt5 no está instalado. Instálalo con: pip install PyQt5")
    raise


# ---------------------- Helper native functions (unchanged logic) ----------------------

def get_printers() -> List[str]:
    try:
        result = subprocess.run(
            ['wmic', 'printer', 'get', 'name'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return [p.strip() for p in result.stdout.split('\n') if p.strip() and p.strip().lower() != 'name']
    except Exception:
        return []


def delete_printer_windows(printer_name: str) -> bool:
    try:
        result = subprocess.run([
            'rundll32.exe',
            'printui.dll,PrintUIEntry',
            '/dl',
            '/n',
            printer_name
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

        if result.returncode != 0:
            powershell_command = f'(New-Object -ComObject WScript.Network).RemovePrinterConnection("{printer_name}")'
            subprocess.run(['powershell', '-Command', powershell_command], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

        time.sleep(1)
        printers = get_printers()
        return printer_name not in printers

    except Exception as e:
        print(f"Error al borrar impresora: {e}")
        return False


def _create_process_with_logon(username: str, password: str, command: str, workdir: str = None) -> int:
    """
    Run a command as another local user using CreateProcessWithLogonW.
    Returns the process exit code or raises an exception on failure.
    """
    LOGON_WITH_PROFILE = 0x00000001
    CREATE_NO_WINDOW = 0x08000000

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    CreateProcessWithLogonW = ctypes.windll.advapi32.CreateProcessWithLogonW
    CreateProcessWithLogonW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPWSTR,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)
    ]
    CreateProcessWithLogonW.restype = wintypes.BOOL

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()

    cmd = command
    success = CreateProcessWithLogonW(
        username, None, password,
        LOGON_WITH_PROFILE,
        None,
        cmd,
        CREATE_NO_WINDOW,
        None,
        workdir or None,
        ctypes.byref(si), ctypes.byref(pi)
    )

    if not success:
        err = ctypes.GetLastError()
        raise OSError(f"CreateProcessWithLogonW failed, GetLastError={err}")

    ctypes.windll.kernel32.WaitForSingleObject(pi.hProcess, -1)
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(pi.hThread)
    ctypes.windll.kernel32.CloseHandle(pi.hProcess)

    return int(exit_code.value)


def _run_admin_printer_cleanup(printer_name: str, username: str, password: str) -> bool:
    """
    Create a temporary PowerShell script that removes the printer registry key and
    runs the spooler stop/start and winsock reset. Execute it as the provided local user.
    Returns True on success (exit code 0), False otherwise.
    """
    ps_content = f'''param([string]$printer)
# Intento de eliminación desde la sesión de usuario (RemovePrinterConnection y printui)
try {{
    try {{ (New-Object -ComObject WScript.Network).RemovePrinterConnection($printer) }} catch {{}}
    try {{ & rundll32.exe printui.dll,PrintUIEntry /dl /n "$printer" }} catch {{}}
}} catch {{}}

# Eliminar la clave de impresora en HKLM por si quedan entradas globales
try {{
    Remove-Item -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Print\\Printers\\$printer" -Recurse -Force -ErrorAction SilentlyContinue
}} catch {{}}

Start-Sleep -Seconds 1
# Reiniciar el servicio Spooler
Try {{ Stop-Service -Name Spooler -Force -ErrorAction SilentlyContinue }} catch {{}}
Start-Sleep -Seconds 1
Try {{ Start-Service -Name Spooler -ErrorAction SilentlyContinue }} catch {{}}
Start-Sleep -Seconds 1
# Reset de winsock
try {{ netsh winsock reset }} catch {{}}

exit 0
'''

    fd, path = tempfile.mkstemp(suffix=".ps1", text=True)
    os.close(fd)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(ps_content)

        command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{path}" "{printer_name}"'
        exit_code = _create_process_with_logon(username, password, command)
        return exit_code == 0
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


# ---------------------- PyQt5 UI ----------------------

class AdminWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(bool, str)  # success, message

    def __init__(self, printer, username, password):
        super().__init__()
        self.printer = printer
        self.username = username
        self.password = password

    def run(self):
        try:
            ok = _run_admin_printer_cleanup(self.printer, self.username, self.password)
            self.finished.emit(ok, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class ConfirmDialog(QtWidgets.QDialog):
    """Custom confirmation dialog with animated buttons and colored Yes/No."""
    def __init__(self, parent, title: str, message: str, yes_text: str = "Sí", no_text: str = "No"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background: transparent; }")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {parent.text}; font-size: 13px;")
        layout.addWidget(label)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self.btn_no = QtWidgets.QPushButton(no_text)
        self.btn_no.setFixedHeight(42)
        self.btn_no.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_no.setStyleSheet(f"QPushButton{{background:#e74c3c;color:#fff;border-radius:8px;padding:8px 18px;font-weight:600}} QPushButton:hover{{background:#c0392b}}")

        self.btn_yes = QtWidgets.QPushButton(yes_text)
        self.btn_yes.setFixedHeight(42)
        self.btn_yes.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_yes.setStyleSheet(f"QPushButton{{background:#27ae60;color:#fff;border-radius:8px;padding:8px 18px;font-weight:700}} QPushButton:hover{{background:#219150}}")

        btn_layout.addWidget(self.btn_no)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(self.btn_yes)

        layout.addLayout(btn_layout)

        # Opacity effects for animation
        self._anim_yes = QtCore.QPropertyAnimation(QtWidgets.QGraphicsOpacityEffect(self.btn_yes), b"opacity")
        self._anim_no = QtCore.QPropertyAnimation(QtWidgets.QGraphicsOpacityEffect(self.btn_no), b"opacity")

        # Apply effects
        eff_yes = QtWidgets.QGraphicsOpacityEffect(self.btn_yes)
        eff_no = QtWidgets.QGraphicsOpacityEffect(self.btn_no)
        self.btn_yes.setGraphicsEffect(eff_yes)
        self.btn_no.setGraphicsEffect(eff_no)

        self._anim_yes.setTargetObject(eff_yes)
        self._anim_no.setTargetObject(eff_no)
        self._anim_yes.setPropertyName(b"opacity")
        self._anim_no.setPropertyName(b"opacity")
        self._anim_yes.setDuration(260)
        self._anim_no.setDuration(260)
        self._anim_yes.setStartValue(0.0)
        self._anim_yes.setEndValue(1.0)
        self._anim_no.setStartValue(0.0)
        self._anim_no.setEndValue(1.0)

        self.btn_yes.clicked.connect(self.accept)
        self.btn_no.clicked.connect(self.reject)

    def showEvent(self, ev):
        # start animations when dialog shows
        try:
            self._anim_yes.start()
            self._anim_no.start()
        except Exception:
            pass
        super().showEvent(ev)


class PrinterAdminWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Administrador de Impresoras")
        self.resize(900, 650)

        # Cargar icono de la misma carpeta si existe
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'Impresora.ico')
            if os.path.exists(icon_path):
                self.setWindowIcon(QtGui.QIcon(icon_path))
        except Exception:
            # no bloquear la app si algo falla con el icono
            pass

        # Softer dark palette: dark slate background + softer green accents
        self.primary = "#6fcf97"  # light green for main action (accesible)
        self.accent = "#56b3b4"   # teal accent
        self.bg = "#1a222b"       # dark blue-gray background
        self.card = "#232c36"     # card surface, un poco más claro
        self.muted = "#3a4651"    # muted slate for secondary actions
        self.text = "#f2f2f2"     # off-white for high-contrast readable text
        self.text_muted = "#b0bfc9" # muted text for deshabilitado

        # Apply background
        self.setStyleSheet(f"background-color: {self.bg}; color: {self.text};")

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Administrador de Impresoras")
        title.setFont(QtGui.QFont("Segoe UI", 20, QtGui.QFont.DemiBold))
        title.setStyleSheet(f"color: {self.text};")
        header.addWidget(title)
        header.addStretch()

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Buscar impresora...")
        self.search.setFixedWidth(360)
        self.search.setClearButtonEnabled(True)
        self.search.setFont(QtGui.QFont("Segoe UI", 14))
        self.search.setStyleSheet(
            f"QLineEdit{{background:{self.card}; color:{self.text}; border:1px solid #20262a; padding:10px; border-radius:10px;}}"
        )
        self.search.textChanged.connect(self._filter_list)
        header.addWidget(self.search)

        root_layout.addLayout(header)

        main = QtWidgets.QHBoxLayout()
        main.setSpacing(14)

        left_card = QtWidgets.QFrame()
        left_card.setStyleSheet(f"background:{self.card}; border-radius:10px;")
        left_card_layout = QtWidgets.QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(12, 12, 12, 12)
        left_card_layout.setSpacing(8)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setFont(QtGui.QFont("Segoe UI", 15))
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.list_widget.setAlternatingRowColors(False)
        # Mejorar accesibilidad y contraste
        self.list_widget.setStyleSheet(f'''
            QListWidget {{
                background: {self.card};
                border: none;
                color: {self.text};
                font-size: 15px;
            }}
            QListWidget::item {{
                background: transparent;
                color: {self.text};
                padding: 14px 10px;
                border-radius: 8px;
            }}
            QListWidget::item:selected {{
                background: {self.primary};
                color: #1a222b;
                border: 2px solid {self.accent};
            }}
            QListWidget::item:hover {{
                background: {self.accent};
                color: #1a222b;
            }}
            QListWidget::item:disabled {{
                color: {self.text_muted};
            }}
        ''')
        left_card_layout.addWidget(self.list_widget)
        main.addWidget(left_card, 1)

        right_card = QtWidgets.QFrame()
        right_card.setStyleSheet(f"background:{self.card}; border-radius:10px;")
        right_layout = QtWidgets.QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        # Botón verde accesible con hover
        self.btn_add = QtWidgets.QPushButton("Agregar Impresora")
        self.btn_add.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_add.setFixedHeight(52)
        self.btn_add.setFont(QtGui.QFont("Segoe UI", 14))
        self.btn_add.setStyleSheet(f'''
            QPushButton {{
                background: #27ae60;
                color: #fff;
                border-radius: 10px;
                padding: 14px 20px;
                font-weight: 700;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #219150;
                color: #eafbe7;
            }}
        ''')

        # Botón rojo accesible con hover
        self.btn_delete = QtWidgets.QPushButton("Borrar Impresora")
        self.btn_delete.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_delete.setFixedHeight(52)
        self.btn_delete.setFont(QtGui.QFont("Segoe UI", 14))
        self.btn_delete.setStyleSheet(f'''
            QPushButton {{
                background: #e74c3c;
                color: #fff;
                border-radius: 10px;
                padding: 14px 20px;
                font-weight: 700;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #c0392b;
                color: #ffeaea;
            }}
        ''')

        # Botón degradado rojo-negro con hover
        self.btn_total = QtWidgets.QPushButton("Borrado Total (Admin)")
        self.btn_total.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_total.setFixedHeight(56)
        self.btn_total.setFont(QtGui.QFont("Segoe UI", 15, QtGui.QFont.DemiBold))
        self.btn_total.setStyleSheet(f'''
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e74c3c, stop:1 #232c36);
                color: #fff;
                border-radius: 10px;
                padding: 14px 20px;
                font-weight: 700;
                font-size: 15px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c0392b, stop:1 #11151a);
                color: #ffeaea;
            }}
        ''')

        self.info_label = QtWidgets.QLabel("Selecciona una impresora y usa las opciones.")
        self.info_label.setFont(QtGui.QFont("Segoe UI", 13))
        self.info_label.setStyleSheet(f"color: {self.text};")

        right_layout.addWidget(self.btn_add)
        right_layout.addWidget(self.btn_delete)
        right_layout.addStretch()
        right_layout.addWidget(self.info_label)
        right_layout.addWidget(self.btn_total)

        main.addWidget(right_card, 0)

        root_layout.addLayout(main)

        self.status = QtWidgets.QLabel("")
        self.status.setFont(QtGui.QFont("Segoe UI", 13))
        self.status.setStyleSheet(f"color: {self.text}; font-size:14px;")
        root_layout.addWidget(self.status)

        self.btn_add.clicked.connect(self.add_printer)
        self.btn_delete.clicked.connect(self.delete_printer_handler)
        self.btn_total.clicked.connect(self.borrado_total_admin_handler)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.update_printer_list)
        self.timer.start()

        self._all_printers = []
        self.update_printer_list()

        # tiny developer credit at bottom-right
        self.dev_label = QtWidgets.QLabel("developed by Ali")
        self.dev_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.dev_label.setStyleSheet(f"color: {self.text_muted}; font-size: 9px; padding-top:6px;")
        root_layout.addWidget(self.dev_label)

    def _filter_list(self, text: str):
        text = text.strip().lower()
        self.list_widget.clear()
        for p in self._all_printers:
            if not text or text in p.lower():
                self.list_widget.addItem(p)

    def update_printer_list(self):
        try:
            printers = get_printers()
            self._all_printers = printers
            current = self.list_widget.currentItem().text() if self.list_widget.currentItem() else None
            self._filter_list(self.search.text())
            # try to restore selection
            if current:
                items = self.list_widget.findItems(current, Qt.MatchExactly)
                if items:
                    self.list_widget.setCurrentItem(items[0])
        except Exception as e:
            self.status.setText(f"Error al listar impresoras: {e}")

    def add_printer(self):
        url = "http://impresion.08i.inss.ss/ipp/"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        self.status.setText("Abriendo navegador para agregar impresora...")
        QtCore.QTimer.singleShot(2500, lambda: (self.status.setText(""), self.update_printer_list()))

    def delete_printer_handler(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Aviso", "Por favor seleccione una impresora")
            return
        printer_name = item.text()
        reply = QMessageBox.question(self, "Confirmar Borrado", f"¿Deseas borrar la impresora '{printer_name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        try:
            ok = delete_printer_windows(printer_name)
            if ok:
                QMessageBox.information(self, "Éxito", f"Impresora '{printer_name}' borrada correctamente.")
            else:
                subprocess.run(['net', 'stop', 'spooler'], creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(1)
                subprocess.run(['net', 'start', 'spooler'], creationflags=subprocess.CREATE_NO_WINDOW)
                QMessageBox.information(self, "Éxito", "La impresora se eliminará al reiniciar el spooler")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo borrar la impresora: {e}")
        finally:
            QtCore.QTimer.singleShot(500, self.update_printer_list)

    def borrado_total_admin_handler(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Aviso", "Por favor seleccione una impresora")
            return
        printer_name = item.text()
        dlg = ConfirmDialog(self, "Confirmar Borrado Total", f"Esto borrará la impresora '{printer_name}' desde el registro y reiniciará servicios. ¿Continuar?", yes_text="Sí", no_text="No")
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        # Usar usuario fijo 'Administrador' y solicitar solo la contraseña
        username = "Administrador"
        password, ok2 = QInputDialog.getText(self, "Credenciales Admin", "Contraseña del usuario 'Administrador':", QtWidgets.QLineEdit.Password)
        if not ok2 or not password:
            QMessageBox.information(self, "Cancelado", "Operación cancelada: contraseña no proporcionada")
            return

        # Run admin work in background thread via QThread
        self.setCursor(QCursor(Qt.WaitCursor))
        self.btn_total.setEnabled(False)
        self.status.setText("Ejecutando operaciones administrativas...")

        self._worker = AdminWorker(printer_name, username, password)
        self._thread = QtCore.QThread()
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._on_admin_finished)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _on_admin_finished(self, ok: bool, msg: str):
        # restore UI
        self.unsetCursor()
        self.btn_total.setEnabled(True)
        self.status.setText("")
        try:
            self._thread.quit()
            self._thread.wait(1000)
        except Exception:
            pass

        if not ok:
            QMessageBox.warning(self, "Advertencia", f"Las operaciones finalizaron con errores. {msg}")

        # preguntar reinicio
        dlg2 = ConfirmDialog(self, "Reiniciar equipo", "¿Deseas reiniciar ahora el equipo?", yes_text="Sí", no_text="No")
        if dlg2.exec_() == QtWidgets.QDialog.Accepted:
            try:
                _create_process_with_logon(self._worker.username, self._worker.password, 'shutdown /r /t 0')
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo iniciar el reinicio: {e}")

        QtCore.QTimer.singleShot(500, self.update_printer_list)


def main():
    app = QtWidgets.QApplication(sys.argv)
    # Establecer icono de la aplicación si existe
    try:
        icon_path = os.path.join(os.path.dirname(__file__), 'Impresora.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QtGui.QIcon(icon_path))
    except Exception:
        pass
    win = PrinterAdminWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()