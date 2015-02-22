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

In development.

### Author

(c) 2015 Yuri Bochkarev
