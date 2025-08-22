# PGN ACE Downloader & Proxy
*v2-M3*

This repository contains a desktop application built with PyQt6 for downloading images from a specific API, and a supporting Cloudflare Worker that acts as a proxy to handle API requests and image downloads. The proxy is necessary to bypass potential CORS restrictions and to handle the large number of requests from the desktop application, and to bypass any potential client-side restrictions.

## Features

    Tag-Based Search: Find and download images using a powerful tag system.

    Autocomplete Suggestions: Get real-time tag suggestions to improve search accuracy.

    Download Management: Track download progress with a progress bar and a detailed log.

    Customizable Settings: Choose your download path and filter out unwanted content.

    CORS Proxy: The Cloudflare Worker script ensures reliable access to the external API and image URLs.

⚙️ Prerequisites
For the Downloader (downloader.py)

    Python 3.x

    PyQt6: For the graphical user interface.

    Requests: For making HTTP requests.

You can install the required Python packages using pip:
```
pip install PyQt6 requests
```
For the Proxy (cloudflare_worker.js)

    Cloudflare Account: You need an account to deploy the worker.

    Web Browser: To access the Cloudflare dashboard.

## Setup and Usage
1. Cloudflare Worker Setup

    Deploy the Worker via Dashboard:

        Log in to your Cloudflare Dashboard.

        On the left-hand navigation, click on Workers & Pages.

        Click the Create application button.

        Choose Create Worker.

        Give your worker a name and then click Deploy.

        After the worker is deployed, click on Edit code.

        Delete the default code in the editor and copy/paste the entire contents of cloudflare_worker.js into it.

        Click Save and Deploy.

        Once saved, a unique URL will be assigned to your worker (e.g., your-worker-name.your-username.workers.dev). Copy this URL.

2. Downloader Application Setup

    Update Credentials: Open dwp_beta_fixed.py.

    Find the API_USER_ID and API_KEY variables at the top of the file and replace the placeholders with your actual API credentials, obtained from the host (green) website.

    Update Worker URL: In the AutocompleteFetcher, ApiFetcher, and ImageDownloader classes, replace "your-workers-link" with the URL you copied in the previous step.

3. Running the Downloader

Execute the Python script from your terminal:

python downloader.py

A graphical window will appear. Enter your search tags and click "Start Download" to begin the process.

©2025 PGN
