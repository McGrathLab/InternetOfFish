# InternetOfFish
Python package for running video collection and on-device real-time computer vision analysis on Raspbery 
Pi computers in the Streelman/McGrath aquatics facility

### Setup and Installation:  
Assemble one or more Raspberry Pis and equip them with SD cards containing a fresh install of the Raspberry Pi OS.
At this time, the coral TPU only support Debian 10 derivatives, so you need to use the legacy Raspberry Pi OS built on 
Debian Buster. Set up the pi(s) in the aquatics facility, making sure to attach the Coral USB TPU accelerator, 
connect the ethernet, and mount the camera. Use the largest SD card available (preferably 256gb) as project data
is stored locally rather than on an external harddrive.

Open the terminal on one of the lab desktops. Rclone should already be installed, but you can check by running 
"rclone --version". Now run "rclone listremotes" and see if there is an entry called "cichlidVideo:". If so, continue to
step 3. If not, run "rclone config" and configure a dropbox remote called cichlidVideo that is authenticated to access
the BioSci-McGrath folder. 

Use the following command to clone the repository into a directory of your choosing, or use an IDE with github
integration (such as PyCharm) to do the same.

        git clone https://github.com/tlancaster6/InternetOfFish

Move into the newly-created InternetOfFish directory and run the following command to install the controller
dependencies.

        bash ./bin/configure_controller.sh
Using nano, open the file called InternetOfFish/credentials/hosts.secret, or create it if it does not exist. In this
file, enter the IP addresses of the pi(s) you want to reach, one per line. Move into the directory 
InternetOfFish/controller. Ping the pi's listed in the host file using the following command, and confirm that they are 
all able to connect.  

       fab ping
Run the automated configuration process using the following command. This will clone this repository into the home
directory of each pi, install all dependencies, and modify some elements of the system configuration. This process will
take a while, especially the part where numpy gets recompiled. If you are configuring multiple pi's, and are in a
hurry, you can also ssh into each pi individually and manually run the configure_worker.sh script (located in the 
project bin).

       fab config
Double check that the repository was cloned successfully and is fully up-to-date using the following command. This
command can also be run any time the main repository is updated to update all pi's on the host list.

       fab pull

### Starting your first project
Begin by either ssh'ing into your pi remotely, or connecting a keyboard and monitor to interface with it directly.
Start a screen session with the command  

      screen -S master
Now run the following command to enter the interactive InternetOfFish command-line interface:

      iof
From the main menu, select  

      create a new project
Then from the submenu that opens, select 

      create a standard project
to enter the interactive project creation process. Answer the prompts as they appear until you are returned to the 
menu where you selected "create a standard project". Choose option 0, 

      return to the previous menu, 
to return to the main menu. At this point, the project framework has been generated, but data collection has not yet 
started: i.e., the project is "active" but not "running". To confirm this, try selecting the each of the following
from the main menu: 
        
      show the currently active project
      check if a project is already running

the first option will print the ID of the project you just created, while the second should inform you that there does 
not appear to be a project currently running. To initiate data collection, run the following command.

      start the currently active project
You should see a message indicating that the project is now running in the background. At this point, it is safe to 
detach the screen (by pressing ctrl+a then ctrl+d) and log out of the pi (by pressing ctrl+d). The application will 
continue to run in the detached screen session, and your first batch of data will upload to DropBox tonight. 

### accessing logs

If you want to double check that data collection is running smoothly, try selecting 
      
      get additional info about the currently active project
from the main menu, and then 

      view the tail of the summary log
This will print the tail end of the program-wide info-level log. To access even more detailed logs, select

      view the tail of a different log
and then type the name of the log you want to access. If you don't know the names of the logs, leave this field blank
and press enter to trigger a help message with the valid log names. You can clear the log files by choosing

        view additional utilities
and then selecting

        clear the log files

At any time, you can also access (and even download) the complete log files from the InternetOfFish/logs directory. Log
files will get overwritten eventually, so it is recommended that you download the log files if your device encounters
a major error. 


