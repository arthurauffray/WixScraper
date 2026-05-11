# Import puppeteer
import json
from urllib.parse import urlparse
import urllib.parse
from pyppeteer import launch
import re
import asyncio
import os
import requests
import unicodedata
import shutil
from PIL import Image

# Scroll to the bottom to load all content
async def scroll_to_bottom(page):
    pageHeight = await page.evaluate('document.body.scrollHeight')
    for i in range(0, pageHeight, 100):
        await page.evaluate(f'window.scrollTo(0, {i})')
        await asyncio.sleep(0.1)
    await asyncio.sleep(1)

# Only use this function in compliance with Wix Terms of Service. 
async def delete_wix(page):
    # Delete the wix header
    # with id WIX_ADS
    await page.evaluate('''() => {
        const element = document.getElementById('WIX_ADS');
        element.parentNode.removeChild(element);
    }''')

    # Edit the in-line CSS defined in <style> tag
    # delete any string "--wix-ads"
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('style');
        for (const element of elements) {
            const text = element.textContent || '';
            if (text.includes('--wix-ads')) {
                element.textContent = text.replace('--wix-ads', '');
            }
        }
    }''')

    # delete any string "Made with Wix"
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('span');
        for (const element of elements) {
            const text = element.textContent || '';
            if (text.includes('Made with Wix') && element.parentNode) {
                element.parentNode.removeChild(element);
            }
        }
    }''')

    # Remove all scripts 
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('script');
        for (const element of elements) {
            element.parentNode.removeChild(element);
        }
    }''')

    # Remove all link tags
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('link');
        for (const element of elements) {
            element.parentNode.removeChild(element);
        }
    }''')

async def fix_gallery(page):

    # If pro-gallery is a class on the page,
    # then we need to fix the gallery

    # Get the gallery element
    gallery = await page.querySelector('.pro-gallery')

    if(gallery != None):

        print("Found gallery! Fixing..")
        
        # Import slick.carousel
        await page.addScriptTag(url='https://cdn.jsdelivr.net/npm/jquery@3.6.4/dist/jquery.min.js')
        await page.addStyleTag(url='https://cdnjs.cloudflare.com/ajax/libs/slick-carousel/1.9.0/slick.css')
        await page.addStyleTag(url='https://cdnjs.cloudflare.com/ajax/libs/slick-carousel/1.9.0/slick-theme.css')
        await page.addScriptTag(url='https://cdnjs.cloudflare.com/ajax/libs/slick-carousel/1.9.0/slick.min.js')

        # Get all img links
        img_links = await gallery.querySelectorAllEval('img', 'nodes => nodes.map(n => n.src)')
    
        # Create the carousel and insert it two parents above the gallery
        await page.evaluate('''() => {
            const element = document.createElement('div');
            element.className = 'slick-carousel';
            document.querySelector('.pro-gallery').parentNode.parentNode.insertBefore(element, document.querySelector('.pro-gallery').parentNode);
        }''')

        # Delete all siblings of the slick carousel
        await page.evaluate('''() => {
            const element = document.querySelector('.slick-carousel');
            while (element.nextSibling) {
                element.nextSibling.parentNode.removeChild(element.nextSibling);
            }
        }''')

        # Add the images to the carousel
        for link in img_links:
            await page.evaluate(f'''() => {{
                const element = document.createElement('img');
                element.src = '{link}';
                element.alt = 'Gallery Image';
                document.querySelector('.slick-carousel').appendChild(element);
            }}''')

        # Add the above evaluation as a script tag
        await page.addScriptTag(content='''
        window.addEventListener('DOMContentLoaded', function() {
            if (typeof window.jQuery === 'undefined' || typeof window.jQuery.fn?.slick === 'undefined') {
                return;
            }

            var $jq = window.jQuery.noConflict();
            $jq(function () {
                $jq('.slick-carousel').slick({
                    dots: true,
                    infinite: true,
                    speed: 300,
                    slidesToShow: 2,
                    responsive: [
                        {
                        breakpoint: 1024,
                        settings: {
                            slidesToShow: 1,
                        }
                        },
                        {
                        breakpoint: 600,
                        settings: {
                            slidesToShow: 1,
                        }
                        }
                    ]
                });
            });
        });''')

