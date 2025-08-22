import sys
import os
import requests
import xml.etree.ElementTree as ET
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QLabel, QProgressBar,
    QPlainTextEdit, QSlider, QStyleFactory, QGroupBox
)
from PyQt6.QtCore import (
    Qt, QRunnable, QThreadPool, pyqtSignal, QObject
)
from PyQt6.QtGui import QFont, QIcon

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
QGroupBox {
    font-weight: bold;
    border: 1px solid #4e4e4e;
    border-radius: 5px;
    margin-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 3px 0 3px;
}
QLabel {
    font-size: 14px;
    font-weight: bold;
}
QLineEdit, QPlainTextEdit {
    background-color: #3e3e3e;
    border: 1px solid #4e4e4e;
    border-radius: 5px;
    padding: 6px;
    color: #e0e0e0;
}
QPushButton {
    background-color: #5e5e5e;
    color: white;
    font-weight: bold;
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #6e6e6e;
}
QPushButton:pressed {
    background-color: #4e4e4e;
}
QPushButton:disabled {
    background-color: #3e3e3e;
    color: #8e8e8e;
}
QProgressBar {
    border: 1px solid #4e4e4e;
    border-radius: 5px;
    text-align: center;
    color: #e0e0e0;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #6e6e6e;
    border-radius: 4px;
}
QSlider::groove:horizontal {
    border: 1px solid #4e4e4e;
    height: 3px;
    background: #3e3e3e;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #e0e0e0;
    border: 1px solid #4e4e4e;
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

class ProxyManager(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()

    def run(self):
        self.signals.log.emit("Attempting to find a working proxy...")
        try:
            # Using a public API that provides a list of free proxies
            response = requests.get("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all", timeout=15)
            response.raise_for_status()
            proxies = response.text.strip().split('\n')
            random.shuffle(proxies)

            for proxy_address in proxies:
                proxy = {"http": f"http://{proxy_address.strip()}", "https": f"http://{proxy_address.strip()}"}
                self.signals.log.emit(f"Testing proxy: {proxy_address}")
                try:
                    # Test the proxy by making a request to a reliable service
                    test_response = requests.get("https://httpbin.org/ip", proxies=proxy, timeout=10)
                    test_response.raise_for_status()
                    self.signals.log.emit(f"Success! Using proxy: {proxy_address}")
                    self.signals.finished.emit(proxy)
                    return
                except requests.exceptions.RequestException:
                    self.signals.log.emit(f"Proxy {proxy_address} failed. Trying next...")
                    continue
            self.signals.error.emit("Could not find a working proxy automatically.")
        except requests.exceptions.RequestException as e:
            self.signals.error.emit(f"Failed to fetch proxy list: {e}")
        except Exception as e:
            self.signals.error.emit(f"An unexpected error occurred while finding a proxy: {e}")

class ApiFetcher(QRunnable):
    def __init__(self, tags, proxy):
        super().__init__()
        self.signals = WorkerSignals()
        self.tags = tags
        self.proxy = proxy
        self.base_url = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"

    def run(self):
        try:
            self.signals.log.emit("Fetching post count...")
            params = {'limit': 0, 'tags': self.tags}
            response = requests.get(self.base_url, params=params, proxies=self.proxy, timeout=15)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            total_count = int(root.get('count'))

            if total_count == 0:
                self.signals.log.emit("No posts found with the given tags.")
                self.signals.finished.emit([])
                return

            self.signals.log.emit(f"Found {total_count} posts. Fetching URLs...")

            all_urls = []
            page = 0
            limit = 1000
            while len(all_urls) < total_count:
                params = {'limit': limit, 'pid': page, 'tags': self.tags}
                page_response = requests.get(self.base_url, params=params, proxies=self.proxy, timeout=15)
                page_response.raise_for_status()
                page_root = ET.fromstring(page_response.content)

                posts = page_root.findall('post')
                if not posts:
                    break

                for post in posts:
                    file_url = post.get('file_url')
                    if file_url:
                        all_urls.append(file_url)

                self.signals.log.emit(f"Fetched {len(all_urls)} / {total_count} URLs...")
                page += 1

            self.signals.finished.emit(all_urls)

        except requests.exceptions.RequestException as e:
            self.signals.error.emit(f"Network Error: {e}")
        except Exception as e:
            self.signals.error.emit(f"An unexpected error occurred: {e}")

class ImageDownloader(QRunnable):
    def __init__(self, url, download_path, proxy):
        super().__init__()
        self.signals = WorkerSignals()
        self.url = url
        self.download_path = download_path
        self.proxy = proxy

    def run(self):
        try:
            filename = self.url.split('/')[-1]
            save_path = os.path.join(self.download_path, filename)

            if os.path.exists(save_path):
                self.signals.log.emit(f"Skipped (already exists): {filename}")
                self.signals.finished.emit(None)
                return

            response = requests.get(self.url, stream=True, proxies=self.proxy, timeout=30)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.signals.log.emit(f"Downloaded: {filename}")
            self.signals.finished.emit(None)

        except requests.exceptions.RequestException as e:
            self.signals.error.emit(f"Failed to download {self.url}: {e}")
        except Exception as e:
            self.signals.error.emit(f"Error saving {self.url}: {e}")

class DownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.download_path = os.path.expanduser("~/Downloads")
        self.image_urls = []
        self.downloads_complete = 0
        self.total_to_download = 0
        self.proxy = None
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(8)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("PGN ACE Downloader")
        self.setGeometry(100, 100, 600, 800)
        self.setWindowIcon(QIcon('ace.png'))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Search Settings ---
        search_group = QGroupBox("Search Settings")
        search_layout = QVBoxLayout()

        tags_label = QLabel("Tags (space-separated)")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("e.g., character_name series_name")

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

        search_layout.addWidget(tags_label)
        search_layout.addWidget(self.tags_input)
        search_layout.addWidget(deny_tags_label)
        search_layout.addWidget(self.deny_tags_input)
        search_layout.addLayout(ai_layout)
        search_group.setLayout(search_layout)

        # --- Proxy Settings ---
        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QVBoxLayout()
        self.proxy_status_label = QLabel("Status: No Proxy")
        self.find_proxy_button = QPushButton("Auto-Find Proxy")
        self.find_proxy_button.clicked.connect(self.find_proxy)
        self.clear_proxy_button = QPushButton("Use Direct Connection")
        self.clear_proxy_button.clicked.connect(self.clear_proxy)
        proxy_layout.addWidget(self.proxy_status_label)
        proxy_layout.addWidget(self.find_proxy_button)
        proxy_layout.addWidget(self.clear_proxy_button)
        proxy_group.setLayout(proxy_layout)


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
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        log_label = QLabel("Log")
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        main_layout.addWidget(search_group)
        main_layout.addWidget(proxy_group)
        main_layout.addSpacing(15)
        main_layout.addLayout(path_layout)
        main_layout.addSpacing(15)
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_output)

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_path)
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
        self.find_proxy_button.setEnabled(enabled)
        self.clear_proxy_button.setEnabled(enabled)

        if enabled:
            self.start_button.setText("Start Download")
            self.find_proxy_button.setText("Auto-Find Proxy")
        else:
            self.start_button.setText("Working...")

    def find_proxy(self):
        self.set_ui_enabled(False)
        self.find_proxy_button.setText("Searching...")
        self.log_output.clear()
        self.log_message("Starting automatic proxy search...")
        proxy_finder = ProxyManager()
        proxy_finder.signals.finished.connect(self.on_proxy_found)
        proxy_finder.signals.error.connect(self.on_fetch_error)
        proxy_finder.signals.log.connect(self.log_message)
        self.threadpool.start(proxy_finder)

    def on_proxy_found(self, proxy):
        self.proxy = proxy
        proxy_address = list(proxy.values())[0]
        self.proxy_status_label.setText(f"Status: Using Proxy {proxy_address}")
        self.log_message(f"Proxy set: {proxy_address}")
        self.set_ui_enabled(True)

    def clear_proxy(self):
        self.proxy = None
        self.proxy_status_label.setText("Status: No Proxy (Direct Connection)")
        self.log_message("Proxy cleared. Using a direct connection.")

    def start_download_process(self):
        tags_list = self.tags_input.text().strip().split()
        deny_tags_list = self.deny_tags_input.text().strip().split()

        if not tags_list:
            self.log_message("Error: At least one search tag is required.")
            return

        final_tags = tags_list
        for tag in deny_tags_list:
            final_tags.append(f"-{tag}")

        if self.ai_slider.value() == 1:
            final_tags.append("-ai_generated")
            final_tags.append("-ai_assisted")

        tags_string = " ".join(final_tags)

        self.set_ui_enabled(False)
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.log_message(f"Starting search with tags: {tags_string}")
        if self.proxy:
            self.log_message(f"Using proxy: {list(self.proxy.values())[0]}")
        else:
            self.log_message("Using direct connection.")


        fetcher = ApiFetcher(tags=tags_string, proxy=self.proxy)
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
            downloader = ImageDownloader(url, self.download_path, self.proxy)
            downloader.signals.finished.connect(self.on_download_finished)
            downloader.signals.error.connect(self.log_message)
            downloader.signals.log.connect(self.log_message)
            self.threadpool.start(downloader)

    def on_download_finished(self, _):
        self.downloads_complete += 1
        self.progress_bar.setValue(self.downloads_complete)

        if self.downloads_complete == self.total_to_download:
            self.log_message("All downloads complete!")
            self.set_ui_enabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    app.setStyleSheet(DARK_STYLESHEET)
    # Note: 'SF Pro' might not be available on all systems.
    # PyQt will fall back to a default font if it's not found.
    font = QFont("SF Pro")
    app.setFont(font)

    main_window = DownloaderApp()
    main_window.show()
    sys.exit(app.exec())