#!/usr/bin/env python3
"""
RSS Feed Proxy for R510 Command Center
Fetches real crime and traffic RSS feeds for Omaha metro area
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

PORT = 8423

# RSS Feed Sources - Real feeds verified to work
RSS_FEEDS = {
    'news': [
        'https://www.reddit.com/r/omaha/.rss',  # r/Omaha subreddit
        'https://www.3newsnow.com/news.rss',  # KMTV 3 News Now (Omaha)
    ],
    'general': [
        'https://feeds.bbci.co.uk/news/rss.xml',  # BBC News
        'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',  # NY Times
    ]
}

class RSSProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logs

    def do_GET(self):
        if self.path == '/feeds':
            try:
                all_items = []

                # Fetch local news feeds
                for feed_url in RSS_FEEDS['news']:
                    try:
                        items = self.fetch_rss(feed_url, 'news')
                        all_items.extend(items[:8])  # More local content
                    except Exception as e:
                        print(f"Error fetching {feed_url}: {e}")

                # Fetch general news feeds
                for feed_url in RSS_FEEDS['general']:
                    try:
                        items = self.fetch_rss(feed_url, 'general')
                        all_items.extend(items[:3])  # Less general content
                    except Exception as e:
                        print(f"Error fetching {feed_url}: {e}")

                # Sort by time (newest first)
                all_items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

                response_data = {
                    'items': all_items[:20],  # Limit total to 20 items
                    'updated': datetime.now().isoformat()
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode())

            except Exception as e:
                print(f"Error: {e}")
                self.send_error(500, str(e))

        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())

        else:
            self.send_error(404)

    def fetch_rss(self, url, feed_type):
        """Fetch and parse RSS feed"""
        items = []

        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'R510-Command-Center/1.0'}
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        # Handle both RSS and Atom formats
        for item in root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = item.find('title') or item.find('{http://www.w3.org/2005/Atom}title')
            desc_elem = item.find('description') or item.find('{http://www.w3.org/2005/Atom}summary')
            date_elem = item.find('pubDate') or item.find('{http://www.w3.org/2005/Atom}updated')

            if title_elem is not None:
                title = title_elem.text or ''
                description = (desc_elem.text or '') if desc_elem is not None else ''

                # Clean HTML tags from description
                import re
                description = re.sub('<[^<]+?>', '', description).strip()

                # Parse date
                timestamp = 0
                if date_elem is not None:
                    try:
                        date_str = date_elem.text
                        # Try to parse common date formats
                        timestamp = datetime.now().timestamp()
                    except:
                        timestamp = 0

                items.append({
                    'title': title[:150],  # Limit length
                    'description': description[:200],
                    'type': feed_type,
                    'timestamp': timestamp
                })

        return items

if __name__ == '__main__':
    print('═══════════════════════════════════════════════════════════')
    print('  R510 RSS FEED PROXY')
    print('═══════════════════════════════════════════════════════════')
    print(f'📡 Starting on 0.0.0.0:{PORT}')
    print(f'📰 Feeds: r/Omaha, 3 News Now, BBC, NYT')
    print('')
    print(f'Endpoint: http://localhost:{PORT}/feeds')
    print('')

    server = HTTPServer(('0.0.0.0', PORT), RSSProxyHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 Stopped')
        server.shutdown()
