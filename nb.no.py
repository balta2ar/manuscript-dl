#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import re
import time
from collections import namedtuple
from io import BytesIO
from json import dumps, loads
from multiprocessing.pool import ThreadPool
from os import makedirs
from os.path import dirname, exists, join, isfile
from shutil import which
from tempfile import gettempdir
from textwrap import dedent
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from diskcache import Cache
from PIL import Image
from plumbum import FG, local

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
logging.basicConfig(format=FORMAT, level=logging.DEBUG)

bash = local["bash"]
cache = Cache(join(gettempdir(), "manuscript-dl", "nb.no"))


def must_bin(name):
    where = which(name)
    if not where:
        raise Exception("Missing {}".format(name))
    return where


@cache.memoize()
def http_get_sync(url, headers=None):
    req = Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "*/*")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    max_retries = 3
    for retry in range(max_retries):
        try:
            logging.info(
                "sync HTTP GET %s (attempt %d/%d)", url, retry + 1, max_retries
            )
            with urlopen(req) as resp:
                return resp.read()
        except Exception as e:
            logging.error("ERROR HTTP GET %s %s", url, e)
            if retry == max_retries - 1:  # If this was the last retry
                return None
            sleep_time = retry + 1  # Increasing timeout: 1, 2, ..., 10s
            logging.info("Retrying in %d seconds...", sleep_time)
            time.sleep(3 * sleep_time)

    return None  # This should never be reached, but added for clarity


def send_consent(id, headers=None):
    """Send legal deposit reservation/consent for a book before downloading.
    Must be called before accessing the book content. Safe to call multiple times."""
    url = "https://api.nb.no/catalog/v1/legaldeposit/reservation/{}".format(id)
    req = Request(url, method="PUT", data=b"")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Content-Length", "0")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        logging.info("sending consent PUT %s", url)
        with urlopen(req) as resp:
            body = resp.read()
            logging.info("consent response: %s %s", resp.status, body)
            return body
    except HTTPError as e:
        logging.warning("consent request failed: %s (may already be consented)", e)
        return None


def suffix(s, suffix):
    if s.endswith(suffix):
        return s
    return s + suffix


def get_manifest(id, downloader):
    # https://api.nb.no/catalog/v1/iiif/URN:NBN:no-nb_digibok_2008091504048/manifest?profile=nbdigital
    url = "https://api.nb.no/catalog/v1/iiif/{}/manifest?profile=nbdigital".format(id)
    data = downloader(url)
    return loads(data)


Shape = namedtuple("Shape", ["width", "height"])
Tile = namedtuple("Tile", ["width", "scale"])
Page = namedtuple("Page", ["id", "url", "index", "shape", "tile"])


def ensure_dir(filename):
    dir = dirname(filename)
    if not exists(dir):
        makedirs(dir)
    return filename


def spit(data, filename):
    with open(ensure_dir(filename), "w") as f:
        f.write(data)


def slurp(filename):
    with open(filename, "r") as f:
        return f.read().strip()


def fs_friendly(path):
    # return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', path)
    return path.replace("/", "_").replace(":", "_")


