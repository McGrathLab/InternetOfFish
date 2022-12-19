#!/bin/bash
echo 'preparing device for update'
touch ~/HARD_SHUTDOWN
sleep 10
rm -f ~/HARD_SHUTDOWN
killall screen
cd ~/InternetOfFish
echo 'initiating end mode'
screen -dm -S master bash -c "python3 internet_of_fish/ui.py --autostart"
touch ~/ENTER_END_MODE
sleep 10
rm -f ~/ENTER_END_MODE
echo 'finalizing cleanup'
touch ~/HARD_SHUTDOWN
sleep 10
rm -f ~/HARD_SHUTDOWN
killall screen
sudo reboot