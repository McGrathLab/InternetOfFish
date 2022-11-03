#!/bin/bash
touch ~/HARD_SHUTDOWN
sleep 10
rm -f ~/HARD_SHUTDOWN
killall screen
echo automatically initiating data collection
cd ~/InternetOfFish
git reset --hard HEAD
git pull
screen -dm -S master bash -c "python3 internet_of_fish/ui.py --autostart"
