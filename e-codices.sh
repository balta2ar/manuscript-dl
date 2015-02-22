#!/bin/bash

#
# This script downloads manuscripts from http://www.e-codices.unifr.ch/en
#
# Arguments:
# $1 - path to json description file
# $2 - size, in percents of original (the original is usually way too big, 50%
# is a good start, maybe even 25)
#
# To download a book:
# 1. Go to book description page: http://www.e-codices.unifr.ch/en/list/one/csg/0369
# 2. Right click on the link "IIIF Manifest URL" and save it to file
# 3. Run $ e-codices.sh path-to-manifest.json
#
# Format:
# http://sr-svx-93.unifr.ch/loris/kba/kba-BN0049/kba-BN0049_009v.jp2/full/full/0/default.jpg
# http://sr-svx-93.unifr.ch/loris/kba/kba-BN0049/kba-BN0049_009v.jp2/full/pct:50/0/default.jpg

IN=$1
[ -z "$2" ] && SIZE="full" || SIZE="pct:$2"
LABEL=$(jq '.label' "$IN" | sed s/\"//g)
echo $LABEL

# Prepare links
LINKS=links.txt
jq '.sequences[0].canvases[].images[].resource["@id"]' "$IN" \
    | sed 's/\"//g' \
    | sed "s|full/full|full/$SIZE|" \
    > $LINKS
N=$(wc -l $LINKS | awk '{print $1}')
echo "$N pages found"

# Download files
PICS=pics
mkdir $PICS

I=0
for f in $(cat $LINKS); do
    # Files won't be downloaded is they already exist
    wget -cN -O "$PICS/$I.jpg" "$f"
    I=$((I+1))
done

# Convert to pdf
I=0
for f in $(ls -1v $PICS/*.jpg); do
    PDF="$(echo $f | sed 's|\.jpg|\.pdf|')"
    if [ ! -f $PDF ]; then
        convert "$f" "$PDF"
    fi
    I=$((I+1))
done

# Fold files one by one (so that memory usage does not blow)
OUT="$LABEL.pdf"
TMP="$LABEL.tmp.pdf"
I=0
for f in $(ls -1v $PICS/*.pdf); do
    echo "Adding $I/$N | $f"

    if [ -f "$OUT" ]; then
        # out exists
        pdftk "$f" "$OUT" cat output "$TMP"
        rm "$OUT"
        mv "$TMP" "$OUT"
    else
        # out does not exist
        cp "$f" "$OUT"
    fi
    I=$((I+1))
done