async def fix_googlemap(page, mapData):

    # Get the one titled = "Google Maps"
    googlemap = await page.querySelector('wix-iframe[title="Google Maps"]')

    if(googlemap != None):

        print("Found Google Maps! Fixing..")

        # Import leaflet
        await page.addStyleTag(url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.3/leaflet.css')

        await page.evaluate('''() => {
            const element = document.createElement('script');
            element.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.3/leaflet.js';
            document.querySelector('script').parentNode.insertBefore(element, document.querySelector('script').nextSibling);
        }''')

        # Add new style tag to the page
        await page.addStyleTag(content='''
        #map { height: 100%; }

        html, body { height: 100%; margin: 0; padding: 0; }

        :root {
        
        --map-tiles-filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7);

        }

        @media (prefers-color-scheme: dark) {
            .map-tiles {
                filter:var(--map-tiles-filter, none);
            }
        }''')

        # Add a new map div next to the google map
        await page.evaluate('''() => {
            const element = document.createElement('div');
            element.id = 'map';
            document.querySelector('iframe[title="Google Maps"]').parentNode.insertBefore(element, document.querySelector('iframe[title="Google Maps"]').nextSibling);
        }''')

        # Delete all siblings of the map div
        await page.evaluate('''() => {
            const element = document.querySelector('#map');
            while (element.nextSibling) {
                element.nextSibling.parentNode.removeChild(element.nextSibling);
            }
        }''')

        

        content = '''
        window.addEventListener('DOMContentLoaded', function() {

        var map = L.map('map').setView([''' + mapData['latitude'] + ',' + mapData['longitude'] + '],' + mapData['zoom'] + ''');

        // set tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors',
            className: 'map-tiles'
        }).addTo(map);

        // add marker
        L.marker([''' + mapData['mapMarker']['latitude'] + ',' + mapData['mapMarker']['longitude'] + ''']).addTo(map)
            .bindPopup(" ''' + mapData['mapMarker']['popup'] + ''' ")
            .openPopup();
            
        });'''

        # Instead of addScriptTag, append the entire above script as a <script> at the end of the body
        await page.evaluate('''() => {
            const element = document.createElement('script');
            element.innerHTML = `''' + content + '''`;
            document.querySelector('body').appendChild(element);
        }''')

        # Delete the google map iframe
        await page.evaluate('''() => {
            const element = document.querySelector('iframe[title="Google Maps"]');
            element.parentNode.removeChild(element);
        }''')      

        # Add preconnect to openstreetmap
        await page.evaluate('''() => {
            const element = document.createElement('link');
            element.rel = 'preconnect';
            element.href = 'https://a.tile.openstreetmap.org';
            document.querySelector('head').appendChild(element);
            element.href = 'https://b.tile.openstreetmap.org';
            document.querySelector('head').appendChild(element);
            element.href = 'https://c.tile.openstreetmap.org';
            document.querySelector('head').appendChild(element);
        }''')


async def fix_slideshow(page):

    # Get the gallery element
    gallery = await page.querySelector('.wixui-slideshow')

    if(gallery != None):

        print("Found Slideshow! Fixing..")
        
        # Import slick.carousel
        await page.addScriptTag(url='https://cdn.jsdelivr.net/npm/jquery@3.6.4/dist/jquery.min.js')
        await page.addStyleTag(url='https://cdnjs.cloudflare.com/ajax/libs/slick-carousel/1.9.0/slick.css')
        await page.addStyleTag(url='https://cdnjs.cloudflare.com/ajax/libs/slick-carousel/1.9.0/slick-theme.css')
        await page.addScriptTag(url='https://cdnjs.cloudflare.com/ajax/libs/slick-carousel/1.9.0/slick.min.js')

        # Create the carousel and insert it two parents above the gallery
        await page.evaluate('''() => {
            const element = document.createElement('div');
            element.className = 'slick-carousel-slides';
            document.querySelector('.wixui-slideshow').parentNode.parentNode.insertBefore(element, document.querySelector('.wixui-slideshow').parentNode);
        }''')


        # Give all images inside slideshow alt tags
        await page.evaluate('''() => {
            const elements = document.querySelectorAll('nav[aria-label="Slides"] li img');
            for (const element of elements) {   
                element.alt = 'Slideshow Image';
            }
        }''')

        slides = await page.querySelectorAll('nav[aria-label="Slides"] li')

        # Ensure first slide is selected
        await asyncio.sleep(5)
        await slides[0].click()

        for slide in slides:

            await slide.click()
            await asyncio.sleep(5)

            #img_parents = await gallery.querySelectorAllEval('img', 'nodes => nodes.map(n => n.parentNode.parentNode.innerHTML)')
            slide_content = await page.querySelector('div[data-testid="slidesWrapper"] > div')

            # Get innerHTML of slide_content
            parent = await page.evaluate('(slide_content) => slide_content.innerHTML', slide_content)

            # Get all parents of img tags, iterate over and add them instead
            await page.evaluate(f'''(parent) => {{
                const element = document.createElement('div');
                element.innerHTML = parent;
                document.querySelector('.slick-carousel-slides').appendChild(element);
            }}''', parent)

        # Delete all children of slidesWrapper
        await page.evaluate('''() => {
            const element = document.querySelector('div[data-testid="slidesWrapper"]');
            while (element.firstChild) {
                element.removeChild(element.firstChild);
            }
        }''')


        # Move slick-carousel next to aria-label="Slideshow"
        await page.evaluate('''() => {
           const element = document.querySelector('.slick-carousel-slides');
           document.querySelector('.wixui-slideshow').parentNode.insertBefore(element, document.querySelector('.wixui-slideshow').nextSibling);
        }''')

        # Take the class and id from aria-label="Slideshow" and add it to slick-carousel, then delete aria-label="Slideshow"
        await page.evaluate('''() => {
           const element = document.querySelector('.wixui-slideshow');
           document.querySelector('.slick-carousel-slides').className = element.className + ' slick-carousel-slides';
           document.querySelector('.slick-carousel-slides').id = element.id;
           element.parentNode.removeChild(element);
        }''')

        # Make .slick-next class element have the style: right: 75px and .slick-prev class element have the style: left: 75px
        # using style tags
        await page.addStyleTag(content='''
        .slick-next {
            z-index: 100;
            right: 75px;
        }

        .slick-prev {
            z-index: 100;
            left: 75px;
        }''')




slideFix = '''<script>
        window.addEventListener('DOMContentLoaded', function() {
        if (typeof window.jQuery === 'undefined' || typeof window.jQuery.fn?.slick === 'undefined') {
            return;
        }

        var $jq = window.jQuery.noConflict();
        $jq(function () {
            $jq('.slick-carousel-slides').slick({
                dots: true,
                infinite: false,
                speed: 300,
                slidesToShow: 1,
                responsive: [
                    {
                    breakpoint: 1024,
                    settings: {
                        slidesToShow: 1,
                    }
                    },
                    {
                    breakpoint: 600,
                    settings: {
                        slidesToShow: 1,
                    }
                    }
                ]
            });
        });
    });</script></body>'''

lightModeFix = '''<style>
        .slick-dots li button:before {
            font-family: 'slick';
            font-size: 6px;
            line-height: 20px;
            position: absolute;
            top: 0;
            left: 0;
            width: 20px;
            height: 20px;
            content: '•';
            text-align: center;
            opacity: .25;
            color: white;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .slick-dots li.slick-active button:before {
            opacity: .75;
            color: white;
        }
    </style></head>'''

async def makeLocalImages(page, hostname, forceDownloadAgain):
        # Create images folder if it doesn't exist in hostname folder
    if not os.path.exists(hostname + '/images'):
        os.makedirs(hostname + '/images')

    def build_image_name(link):
        cleaned_link = link.split('?')[0].split('#')[0]
        path_part = cleaned_link.split('/')[-1]

        if path_part.lower() == 'file.jpeg':
            segments = cleaned_link.split('/')
            media_index = next((index for index, value in enumerate(segments) if value == 'media'), -1)
            if media_index != -1 and media_index + 1 < len(segments):
                path_part = segments[media_index + 1]

        return urllib.parse.unquote(path_part)

    # Download all image-like assets used in img tags, picture/srcset tags, and CSS backgrounds.
    imageLinks = await page.evaluate(r'''() => {
        const links = new Set();

        const addCandidate = (value) => {
            if (!value) {
                return;
            }

            const trimmed = value.trim().replace(/^url\((.*)\)$/i, '$1').replace(/^['"]|['"]$/g, '');
            if (!trimmed || trimmed.startsWith('data:') || trimmed.startsWith('blob:')) {
                return;
            }

            if (!/^https?:\/\//i.test(trimmed)) {
                return;
            }

            links.add(trimmed);
        };

        document.querySelectorAll('img').forEach((node) => {
            addCandidate(node.currentSrc || node.src || node.getAttribute('src'));
            const srcset = node.getAttribute('srcset') || '';
            srcset.split(',').forEach((candidate) => addCandidate(candidate.trim().split(/\s+/)[0] || ''));
        });

        document.querySelectorAll('source').forEach((node) => {
            const srcset = node.getAttribute('srcset') || '';
            srcset.split(',').forEach((candidate) => addCandidate(candidate.trim().split(/\s+/)[0] || ''));
        });

        document.querySelectorAll('*').forEach((node) => {
            const backgroundImage = getComputedStyle(node).backgroundImage || '';
            const matches = backgroundImage.match(/url\((.*?)\)/g) || [];
            matches.forEach((match) => addCandidate(match));
        });

        return Array.from(links);
    }''')

    for link in imageLinks:
        if not link or link.startswith('data:') or link.startswith('blob:'):
            continue

        # If a webp version of the image already exists, skip it
        imageName = build_image_name(link)
        imageBaseName = os.path.splitext(imageName)[0]

        if(not forceDownloadAgain and os.path.exists(hostname + '/images/' + imageBaseName + '.webp')):
            continue

        try:
            # Fetch each image and save it to the images folder
            # Download using requests
            r = requests.get(link, allow_redirects=True)

            contentType = r.headers.get('content-type', '')
            if('image' not in contentType and not imageName.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.svg'))):
                continue

            open(hostname + '/images/' + imageName, 'wb').write(r.content)

            # Convert each image to WebP
            im = Image.open(hostname + '/images/' + imageName)
            im.save(hostname + '/images/' + imageBaseName + '.webp', 'webp')
        except Exception as e:
            print(f"Skipping image {link}: {e}")
            continue

        # Delete the original image
        os.remove(hostname + '/images/' + imageName)

    # Replace all image links with the local image links, using the webp format
    await page.evaluate(r'''() => {
        const buildImageName = (src) => {
            const cleanedSrc = src.split('?')[0].split('#')[0];
            const segments = cleanedSrc.split('/');
            let imageName = segments[segments.length - 1];

            if (imageName.toLowerCase() === 'file.jpeg') {
                const mediaIndex = segments.findIndex((segment) => segment === 'media');
                if (mediaIndex !== -1 && mediaIndex + 1 < segments.length) {
                    imageName = segments[mediaIndex + 1];
                }
            }

            return decodeURIComponent(imageName);
        };

        const elements = document.querySelectorAll('img');
        for (const element of elements) {
            const src = element.currentSrc || element.getAttribute('src') || '';
            if (!src || src.startsWith('data:') || src.startsWith('blob:')) {
                continue;
            }

            const imageName = buildImageName(src).replace(/\.[^.]+$/, '') + '.webp';
            element.src = '../images/' + encodeURIComponent(imageName).replace(/%2F/g, '/');
            // remove any srcset
            element.removeAttribute('srcset');

            const picture = element.closest('picture');
            if (picture) {
                picture.querySelectorAll('source').forEach((source) => {
                    source.removeAttribute('srcset');
                });
            }
        }
    }''')


def build_relative_prefix(page_key):
    normalized_key = page_key.strip('/')

    if not normalized_key:
        return ''

    depth = len([segment for segment in normalized_key.split('/') if segment])
    return '../' * depth


def normalize_path_segment(segment):
    decoded = urllib.parse.unquote(segment).strip().lower()
    ascii_segment = unicodedata.normalize('NFKD', decoded).encode('ascii', 'ignore').decode('ascii')
    ascii_segment = re.sub(r'[^a-z0-9\s-]', '', ascii_segment)
    ascii_segment = re.sub(r'[\s_-]+', '-', ascii_segment)
    ascii_segment = re.sub(r'-{2,}', '-', ascii_segment).strip('-')
    return ascii_segment or 'page'


def normalize_site_path(raw_path, blockPrimaryFolder=''):
    parsed = urllib.parse.urlsplit(raw_path)
    path = parsed.path or raw_path

    if blockPrimaryFolder:
        primary_prefix = '/' + blockPrimaryFolder.strip('/')
        if path == primary_prefix:
            path = '/'
        elif path.startswith(primary_prefix + '/'):
            path = path[len(primary_prefix):]

    segments = [normalize_path_segment(segment) for segment in path.split('/') if segment]
    if not segments:
        return '/'

    return '/' + '/'.join(segments)


def build_local_page_href(raw_path, relative_prefix, blockPrimaryFolder):
    normalized_path = normalize_site_path('/' + raw_path.lstrip('/'), blockPrimaryFolder)
    if normalized_path == '/':
        return f'{relative_prefix}index.html'

    return f'{relative_prefix}{normalized_path.strip("/")}/index.html'


def resolve_browser_executable():
    mac_chrome_paths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
    ]

    for browser_path in mac_chrome_paths:
        if os.path.exists(browser_path):
            return browser_path

    for browser_name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        browser_path = shutil.which(browser_name)
        if browser_path:
            return browser_path

    if os.name == 'nt':
        windows_paths = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        ]

        for browser_path in windows_paths:
            if os.path.exists(browser_path):
                return browser_path

    return None


