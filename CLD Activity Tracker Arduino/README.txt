Hello!

There are a lot of folders in this GitHub, so hopefully this readme can provide a helpful overview of what you're looking at. This document will explain how each of the folders/code is organized, and there will be additional documents explaining how the code works within the folders (along with comments in the code). The important subdirectories are Clinical Trial Scripts and Redesigned PCB Scripts, both of which contain current scripts that will be built off of in the future.

Folders:

Clinical Trial Scripts - Contains all firmware and software scripts used in the clinical trial. These are the most updated scripts that work with the old iteration of the PCB (the iteration used in the clinical trial). All data analysis and collection was done with these scripts. An additional README is provided in this folder to outline how each of them works.

Redesigned PCB Script - contains code for controlling the newest iteration of the PCB. This PCB was not used in clinical testing and is in the early stages of development. The new PCB aims to meet the design specifications related to on-board memory and power consumption. Many of the scripts were designed to validate that the board was working as intended, and to be used in subsequent tests on power consumption.

IMU42670P Scripts - contains code for operating the older iteration of the PCB. This PCB was used in clinical testing and is able to collect and export IMU data. The code in this folder contains many iterations of firmware for this board that were meant to accomplish various tasks. The most updated version of the firmware is included in the clinical trial scripts folder, so it is not necessary to use any of these scripts.

Bluetooth Connectivity - contains code for many iterations of the GUI used for data upload. The most updated GUI used in clinical testing is included in the clinical trial scripts folder, so it is not necessary to use any of these scripts.

Analysis Scripts - contains code for many iterations of data analysis scripts. The most updated data analysis scripts used in clinical testing are included in the clinical trail scripts folder, so it is not necessary to use any of these scripts.

Pedometer Data - contains data from initial team testing of the device. These datasets were recorded at various frequencies and with various gaits to determine how the device was able to track step count under varying conditions.

