import sys
import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import json
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QLabel, QProgressBar,
    QPlainTextEdit, QSlider, QStyleFactory, QCompleter
)
from PyQt6.QtCore import (
    Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QTimer
)
from PyQt6.QtGui import QFont, QIcon, QStandardItemModel, QStandardItem

# HARDCODED API CREDENTIALS - UPDATE THESE WITH YOUR ACTUAL VALUES
API_USER_ID = ""  # Replace with your actual user ID
API_KEY = ""      # Replace with your actual API key

DARK_STYLESHEET = """
QWidget {
    background-color: #2e2e2e;
    color: #e0e0e0;
    font-family: 'SF Pro';
    font-size: 14px;
}
QMainWindow {
    background-color: #2e2e2e;
}
QLabel {
    font-size: 16px;
    font-weight: bold;
}
QLineEdit, QPlainTextEdit {
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 5px;
    padding: 6px;
    color: #e0e0e0;
}
QCompleter QAbstractItemView {
    background-color: #3c3c3c;
    border: 1px solid #555;
    color: #e0e0e0;
}
QCompleter QAbstractItemView::item:selected {
    background-color: #007aff;
}
QPushButton {
    background-color: #007aff;
    color: white;
    font-weight: bold;
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #005ecb;
}
QPushButton:pressed {
    background-color: #004a9e;
}
QPushButton:disabled {
    background-color: #555;
    color: #999;
}
QProgressBar {
    border: 1px solid #555;
    border-radius: 5px;
    text-align: center;
    color: #e0e0e0;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #007aff;
    border-radius: 4px;
}
QSlider::groove:horizontal {
    border: 1px solid #555;
    height: 3px;
    background: #3c3c3c;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #007aff;
    border: 1px solid #007aff;
    width: 18px;
    margin: -8px 0;
    border-radius: 9px;
}
"""

class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    log = pyqtSignal(str)

class AutocompleteFetcher(QRunnable):
    """ Worker thread for fetching autocomplete suggestions. """
    def __init__(self, query):
        super().__init__()
        self.signals = WorkerSignals()
        self.query = query
        self.base_url = "your-workers-link" + "/autocomplete"
    def run(self):
        try:
            params = {'q': self.query}
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            # Pass the full data (list of dicts) to the main thread
            self.signals.finished.emit(data)
        except requests.exceptions.RequestException as e:
            self.signals.error.emit(f"Autocomplete network error: {e}")
        except json.JSONDecodeError:
            self.signals.error.emit("Autocomplete failed to parse response.")
        except Exception as e:
            self.signals.error.emit(f"Autocomplete unexpected error: {e}")


class ApiFetcher(QRunnable):
    def __init__(self, tags):
        super().__init__()
        self.signals = WorkerSignals()
        self.tags = tags
        self.base_url = "your-workers-link" + "/api"

    def run(self):
        try:
            self.signals.log.emit("Fetching post count via proxy...")
            # Encode tags as plus-separated for the API
            tags_param = ('+'.join([t for t in self.tags.split() if t]))
            params = {
                'page': 'dapi', 's': 'post', 'q': 'index', 'limit': 0,
                'tags': tags_param, 'user_id': API_USER_ID, 'api_key': API_KEY
            }
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()

            if response.text.strip().lower().startswith('error'):
                self.signals.error.emit(f"API Error: {response.text}")
                return
            root = ET.fromstring(response.content)

            if root.tag == 'response' and root.get('success') == 'false':
                error_msg = root.get('message', 'Unknown API error')
                self.signals.error.emit(f"API Error: {error_msg}")
                return

            total_count = int(root.get('count', 0))
            if total_count == 0:
                self.signals.log.emit("No posts found with the given tags.")
                self.signals.finished.emit([])
                return

            self.signals.log.emit(f"Found {total_count} posts. Fetching URLs...")
            all_urls = []
            page = 0
            limit = 1000

            while len(all_urls) < total_count:
                import time
                if page > 0: time.sleep(1.1)

                params = {
                    'page': 'dapi', 's': 'post', 'q': 'index', 'limit': limit,
                    'pid': page, 'tags': tags_param, 'user_id': API_USER_ID, 'api_key': API_KEY
                }
                self.signals.log.emit(f"Fetching page {page + 1}...")
                page_response = requests.get(self.base_url, params=params, timeout=15)
                page_response.raise_for_status()

                if page_response.text.strip().lower().startswith('error'):
                    self.signals.error.emit(f"API Error: {page_response.text}")
                    return

                page_root = ET.fromstring(page_response.content)
                if page_root.tag == 'response' and page_root.get('success') == 'false':
                    error_msg = page_root.get('message', 'Unknown API error')
                    self.signals.error.emit(f"API Error: {error_msg}")
                    return

                posts = page_root.findall('post')
                if not posts: break
                for post in posts:
                    if file_url := post.get('file_url'):
                        all_urls.append(file_url)
                self.signals.log.emit(f"Fetched {len(all_urls)} / {total_count} URLs...")
                page += 1
            self.signals.finished.emit(all_urls)
        except requests.exceptions.RequestException as e:
            self.signals.error.emit(f"Network Error: {e}")
        except ET.ParseError as e:
            self.signals.error.emit(f"XML Parse Error: {e}. Response may not be valid XML.")
        except Exception as e:
            self.signals.error.emit(f"An unexpected error occurred: {e}")

