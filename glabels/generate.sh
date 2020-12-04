#! /bin/bash

echo '<?xml version="1.0"?>'
echo '<Glabels-templates xmlns="http://glabels.org/xmlns/3.0/">'

for height in 10 20 25 30 50 60 70 75 80 90 100 110 120 125 130 140 150; do
    sed "s/@@HEIGHT@@/$height/g" Phomemo_Q22.template
done
echo '</Glabels-templates>'
