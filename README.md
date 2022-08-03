# Synthetik_Python_Mod
A save editor tool for the game Synthetik written in python.
if it can't find your save file, try looking in username/appdata/local/synthetik it should be called Save.sav
(you may have to type that directly into the file-path)

You definitely need to have Synthetik closed when you change anything.

HOW TO USE THE OLD SPAWN MENU:

Select the class you want.

Power Token the items you want, then "Submit". (Do the same for Weapons)

Then click "Spawn -> Old Item Spawn" (& Old Weapon Spawn) In the top bar.

HOW TO USE THE NEW SPAWN MENU:

Click "Spawn -> Item spawn" (or Weapon Spawn)

Delete any of the items you don't want showing up (there should be no spaces in,between each,item)

Click "Confirm Spawn List"

ALERT TO ALL NEW SPAWN MENU USERS: the current version uses typos. when those are fixed, your current copied lists will not work.

# Version 2.7
### NEW! The right side now works! you now have the capability to change your tokens outside of the game! it goes: bonus tokens, Up tokens, Down tokens.
### Pretty Colors! Readability! Thank you to Lawro#0858 for helping me with the update!
### Cheat code reset: if you've ever used a cheat code, and want to again, this automatically resets them all!
### Changing the values next to the items/modules/whatever in your loadout will now change their power! - Manual editing, essentially.
### Menubar! specifically File, Power, Misc, and Help.
### File: If you want to edit some other Synthetik (S1) Save file, simply open it!
### Misc: Max Data and Daily Run reset: what they say they do. New! uwu and reseach regression! -uwu was getting annoying, even for me, so by default it's off. Research regression should be used in combination with max data.
### Power: OPauto is now here! additionally, Quick 1.6x makes everything 1.6, the normal daily max, no need to use Auto Module Edit!
### Help: About page, will mention people who helped make this project work in the future! Not Working: Gives some general advice and asks you to @ me on discord.
### Spawn: Item and Weapon Spawn make spawn rates for token weapons higher, and everything else lower. The resets makes the spawn possibility of every item/weapon 0, the highest natural value. Power token (the circle lightning thing) whatever you definetly want to spawn. supply tokens still work as normal, making items and weapons show up in shops.
### ALERT: Reset Item Spawn allows Armageddon shard to spawn when it shouldn't. If someone can tell me what the id for armageddon shard is, that can be fixed. until then, if you reset, just play until you get armageddon shard then quit back to the main menu.
### ALERT: If you want to help me make this code better, feel totally free to @Mason on discord, and/or just fork this project.

## -Now, i gotta tell you, this is some thrown together, dumb as frick code written in python. there's probably bugs.
## -However, the largest bug probable is the deletion of your current day's save file. There are two backups in the same folder already in the game, you can just copy and paste.
## I used (https://towardsdatascience.com/how-to-easily-convert-a-python-script-to-an-executable-file-exe-4966e253c7e9) to generate the exe file from my code. thank you to Caesar_Salad on discord for showing me that it worked without downloading python!
## Thank you to Tactu on discord for general coding advice, and helping edit the UI!

# Future Updates:
### I just need names for the items section for 2.7.1, then i'll add colors to the weapons and items. (Still to do 8/2/22)
### Changing to Class-based coding structure for easier readability and modification
### Changing Newspawns from Text-based entry to Slider-based entry
### Save for the mod itself so you don't have to keep copying and pasting things into the new spawn menu
