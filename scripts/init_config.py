#!/usr/bin/env python3
"""Generate a WixScraper config.json from a Wix site URL."""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests

DEFAULT_WAIT = 3
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts = []
        self.in_title = False
        self.metadata = {}
        self.canonical = ''

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'title':
            self.in_title = True
            return

        if tag == 'meta':
            key = attributes.get('name') or attributes.get('property')
            content = attributes.get('content')
            if key and content:
                self.metadata[key.strip().lower()] = html_module.unescape(content.strip())
            return

        if tag == 'link':
            rel_value = attributes.get('rel', '')
            rel_tokens = rel_value.lower().split() if isinstance(rel_value, str) else []
            if 'canonical' in rel_tokens:
                href = attributes.get('href')
                if href:
                    self.canonical = href.strip()

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self):
        return html_module.unescape(''.join(self.title_parts)).strip()


def ensure_url_has_scheme(value):
    stripped_value = value.strip()
    if not stripped_value:
        raise ValueError('site URL cannot be empty')
    if '://' not in stripped_value:
        stripped_value = f'https://{stripped_value}'
    return stripped_value


def clean_site_url(site_url):
    parsed_url = urlsplit(ensure_url_has_scheme(site_url))
    return urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', ''))


def normalize_path_segment(segment):
    decoded_segment = unquote(segment).strip().lower()
    ascii_segment = re.sub(r'[^a-z0-9\s-]', '', decoded_segment)
    ascii_segment = re.sub(r'[\s_-]+', '-', ascii_segment)
    ascii_segment = re.sub(r'-{2,}', '-', ascii_segment).strip('-')
    return ascii_segment or 'page'


def infer_block_primary_folder(site_url):
    parsed_url = urlsplit(ensure_url_has_scheme(site_url))
    path_segments = [segment for segment in parsed_url.path.split('/') if segment]
    if path_segments:
        return path_segments[0]

    hostname = parsed_url.hostname or ''
    if hostname.endswith('.wixsite.com'):
        return hostname.split('.wixsite.com', 1)[0]

    return ''


def normalize_site_path(raw_path, block_primary_folder=''):
    parsed_url = urlsplit(raw_path)
    path = parsed_url.path or raw_path

    if block_primary_folder:
        primary_prefix = '/' + block_primary_folder.strip('/')
        if path == primary_prefix:
            path = '/'
        elif path.startswith(primary_prefix + '/'):
            path = path[len(primary_prefix):]

    segments = [normalize_path_segment(segment) for segment in path.split('/') if segment]
    if not segments:
        return '/'

    return '/' + '/'.join(segments)


def humanize_slug(value):
    cleaned_value = re.sub(r'[-_]+', ' ', value.strip())
    cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
    return cleaned_value.title() if cleaned_value else 'Wix Site'


def site_label_from_url(site_url, block_primary_folder):
    parsed_url = urlsplit(site_url)
    if block_primary_folder:
        return humanize_slug(block_primary_folder)

    hostname = parsed_url.hostname or ''
    if hostname.endswith('.wixsite.com'):
        return humanize_slug(hostname.split('.wixsite.com', 1)[0])

    if parsed_url.path:
        path_segments = [segment for segment in parsed_url.path.split('/') if segment]
        if path_segments:
            return humanize_slug(path_segments[0])

    return humanize_slug(hostname.split('.')[0] if hostname else '')


def fetch_page_metadata(site_url):
    parser = MetadataParser()
    response = requests.get(
        site_url,
        headers={'User-Agent': DEFAULT_USER_AGENT},
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    parser.feed(response.text)

    return {
        'title': parser.title,
        'description': parser.metadata.get('description') or parser.metadata.get('og:description') or parser.metadata.get('twitter:description') or '',
        'keywords': parser.metadata.get('keywords') or '',
        'canonical': parser.canonical,
        'image': parser.metadata.get('og:image') or parser.metadata.get('twitter:image') or '',
        'author': parser.metadata.get('author') or '',
        'og_title': parser.metadata.get('og:title') or '',
        'og_description': parser.metadata.get('og:description') or '',
    }


def build_root_metadata(site_url, block_primary_folder, fetched_metadata):
    site_label = site_label_from_url(site_url, block_primary_folder)
    title = (
        fetched_metadata.get('title')
        or fetched_metadata.get('og_title')
        or site_label
    )
    description = (
        fetched_metadata.get('description')
        or fetched_metadata.get('og_description')
        or f'Offline copy of {title} generated from {site_url}.'
    )
    canonical = fetched_metadata.get('canonical') or site_url
    image = fetched_metadata.get('image') or ''
    if image:
        image = urljoin(site_url, image)
    if canonical:
        canonical = urljoin(site_url, canonical)

    return {
        'title': title,
        'description': description,
        'keywords': fetched_metadata.get('keywords') or title,
        'canonical': canonical,
        'image': image,
        'author': fetched_metadata.get('author') or '',
    }


def build_config(site_url, wait, recursive, dark_website, force_download_again, skip_fetch):
    clean_url = clean_site_url(site_url)
    block_primary_folder = infer_block_primary_folder(clean_url)
    page_key = normalize_site_path(clean_url, block_primary_folder)

    fetched_metadata = {}
    if not skip_fetch:
        try:
            fetched_metadata = fetch_page_metadata(clean_url)
        except Exception as exc:
            print(f'Warning: could not fetch metadata from {clean_url}: {exc}', file=sys.stderr)

    root_metadata = build_root_metadata(clean_url, block_primary_folder, fetched_metadata)
    metatags = {
        page_key: root_metadata,
    }
    if page_key != '/':
        metatags['/'] = root_metadata

    config = {
        'site': clean_url,
        'blockPrimaryFolder': block_primary_folder,
        'wait': wait,
        'recursive': recursive,
        'darkWebsite': dark_website,
        'forceDownloadAgain': force_download_again,
        'metatags': metatags,
        'mapData': {},
    }

    return config


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a WixScraper config.json from a Wix site URL.')
    parser.add_argument('site', help='The Wix site URL to use as the scraper starting point.')
    parser.add_argument('--output', default='config.json', help='Where to write the generated JSON config.')
    parser.add_argument('--wait', type=int, default=DEFAULT_WAIT, help='Seconds to wait before processing a page.')
    parser.add_argument('--recursive', dest='recursive', action='store_true', help='Crawl linked pages as well.')
    parser.add_argument('--no-recursive', dest='recursive', action='store_false', help='Only scrape the starting page.')
    parser.add_argument('--dark-website', dest='dark_website', action='store_true', help='Apply dark theme rewriting.')
    parser.add_argument('--light-website', dest='dark_website', action='store_false', help='Do not apply dark theme rewriting.')
    parser.add_argument('--force-download-again', dest='force_download_again', action='store_true', help='Download local assets again even if they already exist.')
    parser.add_argument('--reuse-downloaded-files', dest='force_download_again', action='store_false', help='Reuse already downloaded assets when possible.')
    parser.add_argument('--skip-fetch', action='store_true', help='Do not fetch the live site for metadata.')
    parser.set_defaults(recursive=True, dark_website=False, force_download_again=False)
    return parser.parse_args()


def main():
    args = parse_args()
    config = build_config(
        args.site,
        args.wait,
        args.recursive,
        args.dark_website,
        args.force_download_again,
        args.skip_fetch,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {output_path.resolve()}')


if __name__ == '__main__':
    main()
