# manuscript-dl
Collection of scripts to download digitized manuscripts from different online libraries.

Some online libraries provide convenient way to download complete manuscript as a PDF file. Some don't. Mad scripting skills to the resque!

### Supported libraries

#### [Nasjonalbiblioteket](https://www.nb.no/)

To download a book:

1. Find out its ID, e.g.: https://www.nb.no/items/URN:NBN:no-nb_digibok_2008091504048?page=1
2. (optional) Copy curl command from the browser, so that you preserve cookies, and adjust it.
3. Run:
```bash
$ python ./nb.no.py -H 'cookie: something' URN:NBN:no-nb_digibok_2008091504048
```

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

This downloader uses `montage` (`imagemagick` suite) program to convert images
to PDFs and `pdftk` to concatenate PDFs together. You need to have `pdftk` and
`montage` installed in your system.

Ubuntu:

``` bash
sudo apt-get install pdftk imagemagick
```

To download a book you need to find out its short name:

1. Open manuscript description, e.g.: http://www.bl.uk/manuscripts/FullDisplay.aspx?ref=Add_MS_24686
2. In this case the name is "add_ms_24686" (notice lower case). But you can double check if you click any of the pictures below and open a new page: http://www.bl.uk/manuscripts/Viewer.aspx?ref=add_ms_24686_f002r
3. Here, `add_ms_24686_f002r` is a manuscript name + page name. You only need manuscript name.
4. Run the `bl.uk.py` with manuscript name:

``` bash
$ python3 bl.uk.py add_ms_24686 --resolution 12
```

This will grab all available pages with resolution 12. If you want specific pages, you can set page range using `--pages A:B` argument.

At some point the Library started replying with HTTP 429 (Too Many Requests).
Faking user agent helped. If default user agent is not working for you, you can
replace it using `--user-agent` option like this:

``` bash
python3 bl.uk.py add_ms_24686 --user-agent 'Mozilla/5.0 (X11; OpenBSD i386) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36'
```

### Author

(c) 2015-2018 Yuri Bochkarev
