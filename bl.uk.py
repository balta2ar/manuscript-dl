#!/bin/python2

# Download DaVinci's Notebook from http://www.bl.uk/manuscripts/FullDisplay.aspx?ref=Arundel_MS_263
#
# Format is:
# http://www.bl.uk/manuscripts/Proxy.ashx?view=arundel_ms_263_<page_number>_files/<resolution_level>/<column>_<row>.jpg
#
# Pages work in this fashion: f001r, f001v, f002r, f002v, f003r, f003v, ... and ends at f283v.
# At resolution 14, columns range from 0 to 33 and rows range from 0 to 24.
#
# First download this page to obtain all the pages:
# http://www.bl.uk/manuscripts/Viewer.aspx?ref=add_ms_24686
#
# In HTML you will see:
# <input type="hidden" name="PageList" id="PageList" value="##||add_ms_24686_fs001r||add_ms_24686_fs001v

# Contatenate blocks into rows:
# montage -mode concatenate -tile x1 `ls -1cr add_ms_24686_f044r_5_*` row_0.jpg
#
# for row in `seq 0 32`; do montage -mode concatenate -tile x1 `ls -1cr add_ms_24686_f044r_${row}_*` row_${row}.jpg; done
#
# Contatenate rows into page:
# montage -mode concatenate -tile 1x `ls -1cr row_*` add_ms_24686_f044r.jpg

from __future__ import print_function

import os
import re
import sys
import time
import glob
import urllib
import shutil
import imghdr
import argparse
import random

from os.path import join as J
from subprocess import call

import requests
from bs4 import BeautifulSoup


# col 22
# row 32

URL_PAGES = "http://www.bl.uk/manuscripts/Viewer.aspx?ref={manuscript}"
URL_IMAGE_BLOCK = "http://www.bl.uk/manuscripts/Proxy.ashx?view={manuscript_and_page}_files/{resolution}/{column}_{row}.jpg"
INVALID_BLOCK_MAGIC_SUBSTRING = b'Parameter is not valid'
MAX_BLOCK_DOWNLOAD_RETRIES = 6


def download(save_folder):

    # Values at resolution 14
    res = 14
    rows = 24
    cols = 33

    # Page number to start downloading from (1 is smallest)
    cur_page = 1
    # Page number to finish downloading on (283 is largest)
    end_page = 283

    # Variable that we will flip at end of loop to alternamte between r's and v's
    ending = True

    # Start the download loop ...
    while (cur_page <= end_page):
        print("Starting download...")

        page = "f%s" % (str(cur_page).zfill(3))

        if ending:
            page += "r"
            ending = False
        else:
            page += "v"
            ending = True
            cur_page += 1

    for r in range(rows):
        for c in range(cols):
            try:
                print("Saving arundel_ms_263_%s_files/%d/%d_%d.jpg" % (page, res, c, r))
                urllib.urlretrieve(
                    "http://www.bl.uk/manuscripts/Proxy.ashx?view=arundel_ms_263_%s_files/%d/%d_%d.jpg" % (page, res, c, r),
                    save_folder + "%s-%d-%d-%d.jpg" % (page, res, r, c) # Note: row and column are reversed. This made more sense to me.
                )
            except KeyboardInterrupt:
                print("Exiting...")
                return

    print("Download finished!")


def mkpath(path):
    '''
    Make dir if it does not yet exist.
    '''
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError:
            pass


def put(string):
    sys.stdout.write(string)
    sys.stdout.flush()


def get_pages(manuscript):
    '''
    Download manuscript page and extract the number of pages it contains.
    '''
    reply = requests.get(URL_PAGES.format(manuscript=manuscript))
    soup = BeautifulSoup(reply.text, 'html.parser')
    str_pages = soup.find('input', {'id': 'PageList'}).attrs['value']
    pages = str_pages.replace('##', '').split('||')
    pages = list(filter(None, pages))
    return pages


def is_valid_block(current_block, nil_block):
    '''
    Perform two tests to see whether this block is valid. They are not 100%
    reliable, I believe.
    '''
    if INVALID_BLOCK_MAGIC_SUBSTRING in current_block.content:
        return False

    if len(current_block.content) <= len(nil_block.content):
        return False

    return True


def is_valid_image(filename):
    '''
    Valid image is an image that can be parsed as a JPEG file.
    '''
    if not os.path.exists(filename):
        return False

    return imghdr.what(filename) == 'jpeg'


