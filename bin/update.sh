#!/bin/bash
echo 'preparing device for update'
touch ~/HARD_SHUTDOWN
sleep 10
rm -f ~/HARD_SHUTDOWN
killall screen
cd ~/InternetOfFish
echo 'automatically initiating data collection'
screen -dm -S master bash -c "python3 internet_of_fish/ui.py --autostart"
