import sys
import sqlite3
from datetime import datetime
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QTableWidget, QTableWidgetItem, QTabWidget, QLabel,
                           QPushButton, QHeaderView, QLineEdit, QMessageBox,
                           QProgressBar, QFileDialog, QComboBox, QCheckBox,
                           QStatusBar)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont

class DifferenceDetailsTab(QWidget):
    def __init__(self, phone_number, db_path='call_history.db'):
        super().__init__()
        self.phone_number = phone_number
        self.db_path = db_path
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Create header and controls
        header_layout = QHBoxLayout()
        
        # Create header label
        header = QLabel(f"Call Differences for {self.phone_number}")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(header)
        
        # Add search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.filter_table)
        header_layout.addWidget(self.search_box)
        
        # Add export button
        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(self.export_to_csv)
        header_layout.addWidget(export_btn)
        
        layout.addLayout(header_layout)

        # Create filter controls
        filter_layout = QHBoxLayout()
        
        # Date range filter
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("Date From (YYYY-MM-DD)")
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("Date To (YYYY-MM-DD)")
        filter_layout.addWidget(QLabel("Date Range:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(self.date_to)
        
        # Call type filter
        self.call_type_filter = QComboBox()
        self.call_type_filter.addItems(['All', 'Incoming', 'Outgoing', 'Missed'])
        filter_layout.addWidget(QLabel("Call Type:"))
        filter_layout.addWidget(self.call_type_filter)
        
        # Service filter
        self.service_filter = QComboBox()
        self.service_filter.addItems(['All', 'Phone', 'FaceTime', 'FaceTime Video'])
        filter_layout.addWidget(QLabel("Service:"))
        filter_layout.addWidget(self.service_filter)
        
        # Apply filters button
        apply_filters_btn = QPushButton("Apply Filters")
        apply_filters_btn.clicked.connect(self.apply_filters)
        filter_layout.addWidget(apply_filters_btn)
        
        layout.addLayout(filter_layout)

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Date", 
            "Call History Timestamp", 
            "iTunes Timestamp",
            "Call Type",
            "Service"
        ])
        
        self.load_table_data()
        
        # Set table properties
        header = self.table.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        
        # Add status bar
        self.status_bar = QStatusBar()
        self.update_status_bar()
        
        layout.addWidget(self.table)
        layout.addWidget(self.status_bar)
        self.setLayout(layout)

    def load_table_data(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get call history records
            cursor.execute('''
                SELECT date(timestamp), timestamp, call_type, service
                FROM call_history 
                WHERE phone_number = ? AND source = 'call_history'
                ORDER BY timestamp
            ''', (self.phone_number,))
            ch_calls = {row[1]: row for row in cursor.fetchall()}
            
            # Get iTunes records
            cursor.execute('''
                SELECT date(timestamp), timestamp, call_type, service
                FROM call_history 
                WHERE phone_number = ? AND source = 'itunes'
                ORDER BY timestamp
            ''', (self.phone_number,))
            it_calls = {row[1]: row for row in cursor.fetchall()}
            
            # Find differences
            ch_only = set(ch_calls.keys()) - set(it_calls.keys())
            it_only = set(it_calls.keys()) - set(ch_calls.keys())
            
            # Prepare data for display
            self.rows = []
            
            # Add calls only in Call History
            for timestamp in sorted(ch_only):
                call = ch_calls[timestamp]
                self.rows.append({
                    'date': call[0],
                    'ch_time': timestamp,
                    'it_time': '',
                    'call_type': call[2],
                    'service': call[3]
                })
            
            # Add calls only in iTunes
            for timestamp in sorted(it_only):
                call = it_calls[timestamp]
                self.rows.append({
                    'date': call[0],
                    'ch_time': '',
                    'it_time': timestamp,
                    'call_type': call[2],
                    'service': call[3]
                })
            
            self.populate_table(self.rows)
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")

    def populate_table(self, rows):
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row['date']))
            
            # Color-code the timestamps
            ch_time_item = QTableWidgetItem(row['ch_time'])
            it_time_item = QTableWidgetItem(row['it_time'])
            
            if not row['it_time']:  # Only in Call History
                ch_time_item.setBackground(QColor(255, 200, 200))
            if not row['ch_time']:  # Only in iTunes
                it_time_item.setBackground(QColor(200, 255, 200))
                
            self.table.setItem(i, 1, ch_time_item)
            self.table.setItem(i, 2, it_time_item)
            self.table.setItem(i, 3, QTableWidgetItem(row['call_type']))
            self.table.setItem(i, 4, QTableWidgetItem(row['service']))

    def filter_table(self):
        search_text = self.search_box.text().lower()
        for row in range(self.table.rowCount()):
            show_row = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            self.table.setRowHidden(row, not show_row)
        self.update_status_bar()

    def apply_filters(self):
        try:
            filtered_rows = self.rows.copy()
            
            # Apply date range filter
            if self.date_from.text():
                date_from = datetime.strptime(self.date_from.text(), '%Y-%m-%d')
                filtered_rows = [row for row in filtered_rows if datetime.strptime(row['date'], '%Y-%m-%d') >= date_from]
            
            if self.date_to.text():
                date_to = datetime.strptime(self.date_to.text(), '%Y-%m-%d')
                filtered_rows = [row for row in filtered_rows if datetime.strptime(row['date'], '%Y-%m-%d') <= date_to]
            
            # Apply call type filter
            if self.call_type_filter.currentText() != 'All':
                filtered_rows = [row for row in filtered_rows if row['call_type'] == self.call_type_filter.currentText()]
            
            # Apply service filter
            if self.service_filter.currentText() != 'All':
                filtered_rows = [row for row in filtered_rows if row['service'] == self.service_filter.currentText()]
            
            self.populate_table(filtered_rows)
            self.update_status_bar()
            
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Date", "Please enter dates in YYYY-MM-DD format")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error applying filters: {str(e)}")

    def export_to_csv(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export to CSV", "", "CSV Files (*.csv)")
            if filename:
                with open(filename, 'w', newline='') as file:
                    writer = csv.writer(file)
                    # Write headers
                    headers = []
                    for i in range(self.table.columnCount()):
                        headers.append(self.table.horizontalHeaderItem(i).text())
                    writer.writerow(headers)
                    
                    # Write visible rows
                    for row in range(self.table.rowCount()):
                        if not self.table.isRowHidden(row):
                            row_data = []
                            for col in range(self.table.columnCount()):
                                item = self.table.item(row, col)
                                row_data.append(item.text() if item else "")
                            writer.writerow(row_data)
                            
                QMessageBox.information(self, "Success", "Data exported successfully!")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error exporting data: {str(e)}")

    def update_status_bar(self):
        visible_rows = sum(1 for row in range(self.table.rowCount()) 
                         if not self.table.isRowHidden(row))
        total_rows = self.table.rowCount()
        self.status_bar.showMessage(f"Showing {visible_rows} of {total_rows} differences")

class MainWindow(QMainWindow):
    def __init__(self, db_path='call_history.db'):
        super().__init__()
        self.db_path = db_path
        self.setWindowTitle("Call History Comparison")
        self.setGeometry(100, 100, 1200, 800)
        
        try:
            self.init_ui()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error initializing application: {str(e)}")
            sys.exit(1)

    def init_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add controls at the top
        controls_layout = QHBoxLayout()
        
        # Add search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search phone numbers...")
        self.search_box.textChanged.connect(self.filter_main_table)
        controls_layout.addWidget(self.search_box)
        
        # Add refresh button
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.clicked.connect(self.refresh_data)
        controls_layout.addWidget(refresh_btn)
        
        # Add export button
        export_btn = QPushButton("Export Summary")
        export_btn.clicked.connect(self.export_summary)
        controls_layout.addWidget(export_btn)
        
        layout.addLayout(controls_layout)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        # Create main summary table
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(
            ["Phone Number", "Call History Total", "iTunes Total", "Difference"]
        )

        # Store the current sort order
        self.current_sort_column = 0
        self.current_sort_order = Qt.AscendingOrder

        self.populate_summary_table()

        # Set table properties
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self.sort_table)

        # Add status bar
        self.status_bar = QStatusBar()
        self.setCentralWidget(central_widget)
        self.setStatusBar(self.status_bar)
        self.update_status_bar()

        # Add widgets to layout
        layout.addWidget(self.summary_table)
        layout.addWidget(self.tab_widget)

    def get_item_value(self, row, column):
        """Helper function to get sortable value from table item"""
        if column == 0:  # Phone Number column (with contact name)
            item = self.summary_table.item(row, column)
            if item:
                text = item.text()
                # Extract phone number from "Contact Name (phone)" format
                if '(' in text and ')' in text:
                    return text.split('(')[1].rstrip(')')
                return text
            return ""
        elif column in [1, 2]:  # Call History Total and iTunes Total columns
            item = self.summary_table.item(row, column)
            return int(item.text()) if item else 0
        else:  # Difference column
            widget = self.summary_table.cellWidget(row, column)
            if widget and isinstance(widget, QPushButton):
                return int(widget.text())
            item = self.summary_table.item(row, column)
            return int(item.text()) if item else 0

    def sort_table(self, column):
        """Sort the table by the specified column"""
        if self.current_sort_column == column:
            # Toggle sort order if clicking the same column
            self.current_sort_order = Qt.DescendingOrder if self.current_sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            # Default to ascending order for new column
            self.current_sort_order = Qt.AscendingOrder
            self.current_sort_column = column

        # Store the complete row data including widgets and formatting
        rows_data = []
        for row in range(self.summary_table.rowCount()):
            row_items = []
            for col in range(self.summary_table.columnCount()):
                item = self.summary_table.item(row, col)
                widget = self.summary_table.cellWidget(row, col)
                background = item.background() if item else None
                alignment = item.textAlignment() if item else None
                
                row_items.append({
                    'item': item,
                    'widget': widget,
                    'background': background,
                    'alignment': alignment,
                    'sort_value': self.get_item_value(row, col)
                })
            rows_data.append((row_items, row))

        # Sort based on the selected column
        rows_data.sort(
            key=lambda x: x[0][column]['sort_value'],
            reverse=(self.current_sort_order == Qt.DescendingOrder)
        )

        # Rearrange the table contents
        for new_index, (row_items, _) in enumerate(rows_data):
            for col, cell_data in enumerate(row_items):
                # Clear existing content
                self.summary_table.takeItem(new_index, col)
                if self.summary_table.cellWidget(new_index, col):
                    self.summary_table.removeCellWidget(new_index, col)

                # Restore widget if exists
                if cell_data['widget']:
                    self.summary_table.setCellWidget(new_index, col, cell_data['widget'])
                # Restore item if exists
                elif cell_data['item']:
                    new_item = QTableWidgetItem(cell_data['item'])
                    if cell_data['background']:
                        new_item.setBackground(cell_data['background'])
                    if cell_data['alignment']:
                        new_item.setTextAlignment(cell_data['alignment'])
                    self.summary_table.setItem(new_index, col, new_item)

        # Update sort indicator
        self.summary_table.horizontalHeader().setSortIndicator(column, self.current_sort_order)

    def populate_summary_table(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get summary data from view
            cursor.execute('SELECT * FROM call_summary ORDER BY phone_number')
            rows = cursor.fetchall()
            
            self.summary_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                # Phone number with contact name
                display_text = f"{row[0]}"
                if row[1]:  # If contact name exists
                    display_text = f"{row[1]} ({row[0]})"
                number_item = QTableWidgetItem(display_text)
                self.summary_table.setItem(i, 0, number_item)
                
                # Call history total
                ch_total = QTableWidgetItem(str(row[2] or 0))
                ch_total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.summary_table.setItem(i, 1, ch_total)
                
                # iTunes total
                it_total = QTableWidgetItem(str(row[3] or 0))
                it_total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.summary_table.setItem(i, 2, it_total)
                
                # Difference (clickable)
                if row[4] > 0:
                    diff_btn = QPushButton(str(row[4]))
                    diff_btn.clicked.connect(lambda checked, num=row[0]: self.show_difference_details(num))
                    self.summary_table.setCellWidget(i, 3, diff_btn)
                    # Highlight rows with differences
                    for col in range(4):
                        item = self.summary_table.item(i, col)
                        if item:
                            item.setBackground(QColor(255, 255, 200))
                else:
                    diff_item = QTableWidgetItem('0')
                    diff_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.summary_table.setItem(i, 3, diff_item)
            
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error populating summary table: {str(e)}")

    def filter_main_table(self):
        search_text = self.search_box.text().lower()
        for row in range(self.summary_table.rowCount()):
            show_row = False
            for col in range(self.summary_table.columnCount()):
                item = self.summary_table.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            self.summary_table.setRowHidden(row, not show_row)
        self.update_status_bar()

    def show_difference_details(self, phone_number):
        # Check if tab already exists
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == phone_number:
                self.tab_widget.setCurrentIndex(i)
                return

        # Create new tab
        try:
            diff_tab = DifferenceDetailsTab(phone_number, self.db_path)
            self.tab_widget.addTab(diff_tab, phone_number)
            self.tab_widget.setCurrentWidget(diff_tab)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error creating details tab: {str(e)}")

    def close_tab(self, index):
        self.tab_widget.removeTab(index)

    def refresh_data(self):
        try:
            self.populate_summary_table()
            QMessageBox.information(self, "Success", "Data refreshed successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error refreshing data: {str(e)}")

    def export_summary(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Summary to CSV", "", "CSV Files (*.csv)")
            if filename:
                with open(filename, 'w', newline='') as file:
                    writer = csv.writer(file)
                    # Write headers
                    headers = []
                    for i in range(self.summary_table.columnCount()):
                        headers.append(self.summary_table.horizontalHeaderItem(i).text())
                    writer.writerow(headers)
                    
                    # Write visible rows
                    for row in range(self.summary_table.rowCount()):
                        if not self.summary_table.isRowHidden(row):
                            row_data = []
                            for col in range(self.summary_table.columnCount()):
                                item = self.summary_table.item(row, col)
                                if item:
                                    row_data.append(item.text())
                                else:
                                    widget = self.summary_table.cellWidget(row, col)
                                    if isinstance(widget, QPushButton):
                                        row_data.append(widget.text())
                                    else:
                                        row_data.append("")
                            writer.writerow(row_data)
                            
                QMessageBox.information(self, "Success", "Summary exported successfully!")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error exporting summary: {str(e)}")

    def update_status_bar(self):
        visible_rows = sum(1 for row in range(self.summary_table.rowCount()) 
                         if not self.summary_table.isRowHidden(row))
        total_rows = self.summary_table.rowCount()
        total_differences = sum(1 for row in range(self.summary_table.rowCount())
                              if self.summary_table.cellWidget(row, 3) is not None)
        self.status_bar.showMessage(
            f"Showing {visible_rows} of {total_rows} numbers | {total_differences} numbers with differences")

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1) 