class BlockResult(Exception):
    pass

class BlockAlreadyDownloaded(BlockResult):
    pass

class BlockInvalid(BlockResult):
    pass

class BlockMaxRetriesReached(BlockResult):
    pass


def download_block(url, filename, nil_block):
    '''
    Download single page block (rectangular). This method will retry up to
    MAX_BLOCK_DOWNLOAD_RETRIES times if downloaded image is not JPEG.
    Delays between retries are choosen according to the binary exponential
    backoff strategy.
    '''
    for i in range(MAX_BLOCK_DOWNLOAD_RETRIES):
        # Do not download twice
        if is_valid_image(filename):
            raise BlockAlreadyDownloaded()

        block = requests.get(url)
        if not is_valid_block(block, nil_block):
            raise BlockInvalid()

        # Note that I save in row-column order
        with open(filename, 'wb') as output_file:
            output_file.write(block.content)

        # Retry if not a valid image
        if not is_valid_image(filename):
            # Skip sleeping if this is the last attempt
            if i != MAX_BLOCK_DOWNLOAD_RETRIES - 1:
                sleep_duration = random.randint(1, 2**i)
                # print('Failed to download block %s, will sleep for %s and retry' % \
                #       (url, sleep_duration))
                time.sleep(sleep_duration)
            continue

        return None

    # print('Failed to download page block %s after %s retries' % \
    #       (url, MAX_BLOCK_DOWNLOAD_RETRIES))
    raise BlockMaxRetriesReached()


def download_page(resolution, base_dir, manuscript, page):
    '''
    Download single page into base_dir/manuscript/page directory.
    There will be a bunch of block files that you will need to contatenate
    later.
    '''
    mkpath(J(base_dir, manuscript, page))

    # First download image block that is out of range to see how such image
    # looks like (this is used to detect edges later)
    nil_block = requests.get(URL_IMAGE_BLOCK.format(manuscript_and_page=page,
                                                    resolution=resolution,
                                                    column=999, row=999))

    column, row = 0, 0
    max_column, max_row = 0, 0

    while True:
        filename = J(base_dir, manuscript, page,
                     '{0}_{1}_{2}.jpg'.format(page, row, column))

        #print('Getting block {0}x{1}'.format(row, column))
        url = URL_IMAGE_BLOCK.format(manuscript_and_page=page,
                                     resolution=resolution,
                                     column=column, row=row)

        try:
            download_block(url, filename, nil_block)
        except BlockAlreadyDownloaded:
            max_row = max(row, max_row)
            max_column = max(column, max_column)
            column += 1
            put('.')
            continue
        except BlockInvalid:
            put('\n')
            # We are out of range
            if column == 0:
                # The end of the page
                print('End of the page')
                print('Page {0} has size row x column = {1} x {2}'.format(
                    page, max_row, max_column))
                break
            else:
                # The end of the row, reset column, increment row
                column = 0
                row += 1
                continue
        except BlockMaxRetriesReached:
            put('X')
        else:
            put('.')

        # Update page size
        max_row = max(row, max_row)
        max_column = max(column, max_column)

        # Go to next column
        column += 1

    return max_column, max_row


def atoi(text):
    return int(text) if text.isdigit() else text


