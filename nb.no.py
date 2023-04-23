#!/usr/bin/env python

from os import makedirs
from io import BytesIO
import argparse
from json import loads
from collections import namedtuple
from os.path import join, exists, dirname
from tempfile import gettempdir

import logging
import logging.handlers

from urllib.request import urlopen, Request
from PIL import Image
from diskcache import Cache

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)

cache = Cache(join(gettempdir(), 'manuscript-dl', 'nb.no'))

@cache.memoize()
def http_get_sync(url):
    req = Request(url)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', '*/*')
    logging.info('sync HTTP GET %s', url)
    with urlopen(req) as resp:
        return resp.read()

def get_manifest(id):
    # https://api.nb.no/catalog/v1/iiif/URN:NBN:no-nb_digibok_2008091504048/manifest?profile=nbdigital
    url = 'https://api.nb.no/catalog/v1/iiif/{}/manifest?profile=nbdigital'.format(id)
    data = http_get_sync(url)
    return loads(data)

Shape = namedtuple('Shape', ['width', 'height'])
Page = namedtuple('Page', ['id', 'url', 'index', 'shape'])

def ensure_dir(filename):
    dir = dirname(filename)
    if not exists(dir):
        makedirs(dir)
    return filename

class Book:
    #  https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2008091504048_0025/0,0,1024,1024/1024,/0/default.jpg
    def __init__(self, id):
        self.id = id
        self.dir = join('nb.no', id.replace(':', '_'))

    def get_page(self, page, tile):
        filename = join(self.dir, '{:04d}_{}.png'.format(page.index, page.id))
        if exists(filename): return
        cx, cy = 0, 0
        img = Image.new('RGB', (page.shape.width, page.shape.height))
        while cy < page.shape.height:
            while cx < page.shape.width:
                tile_url = page.url + '/{},{},{},{}/{},/0/default.jpg'.format(cx, cy, tile.width, tile.height, tile.width)
                data = http_get_sync(tile_url)
                img.paste(Image.open(BytesIO(data)), (cx, cy))
                cx += tile.width
            cx = 0
            cy += tile.height
        img.save(ensure_dir(filename))

    def download(self):
        manifest = get_manifest(self.id)

        index = 0
        for sequence in manifest['sequences']:
            for canvas in sequence['canvases']:
                for image in canvas['images']:
                    service = image['resource']['service']
                    url = service['@id']
                    id = url.split('_')[-1]
                    # size = max(service['sizes'], key=lambda x: x['width'])
                    # tile = Block(size['width'], size['height'])
                    tile_shape = Shape(1024, 1024)
                    page_shape = Shape(service['width'], service['height'])
                    page = Page(id, url, index, page_shape)
                    self.get_page(page, tile_shape)
                    index += 1
        filename = manifest['label'] + '.pdf'
        #cmd = 'convert -density 300 -quality 100 {}/????_*.png {}'.format(self.dir, filename)
        print(f'convert -density 300 -quality 100 {self.dir}/*.png out.pdf')
        print(f'ocrmypdf -l nor --jobs 12 --output-type pdfa "{filename}" out.pdf')
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser('Download books from nb.no')
    parser.add_argument('id', help='Book ID')
    args = parser.parse_args()

    book = Book(args.id)
    book.download()