def rewrite_local_asset_paths(html, relative_prefix):
    image_prefix = f'{relative_prefix}images/'
    font_prefix = f'{relative_prefix}fonts/'
    root_index = f'{relative_prefix}index.html'

    html = re.sub(r'(?<![A-Za-z0-9_./-])\.\./images/', image_prefix, html)
    html = re.sub(r'(?<![A-Za-z0-9_./-])images/', image_prefix, html)
    html = re.sub(r'(?<![A-Za-z0-9_./-])\.\./fonts/', font_prefix, html)
    html = re.sub(r'(?<![A-Za-z0-9_./-])fonts/', font_prefix, html)
    html = html.replace('href="../index.html"', f'href="{root_index}"')

    return html

async def makeFontsLocal(page, hostname, forceDownloadAgain):
        # Make all fonts local
    # Create a fonts folder if it doesn't exist in hostname folder
    if not os.path.exists(hostname + '/fonts'):
        os.makedirs(hostname + '/fonts')

    # Download all fonts, which are parastorage links
    fontLinks = await page.querySelectorAllEval('style', 'nodes => nodes.map(n => ((n.textContent || "").match(/url\\((.*?)\\)/g) || [])).flat()')

    # Get all url("//static.parastorage.com...") links
    fontLinks = [link for link in fontLinks if link is not None and 'static.parastorage.com' in link]

    for link in fontLinks:
        # Only get if the link is a font
        if('woff' not in link and 'woff2' not in link and 'ttf' not in link and 'eot' not in link and 'otf' not in link and 'svg' not in link):
            continue
        
        # Remove anything before the link
        link = link.split('static.parastorage.com')[1]
        link = 'static.parastorage.com' + link
        # Get the font name
        fontName = link.split('/')[-1].split(')')[0]
        # Remove any ? parameters
        fontName = fontName.split('?')[0]
        # Remove any # parameters
        fontName = fontName.split('#')[0]
        # Remove any "
        fontName = fontName.replace('"', '')
        fontName = fontName.replace("'", '')
        
        # If the font already exists, skip it
        if(not forceDownloadAgain and os.path.exists(hostname + '/fonts/' + fontName)):
            continue
        
        r = requests.get("https://" + link, allow_redirects=True)
        open(hostname + '/fonts/' + fontName, 'wb').write(r.content)

    # Replace all font links with the local font links where the font file name is the last item after the last slash
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('style');
        for (const element of elements) {
            const text = element.textContent || '';
            if (text.includes('static.parastorage.com')) {
                // Get all occurences of url("//static.parastorage.com...") links
                var fontLinks = text.match(/url\\((.*?)\\)/g);

                for (const link of fontLinks) {
                    // Only get if the link is a font
                    // in javascript
                    if(link.includes('woff') || link.includes('woff2') || link.includes('ttf') || link.includes('eot') || link.includes('otf') || link.includes('svg')) {
                            
                        // Get the font name
                        // in javascript, not using split
                        var fontName = link.substring(link.lastIndexOf('/') + 1, link.lastIndexOf(')'));
                        fontName = fontName.replace(/['"]/g, '');

                        // Redo the src link
                        element.textContent = (element.textContent || '').replace(link, 'url("../fonts/' + fontName + '")');
                    }
                }

            }
        }
    }''')

async def fix_page(page, wait, hostname, blockPrimaryFolder, darkWebsite, forceDownloadAgain, metatags, mapData):
    
    # Get the current page
    key = normalize_site_path(page.url, blockPrimaryFolder)

    print("Current page: " + key)
    relative_prefix = build_relative_prefix(key)
    
    await asyncio.sleep(wait)
    await scroll_to_bottom(page)
    await delete_wix(page)
    await fix_gallery(page)
    await fix_googlemap(page, mapData)
    await fix_slideshow(page)

    # Defer all scripts
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('script');
        for (const element of elements) {
            element.setAttribute('defer', '');
        }
    }''')

    # Remove Wix chat, cookie banner, and similar remote widgets that break offline copies.
    await page.evaluate('''() => {
        const selectors = [
            'iframe[title="Wix Chat"]',
            'iframe[aria-label="Wix Chat"]',
            '#pinnedBottomRight',
            '#comp-jha2mdwx-pinned-layer',
            '[data-hook="consent-banner-root"]',
            '.consent-banner-root'
        ];

        for (const selector of selectors) {
            document.querySelectorAll(selector).forEach((element) => element.remove());
        }

        document.querySelectorAll('script').forEach((element) => {
            const src = element.getAttribute('src') || '';
            const content = element.textContent || '';
            if (
                src.includes('chat') ||
                src.includes('firebase') ||
                src.includes('frog.wix.com') ||
                src.includes('engage') ||
                content.includes('firebase') ||
                content.includes('chat-sdk')
            ) {
                element.remove();
            }
        });
    }''')

    # In every font-face, add   font-display: swap; by going into the innertext of styles and replacing @font-face { with @font-face { font-display: swap;
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('style');
        for (const element of elements) {
            const text = element.textContent || '';
            if (text.includes('@font-face')) {
                element.textContent = text.replace('@font-face {', '@font-face { font-display: swap;');
            }
        }
    }''')

    # Remove data-href from every style tag
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('style');
        for (const element of elements) {
            element.removeAttribute('data-href');
            element.removeAttribute('data-url');
        }
    }''')


    # Make all images local
    await makeLocalImages(page, hostname, forceDownloadAgain)

    # Make all fonts local
    await makeFontsLocal(page, hostname, forceDownloadAgain)

    # Meta fixes
    # Delete all meta tags
    await page.evaluate('''() => {
        const elements = document.querySelectorAll('meta');
        for (const element of elements) {
            element.parentNode.removeChild(element);
        }
    }''')


    if(key not in metatags):
        print("Warning: No metatags defined for this page. Using default metatags.")
        key = '/'
       
    title = metatags[key]['title']
    description = metatags[key]['description']
    keywords = metatags[key]['keywords']
    canonical = metatags[key]['canonical']
    image = metatags[key]['image']
    author = metatags[key]['author']

    title_js = json.dumps(title)
    description_js = json.dumps(description)
    keywords_js = json.dumps(keywords)
    canonical_js = json.dumps(canonical)
    image_js = json.dumps(image)
    author_js = json.dumps(author)

    await page.evaluate(f'''() => {{
        const element = document.createElement('title');
        element.textContent = {title_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add meta for title
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'title';
        element.content = {title_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add meta for og:title
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.property = 'og:title';
        element.content = {title_js};
        document.querySelector('head').appendChild(element);
    }}''')

    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'description';
        element.content = {description_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add meta for og:description
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.property = 'og:description';
        element.content = {description_js};
        document.querySelector('head').appendChild(element);
    }}''')

    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'keywords';
        element.content = {keywords_js};
        document.querySelector('head').appendChild(element);
    }}''')

    await page.evaluate(f'''() => {{
        const element = document.createElement('link');
        element.rel = 'canonical';
        element.href = {canonical_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add meta for og:url
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.property = 'og:url';
        element.content = {canonical_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Twitter meta tags
    await page.evaluate('''() => {
        const element = document.createElement('meta');
        element.name = 'twitter:card';
        element.content = 'summary_large_image';
        document.querySelector('head').appendChild(element);
    }''')

    # Add twitter:url
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'twitter:url';
        element.content = {canonical_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add twitter:title
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'twitter:title';
        element.content = {title_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add twitter:description
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'twitter:description';
        element.content = {description_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add twitter:image
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'twitter:image';
        element.content = {image_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add og:image
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.property = 'og:image';
        element.content = {image_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Author meta tag
    await page.evaluate(f'''() => {{
        const element = document.createElement('meta');
        element.name = 'author';
        element.content = {author_js};
        document.querySelector('head').appendChild(element);
    }}''')

    # Add og:type website
    await page.evaluate('''() => {
        const element = document.createElement('meta');
        element.property = 'og:type';
        element.content = 'website';
        document.querySelector('head').appendChild(element);
    }''')

    # Add new meta tags
    await page.evaluate('''() => {
        const element = document.createElement('meta');
        element.name = 'viewport';
        element.content = 'width=device-width, initial-scale=1.0';
        document.querySelector('head').appendChild(element);
    }''')

    await page.evaluate('''() => {
        const element = document.createElement('meta');
        element.name = 'robots';
        element.content = 'index, follow';
        document.querySelector('head').appendChild(element);
    }''')

    await page.evaluate('''() => {
        const element = document.createElement('meta');
        element.name = 'googlebot';
        element.content = 'index, follow';
        document.querySelector('head').appendChild(element);
    }''')


    # <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    await page.evaluate('''() => {
        const element = document.createElement('link');
        element.rel = 'apple-touch-icon';
        element.sizes = '180x180';
        element.href = '/apple-touch-icon.png';
        document.querySelector('head').appendChild(element);
    }''')

    html = await page.evaluate('document.documentElement.outerHTML')

    html = html.replace('<br>', '')
    html = html.replace('</body>', slideFix)
    if(darkWebsite):
        html = html.replace('</head>', lightModeFix)
    # Fix every href to be relative 
    html = html.replace('href="https://' + hostname, 'href="')
    html = html.replace('href="http://' + hostname, 'href="')
    html = html.replace('href="https://www.' + hostname, 'href="')
    html = html.replace('href="http://www.' + hostname, 'href="')
    html = html.replace('href="www.' + hostname, 'href="')
    html = html.replace('href="' + hostname, 'href="')

    # Remove the primaryFolder from any hrefs
    html = html.replace('href="/' + blockPrimaryFolder, 'href="')

    # Any empty hrefs are now root hrefs, replace them with /
    html = html.replace('href=""', 'href="/"')

    # Make hrefs relative so local file browsing works better.
    html = html.replace('href="/"', f'href="{relative_prefix}index.html"')
    html = re.sub(
        r'href="/([^"#?]+?)/?"',
        lambda match: f'href="{build_local_page_href(match.group(1), relative_prefix, blockPrimaryFolder)}"',
        html,
    )
    html = re.sub(r'href="/(images|fonts)/', lambda match: f'href="{relative_prefix}{match.group(1)}/', html)
    html = re.sub(r'src="/(images|fonts)/', lambda match: f'src="{relative_prefix}{match.group(1)}/', html)
    html = rewrite_local_asset_paths(html, relative_prefix)

    # Remove any remaining manifest and favicon references for offline copies.
    html = re.sub(r'<link[^>]+rel="manifest"[^>]*>', '', html)
    html = re.sub(r'<link[^>]+rel="icon"[^>]*favicon[^>]*>', '', html)
    html = html.replace(' allow="clipboard-write;autoplay;camera;microphone;geolocation;vr"', ' allow="clipboard-write;autoplay;camera;microphone;geolocation"')
    html = html.replace(' allowvr="true"', '')

    # Remove browser-sentry script
    html = html.replace('<script src="https://browser.sentry-cdn.com/6.18.2/bundle.min.js" defer></script>', '')
    html = html.replace('//static.parastorage.com', 'https://static.parastorage.com')

    # https://stackoverflow.com/questions/60357083/does-not-use-passive-listeners-to-improve-scrolling-performance-lighthouse-repo
    html = html.replace('<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.4/dist/jquery.min.js" defer=""></script>', 
    '''<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.4/dist/jquery.min.js" defer=""></script><script>window.addEventListener('DOMContentLoaded', function() { jQuery.event.special.touchstart = { setup: function( _, ns, handle ) { this.addEventListener("touchstart", handle, { passive: !ns.includes("noPreventDefault") }); } }; jQuery.event.special.touchmove = { setup: function( _, ns, handle ) { this.addEventListener("touchmove", handle, { passive: !ns.includes("noPreventDefault") }); } }; jQuery.event.special.wheel = { setup: function( _, ns, handle ){ this.addEventListener("wheel", handle, { passive: true }); } }; jQuery.event.special.mousewheel = { setup: function( _, ns, handle ){ this.addEventListener("mousewheel", handle, { passive: true }); } }; });</script>''')

    # Add doctype HTML to start 
    html = '<!DOCTYPE html>' + html

    return html


# Define the main function
async def main():
    
    """ Variable Declarations """
    # Load the data in from the json file
    with open('config.json') as f:
        data = json.load(f)

    site = data['site']
    blockPrimaryFolder = data['blockPrimaryFolder']
    wait = data['wait']
    recursive = data['recursive'].lower() == 'true'
    darkWebsite = data['darkWebsite'].lower() == 'true'
    forceDownloadAgain = data['forceDownloadAgain'].lower() == 'true'
    metatags = data['metatags']
    mapData = data['mapData']

    # Get the hostname
    hostname = urlparse(site).hostname

    # Prefer Chrome on macOS, but fall back to any installed Chromium-based browser.
    browser_executable = resolve_browser_executable()
    launch_kwargs = dict(headless=False, defaultViewport=None, args=['--window-size=1920,1080'])
    if browser_executable:
        launch_kwargs['executablePath'] = browser_executable

    browser = await launch(**launch_kwargs)
    
    page = await browser.newPage()
    await page.goto(site)
    
    print(site)

    # Fix the first page
    html = await fix_page(page, wait, hostname, blockPrimaryFolder, darkWebsite, forceDownloadAgain,metatags, mapData)

    if not os.path.exists(hostname):
        os.mkdir(hostname)

    with open(hostname + '/index.html', 'w', encoding="utf-8") as f:
        f.write(html)

    if(recursive): 
        seen = []
        # Recursively go through all the local links and save them to the directory
        async def save_links(page, links):
            # Delete all links that are not local
            links = [link for link in links if hostname in link]
            # Delete all links with hash
            links = [link for link in links if '#' not in link]
            links = set(links)
            #print(links)
            errors = {}
            for link in links:
                print(link)
                local_page_path = normalize_site_path(link, blockPrimaryFolder)
                if local_page_path in seen:
                    continue

                try:

                    await page.goto(link)
                    
                    seen.append(local_page_path)

                    html = await fix_page(page, wait, hostname, blockPrimaryFolder, darkWebsite, forceDownloadAgain,metatags, mapData)

                    if local_page_path == '/':
                        with open(hostname + '/index.html', 'w', encoding="utf-8") as f:
                            f.write(html)
                    else:
                        destination_dir = os.path.join(hostname, local_page_path.strip('/'))
                        os.makedirs(destination_dir, exist_ok=True)
                        with open(os.path.join(destination_dir, 'index.html'), 'w', encoding="utf-8") as f:
                            f.write(html)
                
                    await save_links(page, await page.querySelectorAllEval('a', 'nodes => nodes.map(n => n.href)'))

                except Exception as e:
                    
                    # Check the error count, if over 3, add link to the seen list (ignore)
                    if(link in errors):
                        errors[link] += 1
                    else:
                        errors[link] = 1

                    if(errors[link] > 3):
                        seen.append(local_page_path)
                        print("Error: " + link + ". Giving up after 3 attempts. Added to seen list.")
                        continue

                    print(e)
                    print("Error: " + link + ". Try " + str(errors[link]) + " of 3")

                    continue

        await save_links(page, await page.querySelectorAllEval('a', 'nodes => nodes.map(n => n.href)'))
        
    #await browser.close()

asyncio.run(main())

