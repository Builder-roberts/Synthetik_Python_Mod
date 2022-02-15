#made by: Builder_Roberts for Synthetik
#Version: 2.2
#Last updated: 2/14/2022 13:17


import re
import getpass
import time
import os
#todo print intro
uinput = ''
username = getpass.getuser()

def CopytoSave():
    uinput = ''
    while uinput != "quit":
        uinput = input("Y/N Do you want to overwite your Save File?\n>>> ")
        if uinput == "Y":
            print("Here comes the BIG GUNS")
            with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "w") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "r") as Tsave:
                for line in Tsave:
                    Save.write(line)
            break
        elif uinput == "N":
            print("good choice, make a copy first, know that your edits are not saved.")
            break
        else:
            continue

def AutoModuleEdit(power):
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        TruePower = '"' + power + '"'
        for line in Save:
            #write content to new file
            #Just find the tpoints_perk thing and edit every line that starts with that. This only works for perks & cores, specifically the Power of said.
            if line.startswith("tpoints_obj_perk_"):
                Tsave.write(re.sub('"-?\d+\.\d+"', TruePower, line))
                continue
            Tsave.write(line)
    CopytoSave()

def AutoWeaponItemEdit(power):
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        TruePower = '"' + power + '"'
        for line in Save:
            #write content to new file
            #Just find the tpoints_perk thing and edit every line that starts with that. This only works for perks & cores, specifically the Power of said.
            if line.startswith("idropchange") or line.startswith("wdropchange"):
                Tsave.write(re.sub('"-?\d+\.\d+"', TruePower, line))
                continue
            Tsave.write(line)
    CopytoSave()

def OPModuleEdit():
    
    OPpower=["10.000000","2.500000","2.000000","3.000000","-7.000000","7.000000","30.000000","50.000000","10.000000","15.000000","6.000000","4.000000","4.000000","5.000000","10.000000","3.000000","1.000000","1.000000","8.000000","7.000000","5.000000","10.000000","7.000000","2.500000","40.000000","7.000000","5.000000","20.000000","-0.000100","10.000000","7.000000","7.000000","3.000000","1","1","1","1","15.000000","10.000000","8.000000","4.000000","5.500000","2.900000","1.600000","10.000000","7.000000","5.000000","6.000000","20.000000","20.000000","2.500000","10.000000","1","1","10.000000","20.000000","20.000000","30.000000","20.00000","20.000000","4.000000","5.000000","10.000000","2.500000","10.000000","2.00000","7.000000","7.000000","-34.000000","12.000000","1","1","1"]
    print("Overpowered module power editing (your mileage may vary)")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        j = 0
        for line in Save:
            #write content to new file
            #Just find the tpoints_perk thing and edit every line that starts with that. This only works for perks & cores, specifically the Power of said
            if line.startswith("tpoints_obj_perk_"):
                item = OPpower[j]
                ActiveLine = '"' + item + '"'
                Tsave.write(re.sub('"-?\d+\.\d+"', ActiveLine, line))
                j += 1
                continue
            Tsave.write(line)
    CopytoSave()

def ManualModuleEdit():
    print("Manual module power editing (remember to just input a decimal)(just press enter to skip)")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        for line in Save:
            #write content to new file
            #Just find the tpoints_perk thing and edit every line that starts with that. This only works for perks & cores, specifically the Power of said
            if line.startswith("tpoints_obj_perk_"):
                Activeline = input(line + ">>> ")
                if Activeline == "":
                    Tsave.write(line)
                    continue
                Activeline = re.search("(-?(0|[1-9]\d*)?(\.\d+)?(?<=\d)(e-?(0|[1-9]\d*))?|0x[0-9a-f]+)", Activeline)
                Activeline = Activeline.group()
                ActiveLine = '"' + Activeline + '"'
                Tsave.write(re.sub('"-?\d+\.\d+"', ActiveLine, line))
                continue
            Tsave.write(line)
    CopytoSave()

def AutoWeaponSpawnEdit():
    uinput = ''
    subclass = ''
    weplist = list()
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
        while uinput != "quit":
            #ask for what class you will be playing
            uinput = input("What class are you going to play? Choose one:\nRG BR SN AS RD HG EN DM\n>>> ")
            if uinput == "RG":
                subclass = "1_0"
                break
            elif uinput == "BR":
                subclass = "1_1"
                break
            elif uinput == "SN":
                subclass = "2_0"
                break
            elif uinput == "AS":
                subclass = "2_1"
                break
            elif uinput == "RD":
                subclass = "3_0"
                break
            elif uinput == "HG":
                subclass = "3_1"
                break
            elif uinput == "EN":
                subclass = "4_0"
                break
            elif uinput == "DM":
                subclass = "4_1"
                break
            else:
                print("sorry, next time write exactly 1 set of 2 capital letters, from the selection shown.")
                continue
        for line in Save:
            if line.startswith("wbonus_"+subclass):
                wepID = re.search('"\d+\.', line)
                wepID = wepID.group()
                weplist.append(wepID[1:-1])
        print("I found ", len(weplist)," weapon(s) in this class that hold a power token")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        if len(weplist) != 0:
            print("Setting Drop chances for tokened weapons to 100, and all others to -10.\n This only works for one run, one time per weapon pickup.\n(this makes all other weapons unspawnable.)")
            for line in Save:
                if line.startswith("wdropchange"):
                    for weapon in weplist:
                        if line.startswith("wdropchange"+weapon):
                            Tsave.write(re.sub('"-?\d+\.\d+"','"10000.000000"',line))
                            break
                        else:
                            continue
                    if not(line.startswith("wdropchange"+weapon)):
                        Tsave.write(re.sub('"-?\d+\.\d+"','"-100.000000"',line))
                else:
                    Tsave.write(line)
        else:
            for line in Save:
                Tsave.write(line)
            print("Sorry, could you go add a power token to the weapon you want?")
    #Search for wbonus_[class]_[subclass] and find ( "\d+\. ) in the line.  search for \d in that. append item to list
    #for each number in the list, find the corresponding wdropchange//
    #edit that wdropchange to be 10000.000000
    CopytoSave()