class Book:
    #  https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2008091504048_0025/0,0,1024,1024/1024,/0/default.jpg
    def __init__(self, id: str, downloader):
        self.downloader = downloader
        self.id = id
        self.manifest = get_manifest(id, downloader)
        self.label = fs_friendly(self.manifest["label"])
        self.dir = join("nb.no", fs_friendly(id) + "-" + self.label)

    def get_page(self, page: Page):
        filename = join(self.dir, "{:04d}_{}.png".format(page.index, page.id))
        if exists(filename):
            return
        cx, cy = 0, 0
        img = Image.new("RGB", (page.shape.width, page.shape.height))
        while cy < page.shape.height:
            # tw, th = page.tile.width, page.tile.height
            while cx < page.shape.width:
                tile_url = page.url + "/{},{},{},{}/{},/0/default.jpg".format(
                    cx, cy, page.tile.width, page.tile.height, page.tile.width
                )
                data = self.downloader(tile_url)
                if data is not None:
                    tile = Image.open(BytesIO(data))
                    # tw, th = tile.size
                    # print('TILE size', tile.size)
                    img.paste(tile, (cx, cy))
                cx += page.tile.width
                # cx += tw
            cx = 0
            cy += page.tile.height
            # cy += th
        img.save(ensure_dir(filename))
        logging.info("saved %s", filename)

    def download(self):
        spit(dumps(self.manifest, indent=4), join(self.dir, "manifest.json"))

        tasks = []
        index = 0
        for sequence in self.manifest["sequences"]:
            for canvas in sequence["canvases"]:
                for image in canvas["images"]:
                    service = image["resource"]["service"]
                    url = service["@id"]
                    id = url.split("_")[-1]
                    # size = max(service['sizes'], key=lambda x: x['width'])
                    # tile_shape = Shape(size['width'], size['height'])
                    # tile_shape = Shape(2048, 2048)
                    tile_shape = Shape(1024, 1024)
                    # tile_shape = Shape(512, 512)
                    page_shape = Shape(service["width"], service["height"])
                    page = Page(id, url, index, page_shape, tile_shape)
                    # self.get_page(page)
                    tasks.append(page)
                    index += 1

        with ThreadPool(1) as pool:
            for _ in pool.imap(self.get_page, tasks):
                pass

    def convert(self, filename):
        must_bin("bash")
        must_bin("convert")
        must_bin("pdftk")
        must_bin("ocrmypdf")
        must_bin("parallel")
        filename = suffix(filename or self.label, ".pdf")
        # cmd = 'convert -density 300 -quality 100 {}/????_*.png {}'.format(self.dir, filename)
        script = f"""
        #!/bin/bash
        set -e
        set -x
        mkdir -p pdf
        mkdir -p out
        #parallel --bar convert "{{}}" "pdf/{{.}}.pdf" ::: *.png
        #parallel --jobs 1 --bar convert -resize "50%" "{{}}" "pdf/{{.}}.pdf" ::: *.png
        parallel --jobs 12 --bar gm convert -resize "50%" "{{}}" "pdf/{{.}}.pdf" ::: *.png
        pdftk pdf/*.pdf cat output out/out.pdf
        env TMPDIR=/mnt/payload/tmp ocrmypdf -l nor --jobs 12 --output-type pdfa out/out.pdf "../../{filename}"
"""
        script = dedent(script).strip()
        spit(script, join(self.dir, "convert.sh"))
        with local.cwd(self.dir):
            bash["./convert.sh"] & FG

        # print(f'cd "{self.dir}"')
        # print('parallel --bar convert "{}" "{.}.pdf" ::: *.png')
        # # print('pdfunite *.pdf out.pdf')
        # print('pdftk *.pdf cat output out.pdf')
        # #print('convert -density 300 -quality 100 *.png out.pdf')
        # print(f'ocrmypdf -l nor --jobs 12 --output-type pdfa out.pdf "{filename}"')


def main():
    must_bin('bash')
    must_bin('convert')
    must_bin('pdftk')
    must_bin('ocrmypdf')
    must_bin('parallel')
    must_bin('gm')

    # python ./nb.no.py -H 'header: value' URN:NBN:no-nb_digibok_2008091504048
    parser = argparse.ArgumentParser("Download books from nb.no")
    parser.add_argument("id", help="Book ID")
    parser.add_argument("filename", nargs="?", default=None, help="Output filename")
    parser.add_argument("-H", "--header", help="HTTP header", action="append")
    args = parser.parse_args()
    print(args)

    def parse_headers():
        headers = {}
        for h in args.header:
            if isfile(h):
                h = slurp(h)
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
        return headers

    def downloader(url):
        return http_get_sync(url, parse_headers())

    send_consent(args.id, parse_headers())

    book = Book(args.id, downloader)
    book.download()
    book.convert(args.filename)


if __name__ == "__main__":
    main()
