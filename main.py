import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog,
    QTableWidget, QTableWidgetItem, QCheckBox, QLineEdit,
    QRadioButton, QButtonGroup, QMessageBox, QHeaderView, QMenu, QComboBox,
    QDialog, QTextEdit
)
import csv
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from governance_controller import run_governance, detect_spec_type


class SummaryDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(750, 550)
        
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
        """)

        # Title Label
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-bottom: 5px;")
        layout.addWidget(title_label)
        
        # Text display
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        # Monospace font for diff-like output
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d1d1d1;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                padding: 12px;
                border: 1px solid #444444;
                border-radius: 4px;
            }
        """)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        layout.addWidget(self.text_edit)
        layout.addWidget(close_btn)


class UnifiedGovernanceApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ValidationUtility")
        self.setWindowIcon(QIcon("ValidationUtility.ico"))
        self.setMinimumSize(900, 600)

        self.selected_file = None
        self.violations_data = [] # Original raw violations
        self.grouped_violations = [] # Grouped for UI
        self.detected_type = None

        self.init_ui()

    # ==========================
    # UI Setup
    # ==========================

    def init_ui(self):
        main_layout = QVBoxLayout()

        # File Selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_file)

        file_layout.addWidget(self.file_label)
        file_layout.addWidget(browse_btn)

        # Detection Display
        self.detected_label = QLabel("Detected Spec: Not Detected")

        # Override Selection
        override_layout = QHBoxLayout()

        self.auto_radio = QRadioButton("Auto Detect")
        self.api_radio = QRadioButton("Force API")
        self.event_radio = QRadioButton("Force Event")

        self.auto_radio.setChecked(True)

        self.override_group = QButtonGroup()
        self.override_group.addButton(self.auto_radio)
        self.override_group.addButton(self.api_radio)
        self.override_group.addButton(self.event_radio)

        override_layout.addWidget(self.auto_radio)
        override_layout.addWidget(self.api_radio)
        override_layout.addWidget(self.event_radio)

        # Actions & Filters
        actions_layout = QHBoxLayout()
        validate_btn = QPushButton("1. Validate Spec")
        validate_btn.clicked.connect(self.run_validation)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Issues")
        self.filter_combo.currentIndexChanged.connect(self.filter_table)
        self.filter_combo.setEnabled(False)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search field name...")
        self.search_input.textChanged.connect(self.filter_table)
        self.search_input.setEnabled(False)

        actions_layout.addWidget(validate_btn)
        actions_layout.addWidget(QLabel("Filter:"))
        actions_layout.addWidget(self.filter_combo)
        actions_layout.addWidget(QLabel("Search:"))
        actions_layout.addWidget(self.search_input)
        actions_layout.addStretch()

        # Bulk Actions
        bulk_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.toggle_all(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self.toggle_all(False))
        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(self.export_csv)

        bulk_layout.addWidget(select_all_btn)
        bulk_layout.addWidget(deselect_all_btn)
        bulk_layout.addStretch()
        bulk_layout.addWidget(export_btn)

        # Table Output
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Ignore", "Field", "Issue", "Expected", "Found", "Edit"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.handle_double_click)
        self.setStyleSheet("""
            QTableWidget {
                font-size: 14px;
                gridline-color: #c0c0c0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                font-size: 14px;
                font-weight: bold;
                padding: 6px;
            }
            QLineEdit {
                font-size: 14px;
                padding: 4px;
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton:pressed {
                background-color: #004275;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #888888;
            }
        """)
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Apply Fix Button
        self.apply_btn = QPushButton("2. Apply Overrides & Fix")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.apply_fixes)

        # Layout assembly
        main_layout.addLayout(file_layout)
        main_layout.addWidget(self.detected_label)
        main_layout.addLayout(override_layout)
        main_layout.addLayout(actions_layout)
        main_layout.addLayout(bulk_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.apply_btn)

        self.setLayout(main_layout)

    # ==========================
    # File Browse
    # ==========================

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YAML File",
            "",
            "YAML Files (*.yaml *.yml)"
        )

        if file_path:
            self.selected_file = file_path
            self.file_label.setText(file_path)
            self.violations_data = []
            self.table.setRowCount(0)
            self.apply_btn.setEnabled(False)
            self.filter_combo.setEnabled(False)

            # Auto detect spec
            detected = detect_spec_type(file_path)
            if detected == "api":
                self.detected_label.setText("Detected Spec: OpenAPI")
            elif detected == "event":
                self.detected_label.setText("Detected Spec: AsyncAPI")
            else:
                self.detected_label.setText("Detected Spec: Unknown")

    def get_override_type(self):
        if self.api_radio.isChecked():
            return "api"
        elif self.event_radio.isChecked():
            return "event"
        return None

    # ==========================
    # Validation
    # ==========================

    def run_validation(self):
        if not self.selected_file:
            QMessageBox.warning(self, "Warning", "Please select a YAML file.")
            return

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            violations, detected_type = run_governance(
                self.selected_file,
                "validate",
                self.get_override_type()
            )

            self.detected_type = detected_type
            self.detected_label.setText(f"Detected Spec: {detected_type}")

            if isinstance(violations, dict) and "error" in violations:
                QMessageBox.warning(self, "Error", violations["error"])
                return
                
            if isinstance(violations, str):
                 QMessageBox.warning(self, "Error", violations)
                 return
                 
            self.violations_data = violations
            self.populate_table()

            if violations:
                self.apply_btn.setEnabled(True)
                self.update_filters()
                QApplication.restoreOverrideCursor()
                QMessageBox.information(self, "Validation", f"Found {len(violations)} violations.")
            else:
                self.apply_btn.setEnabled(False)
                QApplication.restoreOverrideCursor()
                QMessageBox.information(self, "Validation", "No violations found. File is fully compliant.")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", str(e))

    def update_filters(self):
        self.filter_combo.clear()
        self.filter_combo.addItem("All Issues")
        
        issues = set(v.get("issue", "") for v in self.violations_data)
        for issue in sorted(issues):
            if issue:
                self.filter_combo.addItem(issue)
                
        self.filter_combo.setEnabled(True)
        self.search_input.setEnabled(True)

    def update_edit_value(self, row_index, value):
        """Update the QLineEdit in the Edit column (column 5)."""
        edit_widget = self.table.cellWidget(row_index, 5)
        if edit_widget and isinstance(edit_widget, QLineEdit):
            edit_widget.setText(value)

    def populate_table(self):
        self.table.setRowCount(0)
        
        # Group violations by (field, issue, expected, found)
        groups = {}
        for v in self.violations_data:
            sig = (v.get("field"), v.get("issue"), v.get("expected"), v.get("found"))
            if sig not in groups:
                groups[sig] = {
                    "field": v.get("field"),
                    "issue": v.get("issue"),
                    "expected": v.get("expected"),
                    "found": v.get("found"),
                    "paths": []
                }
            groups[sig]["paths"].append(v.get("path"))

        self.grouped_violations = list(groups.values())

        for i, g in enumerate(self.grouped_violations):
            self.table.insertRow(i)

            # 0. Ignore Checkbox
            checkbox_widget = QWidget()
            checkbox = QCheckBox()
            chk_layout = QHBoxLayout(checkbox_widget)
            chk_layout.addWidget(checkbox)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0,0,0,0)
            self.table.setCellWidget(i, 0, checkbox_widget)

            # 1. Field
            field_name = g.get("field", "")
            field_item = QTableWidgetItem(field_name)
            field_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(i, 1, field_item)

            # 2. Issue
            issue_item = QTableWidgetItem(g.get("issue", ""))
            issue_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(i, 2, issue_item)

            # 3. Expected (Handle Multiple Suggestions)
            expected_text = str(g.get("expected", ""))
            if " || " in expected_text:
                options = [o.strip() for o in expected_text.split("||")]
                container = QWidget()
                vbox = QVBoxLayout(container)
                vbox.setContentsMargins(8, 4, 8, 4)
                vbox.setSpacing(4)
                
                group = QButtonGroup(container)
                for opt in options:
                    rb = QRadioButton(opt)
                    rb.setStyleSheet("color: #d1d1d1; font-size: 13px;")
                    vbox.addWidget(rb)
                    group.addButton(rb)
                    # Closure to capture current index and value
                    rb.toggled.connect(lambda checked, v=opt, r=i: self.update_edit_value(r, v) if checked else None)
                
                self.table.setCellWidget(i, 3, container)
            else:
                expected_item = QTableWidgetItem(expected_text)
                expected_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                expected_item.setToolTip(expected_text)
                self.table.setItem(i, 3, expected_item)

            # 4. Found
            found_text = str(g.get("found", ""))
            found_item = QTableWidgetItem(found_text)
            found_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            found_item.setToolTip(found_text)
            self.table.setItem(i, 4, found_item)

            # 5. Edit
            edit_input = QLineEdit()
            edit_input.setPlaceholderText("Enter custom fix...")
            self.table.setCellWidget(i, 5, edit_input)

        self.table.resizeRowsToContents()
        self.filter_table()

    def filter_table(self):
        selected_filter = self.filter_combo.currentText()
        search_text = self.search_input.text().lower()
        
        for i in range(self.table.rowCount()):
            # Column 1 = Field Name, Column 2 = Issue Type
            field_item = self.table.item(i, 1)
            issue_item = self.table.item(i, 2)
            
            field_name = field_item.text().lower() if field_item else ""
            issue_text = issue_item.text() if issue_item else ""
            
            issue_match = (selected_filter == "All Issues") or (issue_text == selected_filter)
            search_match = (not search_text) or (search_text in field_name)
            
            self.table.setRowHidden(i, not (issue_match and search_match))

    def toggle_all(self, state):
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                widget = self.table.cellWidget(i, 0)
                if widget:
                    checkbox = widget.layout().itemAt(0).widget()
                    checkbox.setChecked(state)

    def handle_double_click(self, row, column):
        if column == 3: # Expected column is 3
            expected_text = self.table.item(row, column).text()
            edit_widget = self.table.cellWidget(row, 5) # Edit column is 5
            if edit_widget:
                edit_widget.setText(expected_text)

    def export_csv(self):
        if not self.violations_data:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
            
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Path", "Issue", "Expected", "Found"])
                for v in self.violations_data:
                    writer.writerow([
                        v.get("field", ""),
                        v.get("path", ""),
                        v.get("issue", ""),
                        str(v.get("expected", "")),
                        str(v.get("found", ""))
                    ])
            QMessageBox.information(self, "Success", f"Successfully exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV: {str(e)}")

    def show_context_menu(self, position):
        item = self.table.itemAt(position)
        if not item:
            return

        row = item.row()
        violation = self.grouped_violations[row]

        menu = QMenu(self.table)
        copy_expected_action = menu.addAction("Copy Expected")
        copy_found_action = menu.addAction("Copy Found")
        copy_field_action = menu.addAction("Copy Field")

        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action:
            clipboard = QApplication.clipboard()
            if action == copy_expected_action:
                clipboard.setText(str(violation.get("expected", "")))
            elif action == copy_found_action:
                clipboard.setText(str(violation.get("found", "")))
            elif action == copy_field_action:
                clipboard.setText(violation.get("field", ""))

    # ==========================
    # Applying Fixes
    # ==========================

    def apply_fixes(self):
        user_actions = {}

        for i in range(self.table.rowCount()):
            gv = self.grouped_violations[i]
            issue = gv.get("issue")
            paths = gv.get("paths", [])

            # Extract Ignore
            checkbox_widget = self.table.cellWidget(i, 0)
            checkbox = checkbox_widget.layout().itemAt(0).widget()
            ignored = checkbox.isChecked()

            # Extract Edit
            edit_widget = self.table.cellWidget(i, 5) # Edit column is 5
            edited_val = edit_widget.text().strip()

            action = {}
            if ignored:
                action["ignore"] = True
            elif edited_val:
                action["edit"] = edited_val

            if action:
                # Apply action to ALL paths in this group
                for path_str in paths:
                    key = f"{path_str}|{issue}"
                    user_actions[key] = action

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            changes, detected_type = run_governance(
                self.selected_file,
                "fix",
                self.get_override_type(),
                user_actions
            )

            # Show changes dialog
            if changes:
                msg = "\n".join(changes)
                self.table.setRowCount(0)
                self.violations_data = []
                self.apply_btn.setEnabled(False)
                self.filter_combo.setEnabled(False)
                QApplication.restoreOverrideCursor()
                
                # Use custom scrollable dialog instead of QMessageBox
                dialog = SummaryDialog("Fix Summary", f"Fixes applied successfully:\n\n{msg}", self)
                dialog.exec()
            else:
                QApplication.restoreOverrideCursor()
                QMessageBox.information(self, "Info", "No changes were applied.")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UnifiedGovernanceApp()
    window.show()
    sys.exit(app.exec())