def AutoItemSpawnEdit():
    uinput = ''
    subclass = ''
    itemlist = list()
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
        while uinput != "quit":
            #ask for what class you will be playing
            uinput = input("What class are you going to play? Choose one:\nRG BR SN AS RD HG EN DM\n>>> ")
            if uinput == "RG":
                subclass = "1_0"
                break
            elif uinput == "BR":
                subclass = "1_1"
                break
            elif uinput == "SN":
                subclass = "2_0"
                break
            elif uinput == "AS":
                subclass = "2_1"
                break
            elif uinput == "RD":
                subclass = "3_0"
                break
            elif uinput == "HG":
                subclass = "3_1"
                break
            elif uinput == "EN":
                subclass = "4_0"
                break
            elif uinput == "DM":
                subclass = "4_1"
                break
            else:
                print("sorry, next time write exactly 1 set of 2 capital letters, from the selection shown.")
                continue
        for line in Save:
            if line.startswith("ibonus_"+subclass):
                itemID = re.search('"\d+\.', line)
                itemID = itemID.group()
                itemlist.append(itemID[1:-1])
        print("I found ", len(itemlist)," item(s) in this class that hold a power token")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        if len(itemlist) != 0:
            print("Setting Drop chances for tokened items to 100. Setting drop chances for all other items to -100.\nThis only works for one run, one time per item.\nThis might also be a bit off kilter- perhaps the tokened item ids do not corellate 1-1 with thier spawn ids")
            for line in Save:
                if line.startswith("idropchange"):
                    for item in itemlist:
                        if line.startswith("idropchange "+item):
                            Tsave.write(re.sub('"-?\d+\.\d+"','"10000.000000"',line))
                            break
                        else:
                            continue                        
                    if not(line.startswith("idropchange "+item)):
                        Tsave.write(re.sub('"-?\d+\.\d+"','"-100.000000"',line))
                else:
                    Tsave.write(line)
        else:
            for line in Save:
                Tsave.write(line)
            print("Sorry, could you go add a power token to the item you want?")
    CopytoSave()

def openSave():
    os.startfile("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav")

while uinput != "quit":
    uinput = input(">>> ")
    if uinput == "help":
    #todo write help page
        print(" auto - sets every module to a user-decided amount of power\n manual - allows the user to set the power of individual modules\n copynow - copies the temporary save directly to save.sav\n weaponspawn - sets spawn chances for weapons with power tokens\n itemspawn - sets spawn chances for items with power tokens\n opensave - opens the save file in your default file editor\n quit - stops the program")
        continue
    elif uinput == "auto":
        print("what power would you like every module to have? (normal variance is 1.0 - 1.6)")
        uinput = input(">>> ")
        uinput = re.search("(-?(0|[1-9]\d*)?(\.\d+)?(?<=\d)(e-?(0|[1-9]\d*))?|0x[0-9a-f]+)", uinput)
        uinput = uinput.group()
        if uinput != "":
            AutoModuleEdit(uinput)
        else:
            print("well, make up your mind")
        continue
    elif uinput == "Spawauto":
        print("This is for spawn rates of every item and weapon. (normal variance is -7 to 0)")
        uinput = input(">>> ")
        uinput = re.search("(-?(0|[1-9]\d*)?(\.\d+)?(?<=\d)(e-?(0|[1-9]\d*))?|0x[0-9a-f]+)", uinput)
        uinput = uinput.group()
        if uinput != "":
            AutoWeaponItemEdit(uinput)
        else:
            print("well, make up your mind")
        continue
    elif uinput == "OPauto":
         OPModuleEdit()
         continue
    elif uinput == "manual":
        ManualModuleEdit()
        continue
    elif uinput == "weaponspawn":
        AutoWeaponSpawnEdit()
        continue
    elif uinput == "itemspawn":
        AutoItemSpawnEdit()
        continue
    elif uinput == "copynow":
        CopytoSave()
        continue
    elif uinput == "quit":
        print("thanks for trying this out!\nMade by: Builder_Roberts for Synthetik")
        time.sleep(2)
        break
    elif uinput == "opensave":
        openSave()
        continue
    else:
        print("try typing 'help' for a list of commands")
        continue