class ImageDownloader(QRunnable):
    def __init__(self, url, download_path):
        super().__init__()
        self.signals = WorkerSignals()
        self.url = url
        self.download_path = download_path

    def run(self):
        try:
            filename = self.url.split('/')[-1]
            if '?' in filename:
                filename = filename.split('?')[0]
            save_path = os.path.join(self.download_path, filename)

            if os.path.exists(save_path):
                self.signals.log.emit(f"Skipped (already exists): {filename}")
                self.signals.finished.emit(None)
                return

            encoded_url = urllib.parse.quote(self.url, safe=':/?#[]@!$&\'()*+,;=')
            proxy_download_url = f"your-workers-link" + f"/image?url={encoded_url}"
            self.signals.log.emit(f"Proxying download: {filename}")
            response = requests.get(proxy_download_url, stream=True, timeout=30)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            self.signals.log.emit(f"Downloaded: {filename}")
            self.signals.finished.emit(None)
        except requests.exceptions.RequestException as e:
            self.signals.error.emit(f"Failed to download {self.url}: {e}")
        except Exception as e:
            self.signals.error.emit(f"Error saving {self.url}: {e}")

class DownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_download_path = os.path.expanduser("~/pgn/ace/downloads")
        self.download_path = self.base_download_path
        self.image_urls = []
        self.downloads_complete = 0
        self.total_to_download = 0
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(5)

        # --- Autocomplete setup ---
        # Use QStandardItemModel to hold different data roles
        self.completer_model = QStandardItemModel()
        self.autocomplete_timer = QTimer(self)
        self.autocomplete_timer.setSingleShot(True)
        self.autocomplete_timer.setInterval(300) # 300ms delay
        self.autocomplete_timer.timeout.connect(self.fetch_autocomplete_suggestions)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("PGN ACE Downloader v2-M3")
        self.setGeometry(100, 100, 600, 700)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        api_status_label = QLabel(f"User ID: {API_USER_ID[:8]}..." if len(API_USER_ID) > 8 else f'User ID: {API_USER_ID}')
        api_status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        main_layout.addWidget(api_status_label)

        tags_label = QLabel("Tags (space-separated)")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("e.g., character_name series_name")
        self.tags_input.textChanged.connect(self.trigger_autocomplete)

        # --- Completer setup ---
        self.completer = QCompleter(self.completer_model, self)
        # **CRITICAL FIX**: Tell the completer to use a different role for the actual completion text
        self.completer.setCompletionRole(Qt.ItemDataRole.UserRole)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.tags_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completion_activated)

        deny_tags_label = QLabel("Denied Tags (space-separated)")
        self.deny_tags_input = QLineEdit()
        self.deny_tags_input.setPlaceholderText("e.g., monochrome text")

        ai_layout = QHBoxLayout()
        ai_label = QLabel("Filter AI Content:")
        self.ai_slider = QSlider(Qt.Orientation.Horizontal)
        self.ai_slider.setRange(0, 1)
        self.ai_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.ai_slider.setFixedWidth(50)
        self.ai_slider_label = QLabel("Off")
        self.ai_slider.valueChanged.connect(lambda v: self.ai_slider_label.setText("On" if v else "Off"))
        ai_layout.addWidget(ai_label)
        ai_layout.addWidget(self.ai_slider)
        ai_layout.addWidget(self.ai_slider_label)
        ai_layout.addStretch()

        path_layout = QHBoxLayout()
        self.path_label = QLabel(f"Download to: {self.download_path}")
        self.path_button = QPushButton("Select Folder")
        self.path_button.clicked.connect(self.select_directory)
        path_layout.addWidget(self.path_label)
        path_layout.addStretch()
        path_layout.addWidget(self.path_button)

        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download_process)
        self.progress_bar = QProgressBar()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        main_layout.addWidget(tags_label)
        main_layout.addWidget(self.tags_input)
        main_layout.addWidget(deny_tags_label)
        main_layout.addWidget(self.deny_tags_input)
        main_layout.addLayout(ai_layout)
        main_layout.addSpacing(15)
        main_layout.addLayout(path_layout)
        main_layout.addSpacing(15)
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(QLabel("Log"))
        main_layout.addWidget(self.log_output)

    def trigger_autocomplete(self, text):
        last_word = text.split(' ')[-1]
        if len(last_word) >= 2:
            self.autocomplete_timer.start()
        else:
            self.completer_model.clear()

    def fetch_autocomplete_suggestions(self):
        last_word = self.tags_input.text().split(' ')[-1]
        if not last_word: return
        fetcher = AutocompleteFetcher(query=last_word)
        fetcher.signals.finished.connect(self.on_autocomplete_success)
        fetcher.signals.error.connect(self.log_message)
        self.threadpool.start(fetcher)

    def on_autocomplete_success(self, suggestions_data):
        """ Populates the QStandardItemModel with display and user roles. """
        self.completer_model.clear()
        for suggestion in suggestions_data:
            item = QStandardItem(suggestion['label']) # Text to be displayed
            # Text to be inserted by the completer
            item.setData(suggestion['value'], Qt.ItemDataRole.UserRole)
            self.completer_model.appendRow(item)

    def on_completion_activated(self, text):
        """ The completer now inserts the correct text. This just adds a space. """
        current_text = self.tags_input.text()
        if not current_text.endswith(' '):
            self.tags_input.setText(current_text + ' ')

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.base_download_path)
        if path:
            self.download_path = path
            self.path_label.setText(f"Download to: {self.download_path}")

    def log_message(self, message):
        self.log_output.appendPlainText(message)

    def set_ui_enabled(self, enabled):
        self.tags_input.setEnabled(enabled)
        self.deny_tags_input.setEnabled(enabled)
        self.ai_slider.setEnabled(enabled)
        self.path_button.setEnabled(enabled)
        self.start_button.setEnabled(enabled)
        self.start_button.setText("Start Download" if enabled else "Working...")

    def start_download_process(self):
        if API_USER_ID.startswith("YOUR_") or API_KEY.startswith("YOUR_"):
            self.log_message("ERROR: Please update the API_USER_ID and API_KEY variables.")
            return

        tags_list = [t for t in re.split(r'[\s,]+', self.tags_input.text().strip()) if t]
        if not tags_list:
            self.log_message("Error: At least one search tag is required.")
            return

        deny_tags_list = [t for t in re.split(r'[\s,]+', self.deny_tags_input.text().strip()) if t]
        final_tags = tags_list + [f"-{tag}" for tag in deny_tags_list]
        if self.ai_slider.value() == 1:
            final_tags.extend(["-ai_generated", "-ai_assisted"])

        tags_string = " ".join(final_tags)
        tags_folder_name = "_".join(re.sub(r'[^A-Za-z0-9._-]', '_', t.lstrip('-')) for t in tags_list if not t.startswith('-'))
        self.download_path = os.path.join(self.base_download_path, tags_folder_name)
        os.makedirs(self.download_path, exist_ok=True)
        self.path_label.setText(f"Download to: {self.download_path}")

        self.set_ui_enabled(False)
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.log_message(f"Starting search with tags: {tags_string}")
        self.log_message(f"Downloads will be saved to: {self.download_path}")

        fetcher = ApiFetcher(tags=tags_string)
        fetcher.signals.finished.connect(self.on_url_fetch_complete)
        fetcher.signals.error.connect(self.on_fetch_error)
        fetcher.signals.log.connect(self.log_message)
        self.threadpool.start(fetcher)

    def on_fetch_error(self, error_message):
        self.log_message(f"ERROR: {error_message}")
        self.set_ui_enabled(True)

    def on_url_fetch_complete(self, urls):
        self.image_urls = urls
        self.total_to_download = len(urls)

        if self.total_to_download == 0:
            self.log_message("Finished: No images to download.")
            self.set_ui_enabled(True)
            return

        self.log_message(f"URL fetch complete. Found {self.total_to_download} images.")
        self.log_message("Starting image downloads...")
        self.progress_bar.setMaximum(self.total_to_download)
        self.downloads_complete = 0

        for url in self.image_urls:
            downloader = ImageDownloader(url, self.download_path)
            downloader.signals.finished.connect(self.on_download_finished)
            downloader.signals.error.connect(self.log_message)
            downloader.signals.log.connect(self.log_message)
            self.threadpool.start(downloader)

    def on_download_finished(self):
        self.downloads_complete += 1
        self.progress_bar.setValue(self.downloads_complete)
        if self.downloads_complete == self.total_to_download:
            self.log_message("All downloads complete!")
            self.set_ui_enabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    app.setStyleSheet(DARK_STYLESHEET)
    font = QFont("SF Pro")
    if font.family() != "SF Pro": font = QFont("Arial")
    app.setFont(font)
    main_window = DownloaderApp()
    main_window.show()
    sys.exit(app.exec())