def natural_keys(text):
    '''
    Taken from:
    http://stackoverflow.com/a/5967539/258421

    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [atoi(c) for c in re.split('(\d+)', text)]


def concatenate_page(base_dir, manuscript, page, columns, rows):
    '''
    Concatenate image blocks into a single page (still jpg).
    '''
    # How concat blocks into row looks in shell:
    # montage -mode concatenate -tile x1 `ls -1cr add_ms_24686_f044r_5_*` row_0.jpg
    for row in range(rows + 1):
        row_filename = J(base_dir, manuscript, page, 'row_{0}.jpg'.format(row))
        if os.path.exists(row_filename):
            continue

        glob_name = '{0}_{1}_*.jpg'.format(
            J(base_dir, manuscript, page, page), row)
        row_blocks = sorted(glob.glob(glob_name), key=natural_keys)
        cmd = ('montage -mode concatenate -tile x1'.split() +
               row_blocks + [row_filename])
        call(cmd)
        put('.')

    # How concat rows into page looks in shell:
    # montage -mode concatenate -tile 1x `ls -1cr row_*` add_ms_24686_f044r.jpg
    page_filename = J(base_dir, manuscript, page) + '.jpg'
    if os.path.exists(page_filename):
        return

    glob_name = '{0}_*.jpg'.format(J(base_dir, manuscript, page, 'row'))
    rows = sorted(glob.glob(glob_name), key=natural_keys)
    cmd = ('montage -mode concatenate -tile 1x'.split() +
           rows + [page_filename])
    call(cmd)
    put('\n')


def convert_pages(base_dir, manuscript, pages):
    '''
    Convert manuscript images into PDFs and join into single PDF.
    '''
    for i, page in enumerate(pages):
        input_name = J(base_dir, manuscript, '{0}.jpg'.format(page))
        output_name = J(base_dir, manuscript, '{0}.pdf'.format(page))
        if os.path.exists(output_name):
            continue
        print('Converting page {0} ({1}/{2})'.format(page, i + 1, len(pages)))
        cmd = ['convert', input_name, output_name]
        call(cmd)


def fold_pages(base_dir, manuscript, pages, output_name):
    '''
    Fold pdf pages into one by applying concat operation to a pair of docs.
    '''
    tmp_name = J(base_dir, manuscript + '.pdf.tmp')
    pdfs = ['{0}.pdf'.format(page) for page in pages]
    for i, pdf in enumerate(pdfs):
        print('Folding page {0} ({1}/{2})'.format(pdf, i + 1, len(pages)))
        pdf_name = J(base_dir, manuscript, pdf)
        if os.path.exists(output_name):
            cmd = ['pdftk', output_name, pdf_name, 'cat', 'output', tmp_name]
            call(cmd)
            os.unlink(output_name)
            os.rename(tmp_name, output_name)
        else:
            shutil.copy2(pdf_name, output_name)


def download_pages(resolution, base_dir, manuscript, pages):
    '''
    Download all pages of the manuscript.
    '''
    # Download pages
    for i, page in enumerate(pages):
        print('Downloading page {0} ({1}/{2})'.format(page, i + 1, len(pages)))
        columns, rows = download_page(resolution, base_dir, manuscript, page)

        print('Concatenating page {0} ({1}/{2})'.format(page, i + 1, len(pages)))
        concatenate_page(base_dir, manuscript, page, columns, rows)


def convert_manuscript(resolution, base_dir, manuscript, pages):
    '''
    Convert manuscript and fold its pages into a single PDF.
    '''
    convert_pages(base_dir, manuscript, pages)
    suffix = '-p{0}-r{1}.pdf'.format(len(pages), resolution)
    output_name = J(base_dir, manuscript + suffix)
    fold_pages(base_dir, manuscript, pages, output_name)


def subset_pages(pages, pages_range):
    a, b = pages_range.split(':')
    a = int(a) if a else 0
    b = int(b) + 1 if b else len(pages) + 1
    return pages[a:b]


def download_manuscript(pages_range, resolution, base_dir, manuscript):
    '''
    Download whole manuscript. The result is a pdf file.
    '''
    print('Downloading manuscript {0} resolution {1}'
          .format(manuscript, resolution))

    # Get list of pages
    pages = get_pages(manuscript)
    print('{0} pages found'.format(len(pages)))
    pages = subset_pages(pages, pages_range)
    print('{0} pages downloading (range {1})'.format(len(pages), pages_range))

    # Download all pages
    download_pages(resolution, base_dir, manuscript, pages)

    # Convert pages from jpg to pdf and join into single pdf
    print('Converting manuscript {0} into PDF'.format(manuscript))
    convert_manuscript(resolution, base_dir, manuscript, pages)


def main(args):
    for name in args.names:
        download_manuscript(args.pages,
                            args.resolution,
                            J(args.base_dir, str(args.resolution)),
                            name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='British Library manuscript downloader')
    parser.add_argument('names', type=str, nargs='+',
                        help='Names of the manuscript to download')
    parser.add_argument('--base-dir', type=str, default='pics',
                        help='Base directory')
    parser.add_argument('--resolution', type=int, default=12,
                        help='Resolution level (zoom, 14 is the highest)')
    parser.add_argument('--pages', type=str, default=':',
                        help='Range of pages to download (both ends including)')
    args = parser.parse_args()
    sys.exit(main(args))
