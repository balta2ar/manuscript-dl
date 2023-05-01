#!/usr/bin/env python

import re
import argparse
import logging
import logging.handlers
from collections import namedtuple
from io import BytesIO
from json import dumps, loads
from multiprocessing.pool import ThreadPool
from os import makedirs
from os.path import dirname, exists, join
from shutil import which
from tempfile import gettempdir
from textwrap import dedent
from urllib.request import Request, urlopen

from diskcache import Cache
from PIL import Image
from plumbum import local, FG

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)

bash = local['bash']
cache = Cache(join(gettempdir(), 'manuscript-dl', 'nb.no'))

def must_bin(name):
    where = which(name)
    if not where:
        raise Exception('Missing {}'.format(name))
    return where

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
Page = namedtuple('Page', ['id', 'url', 'index', 'shape', 'tile'])

def ensure_dir(filename):
    dir = dirname(filename)
    if not exists(dir):
        makedirs(dir)
    return filename

def spit(data, filename):
    with open(ensure_dir(filename), 'w') as f:
        f.write(data)

def fs_friendly(path):
    # return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', path)
    return path.replace('/', '_').replace(':', '_')

class Book:
    #  https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2008091504048_0025/0,0,1024,1024/1024,/0/default.jpg
    def __init__(self, id: str):
        self.id = id
        self.manifest = get_manifest(id)
        self.label = fs_friendly(self.manifest['label'])
        self.dir = join('nb.no', fs_friendly(id) + '-' + self.label)

    def get_page(self, page: Page):
        filename = join(self.dir, '{:04d}_{}.png'.format(page.index, page.id))
        if exists(filename): return
        cx, cy = 0, 0
        img = Image.new('RGB', (page.shape.width, page.shape.height))
        while cy < page.shape.height:
            while cx < page.shape.width:
                tile_url = page.url + '/{},{},{},{}/{},/0/default.jpg'.format(
                    cx, cy, page.tile.width, page.tile.height, page.tile.width)
                data = http_get_sync(tile_url)
                img.paste(Image.open(BytesIO(data)), (cx, cy))
                cx += page.tile.width
            cx = 0
            cy += page.tile.height
        img.save(ensure_dir(filename))
        logging.info('saved %s', filename)

    def download(self):
        spit(dumps(self.manifest, indent=4), join(self.dir, 'manifest.json'))

        tasks = []
        index = 0
        for sequence in self.manifest['sequences']:
            for canvas in sequence['canvases']:
                for image in canvas['images']:
                    service = image['resource']['service']
                    url = service['@id']
                    id = url.split('_')[-1]
                    # size = max(service['sizes'], key=lambda x: x['width'])
                    # tile = Block(size['width'], size['height'])
                    tile_shape = Shape(1024, 1024)
                    page_shape = Shape(service['width'], service['height'])
                    page = Page(id, url, index, page_shape, tile_shape)
                    # self.get_page(page)
                    tasks.append(page)
                    index += 1

        with ThreadPool(5) as pool:
            for _ in pool.imap(self.get_page, tasks): pass
    
    def convert(self):
        must_bin('bash')
        must_bin('convert')
        must_bin('pdftk')
        must_bin('ocrmypdf')
        must_bin('parallel')

        filename = self.label + '.pdf'
        #cmd = 'convert -density 300 -quality 100 {}/????_*.png {}'.format(self.dir, filename)
        script = f'''
        #!/bin/bash
        set -e
        set -x
        mkdir -p pdf
        mkdir -p out
        #parallel --bar convert "{{}}" "pdf/{{.}}.pdf" ::: *.png
        parallel --bar convert -resize "50%" "{{}}" "pdf/{{.}}.pdf" ::: *.png
        pdftk pdf/*.pdf cat output out/out.pdf
        ocrmypdf -l nor --jobs 12 --output-type pdfa out/out.pdf "../../{filename}"
'''
        script = dedent(script).strip()
        spit(script, join(self.dir, 'convert.sh'))
        with local.cwd(self.dir):
            bash['./convert.sh'] & FG
        
        # print(f'cd "{self.dir}"')
        # print('parallel --bar convert "{}" "{.}.pdf" ::: *.png')
        # # print('pdfunite *.pdf out.pdf')
        # print('pdftk *.pdf cat output out.pdf')
        # #print('convert -density 300 -quality 100 *.png out.pdf')
        # print(f'ocrmypdf -l nor --jobs 12 --output-type pdfa out.pdf "{filename}"')
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser('Download books from nb.no')
    parser.add_argument('id', help='Book ID')
    args = parser.parse_args()

    book = Book(args.id)
    book.download()
    book.convert()