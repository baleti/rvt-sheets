cd ~/bisect600; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
rm -f ~/bisect600.txt
for d in *; do echo -n "$d " >> ~/bisect600.txt; (cd $d && python tools/peak_rss.py $F 600158 >> ~/bisect600.txt 2>&1); done
echo DONE >> ~/bisect600.txt
