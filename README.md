# manuscript-dl
Collection of scripts to download digitized manuscripts from different online libraries.

Some online libraries provide convenient way to download complete manuscript as a PDF file. Some don't. Mad scripting skills to the resque!

### Supported libraries

#### [e-codices - Virtual Manuscript Library of Switzerland](http://www.e-codices.unifr.ch/en)

To download a book:

1. Go to book description page, e.g.: http://www.e-codices.unifr.ch/en/list/one/csg/0369
2. Right click on the link "IIIF Manifest URL" and save it to file, e.g. manifest.json
3. Run

``` bash
$ e-codices.sh manifest.json [size]
```

`size` is an optional argument. Original size of manuscripts on e-codices is usually way too big and needs to be reduced.

#### [British Library Digitised Manuscripts](http://www.bl.uk/manuscripts/)

This downloader uses `pdftk` program to convert images to PDFs and concatenate
them together. You need to have `pdftk` installed in your system.

Ubuntu:

``` bash
sudo apt-get install pdftk
```

To download a book you need to find out its short name:

1. Open manuscript description, e.g.: http://www.bl.uk/manuscripts/FullDisplay.aspx?ref=Add_MS_24686
2. In this case the name is "add_ms_24686" (notice lower case). But you can double check if you click any of the pictures below and open a new page: http://www.bl.uk/manuscripts/Viewer.aspx?ref=add_ms_24686_f002r
3. Here, `add_ms_24686_f002r` is a manuscript name + page name. You only need manuscript name.
4. Run the `bl.uk.py` with manuscript name:

``` bash
$ python2 bl.uk.py add_ms_24686 --resolution 12
```

This will grab all available pages with resolution 12. If you want specific pages, you can set page range using `--pages A:B` argument.

### Author

(c) 2015 Yuri Bochkarev
