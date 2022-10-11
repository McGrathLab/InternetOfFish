#!/bin/bash
# update the repository
echo 'updating repository'
cd ~/InternetOfFish
git reset --hard HEAD
git pull
# install requirements
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
sudo apt-get -y install libedgetpu1-std
sudo apt-get -y install python3-pycoral
sudo apt-get -y install screen
curl https://rclone.org/install.sh | sudo bash
sudo pip3 install picamera
sudo pip3 install sendgrid
sudo pip3 install opencv-python-headless
sudo pip3 install ffmpeg
sudo pip3 install -U numpy
sudo apt-get -y install libatlas-base-dev
# generate a crontab entry to restart data collection every time the pi reboots
echo 'setting up cron job'
(crontab -l ; echo "@reboot ~/InternetOfFish/bin/unit_scripts/auto_start.sh" ) | sort - | uniq - | crontab -
# copy the special bash alias file into the home directory
echo 'setting up bash aliases'
cp ~/InternetOfFish/bin/system_files/.bash_aliases ~/.bash_aliases
# download credential files
rclone copy cichlidVideo:/BioSci-McGrath/Apps/CichlidPiData/__CredentialFiles/iof_credentials ~/InternetOfFish/credentials

##arducam 16mp reqs
#wget -O install_pivariety_pkgs.sh https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
#chmod +x install_pivariety_pkgs.sh
#sudo apt update
#./install_pivariety_pkgs.sh -p libcamera_dev
#./install_pivariety_pkgs.sh -p libcamera_apps
#./install_pivariety_pkgs.sh -p imx519_kernel_driver
#
##picamera2
#sudo apt install -y python3-kms++
#sudo apt install -y python3-pyqt5 python3-prctl libatlas-base-dev ffmpeg
#sudo pip3 install numpy --upgrade
#sudo pip3 install picamera2==0.3.2