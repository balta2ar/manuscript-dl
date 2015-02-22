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

import sys
import urllib
import argparse

import requests
from bs4 import BeautifulSoup

# col 22
# row 32


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
        print "Starting download..."

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
                print "Saving arundel_ms_263_%s_files/%d/%d_%d.jpg" % (page, res, c, r)
                urllib.urlretrieve(
                    "http://www.bl.uk/manuscripts/Proxy.ashx?view=arundel_ms_263_%s_files/%d/%d_%d.jpg" % (page, res, c, r),
                    save_folder + "%s-%d-%d-%d.jpg" % (page, res, r, c) # Note: row and column are reversed. This made more sense to me.
                )
            except KeyboardInterrupt:
                print "Exiting..."
                return

    print "Download finished!"


def main(args):
    print(args.names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='British Library manuscript downloader')
    parser.add_argument('names', type=str, nargs='+',
                        help='Names of the manuscript to download')
    args = parser.parse_args()
    sys.exit(main(args))

    # Check if a save folder was specified in arguments
    if len(sys.argv) > 1:
        download(sys.argv[1])

    # Otherwise save to the current directory
    else:
        download("")
