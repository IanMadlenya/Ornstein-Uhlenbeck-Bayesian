#!/bin/bash
for i in `seq 1 $1`;
do
    time python langevin_pymc3_repeat.py >> log.txt
done
