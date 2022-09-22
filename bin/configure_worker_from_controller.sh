#!/bin/bash

mdt exec 'git clone http://github.com/McGrathLab/InternetOfFish.git'
mdt push ~/.config/rclone/rclone.conf /home/mendel/.config/rclone
mdt exec 'bash ~/InternetOfFish/bin/configure_worker.sh'
