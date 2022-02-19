#gui with tkinter
from cgitb import text
import tkinter as tk
from tkinter import ttk
import getpass
import re

username = getpass.getuser()


root = tk.Tk()
root.title("Synthetik Loadout Editor")
items = []
VarSmodules = []
VarPistols =[]
DoubleModules = []
CurrentModPowers = []
OptionMod1 = tk.StringVar(root)
OptionMod2 = tk.StringVar(root)
OptionMod3 = tk.StringVar(root)
OptionMod4 = tk.StringVar(root)
OptionMod5 = tk.StringVar(root)
OptionMod6 = tk.StringVar(root)
PistolMod = tk.StringVar(root)

PowerMod1 = tk.StringVar(root)
PowerMod2 = tk.StringVar(root)
PowerMod3 = tk.StringVar(root)
PowerMod4 = tk.StringVar(root)
PowerMod5 = tk.StringVar(root)
PowerMod6 = tk.StringVar(root)


with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
    for line in Save:
        if line.startswith("tpoints_obj_perk") or line.startswith("tpoints_obj_artefact") or line.startswith("tpoints_obj_item"):
            P = re.search("obj_\w+(\d+)?_\w+",line).group()
            VarSmodules.append(P)
            P = re.search('"-?\d+(\.\d+)?"',line).group()
            P = re.search('-?\d+(\.\d+)?',P).group()
            DoubleModules.append(P)
        elif line.startswith("tpoints_obj_weapon"):
            P = re.search("obj_\w+(\d+)?_\w+",line).group()
            VarPistols.append(P)



Gun = ttk.Combobox(root, textvariable = PistolMod)
Gun['values'] = VarPistols
Gun.grid(row=0,column=1,columnspan=2)
Core = ttk.Combobox(root, textvariable = OptionMod1)
Core['values'] = VarSmodules
Core.grid(row=1,column=1)

CorePower = tk.Entry(root, textvariable = PowerMod1)
CorePower.grid(row=1,column=2)

StartItem = ttk.Combobox(root, textvariable = OptionMod2)
StartItem['values'] = VarSmodules
StartItem.grid(row=2,column=1)

SIPower = tk.Entry(root, textvariable = PowerMod2)
SIPower.grid(row=2,column=2)

Item1 = ttk.Combobox(root, textvariable = OptionMod3)
Item1['values'] = VarSmodules
Item1.grid(row=3,column=1)

I1Power = tk.Entry(root,textvariable= PowerMod3)
I1Power.grid(row=3,column=2)

Item2 = ttk.Combobox(root,textvariable = OptionMod4)
Item2['values'] = VarSmodules
Item2.grid(row=4,column=1)

I2Power = tk.Entry(root,textvariable= PowerMod4)
I2Power.grid(row=4,column=2)

Mod1 = ttk.Combobox(root, textvariable =OptionMod5)
Mod1['values'] = VarSmodules
Mod1.grid(row=5,column=1)

M1Power = tk.Entry(root,textvariable=PowerMod5)
M1Power.grid(row=5,column=2)

Mod2 = ttk.Combobox(root,textvariable = OptionMod6)
Mod2['values'] = VarSmodules
Mod2.grid(row=6,column=1)

M2Power = tk.Entry(root,textvariable=PowerMod6)
M2Power.grid(row=6,column=2)

Loadout = ["9","7","6","5","4","3","0"]
Currentclass = ""



def Testfunc(subclass):
    global Currentclass
    Currentclass = subclass
    CurrentModPowers.clear()
    items.clear()
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
        for line in Save:
            if line.startswith("perkslot"):
                for num in Loadout:
                    if line.startswith("perkslot"+num+"class"+subclass):
                        P = re.search("obj_\w+(\d+)?_\w+",line).group()
                        items.append(P)
                    else:
                        continue
            else:
                continue
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
        for line in Save:
            if line.startswith("tpoints_obj_perk") or line.startswith("tpoints_obj_artefact"):
                for U in items:
                    if line.startswith("tpoints_"+U):
                        P = re.search('-?\d+(\.\d+)?',line).group()
                        CurrentModPowers.append(P)
                    else:
                        continue
            else:
                continue
    PistolMod.set(VarPistols[VarPistols.index(items[0])])
    OptionMod1.set(VarSmodules[VarSmodules.index(items[6])])
    PowerMod1.set(DoubleModules[VarSmodules.index(items[6])])
    OptionMod2.set(VarSmodules[VarSmodules.index(items[5])])
    PowerMod2.set(DoubleModules[VarSmodules.index(items[5])])
    OptionMod3.set(VarSmodules[VarSmodules.index(items[4])])
    PowerMod3.set(DoubleModules[VarSmodules.index(items[4])])
    OptionMod4.set(VarSmodules[VarSmodules.index(items[3])])
    PowerMod4.set(DoubleModules[VarSmodules.index(items[3])])
    OptionMod5.set(VarSmodules[VarSmodules.index(items[2])])
    PowerMod5.set(DoubleModules[VarSmodules.index(items[2])])
    OptionMod6.set(VarSmodules[VarSmodules.index(items[1])])
    PowerMod6.set(DoubleModules[VarSmodules.index(items[1])])

def SubmitLoadout():
    print("now applying changes to Tsave")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        for line in Save:
            if line.startswith("perkslot"+Loadout[0]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",PistolMod.get(),line))
            elif line.startswith("perkslot"+Loadout[6]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",OptionMod1.get(),line))
            elif line.startswith("perkslot"+Loadout[5]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",OptionMod2.get(),line))
            elif line.startswith("perkslot"+Loadout[4]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",OptionMod3.get(),line))
            elif line.startswith("perkslot"+Loadout[3]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",OptionMod4.get(),line))
            elif line.startswith("perkslot"+Loadout[2]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",OptionMod5.get(),line))
            elif line.startswith("perkslot"+Loadout[1]+"class"+Currentclass):
                Tsave.write(re.sub("obj_\w+(\d+)?_\w+",OptionMod6.get(),line))
            else:
                Tsave.write(line)
    Safetywindow()


def Safetywindow():
    SafetyWindow = tk.Toplevel(root)
    SafetyWindow.title("ALERT!")
    tk.Label(SafetyWindow, text ="Do you want to overwrite your Save File?").pack()
    tk.Button(SafetyWindow, text = "Yes", command=lambda: [CopytoSave(),SafetyWindow.destroy()]).pack()


def CopytoSave():
    print("this is working")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "w") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "r") as Tsave:
        for line in Tsave:
            Save.write(line)

def GetPower():
    global DoubleModules
    DoubleModules.clear()
    print("getpower called")
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
        for line in Save:
            if line.startswith("tpoints_obj_perk") or line.startswith("tpoints_obj_artefact") or line.startswith("tpoints_obj_item"):
                P = re.search('"-?\d+(\.\d+)?"',line).group()
                P = re.search('-?\d+(\.\d+)?',P).group()
                DoubleModules.append(P)

def AutoModuleEdit(power):
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "w") as Tsave:
        TruePower = '"' + power + '"'
        for line in Save:
            #write content to new file
            #Just find the tpoints_perk thing and edit every line that starts with that. This only works for perks & cores, specifically the Power of said.
            if line.startswith("tpoints_obj_perk_"):
                Tsave.write(re.sub('"-?\d+(\.\d+)?"', TruePower, line))
                continue
            Tsave.write(line)
    Safetywindow()
    GetPower()

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
                Tsave.write(re.sub('"-?\d+(\.\d+)?"', ActiveLine, line))
                j += 1
                continue
            Tsave.write(line)
    Safetywindow()
    GetPower()



Class10 = tk.Button(root, text="Riot Guard",fg="white", bg="blue",command=lambda: Testfunc("10"))
Class10.grid(row=0,column=0)
Class11 = tk.Button(root, text="Breacher",fg="white", bg="blue",command=lambda: Testfunc("11"))
Class11.grid(row=1,column=0)
Class20 = tk.Button(root, text="Sniper",fg="white", bg="darkblue",command=lambda: Testfunc("20"))
Class20.grid(row=2,column=0)
Class21 = tk.Button(root, text="Assassin",fg="white", bg="darkblue",command=lambda: Testfunc("21"))
Class21.grid(row=3,column=0)
Class30 = tk.Button(root, text="Raider",fg="white", bg="darkgreen",command=lambda: Testfunc("30"))
Class30.grid(row=4,column=0)
Class31 = tk.Button(root, text="Heavy Gunner",fg="white", bg="darkgreen",command=lambda: Testfunc("31"))
Class31.grid(row=5,column=0)
Class40 = tk.Button(root, text="Engineer",fg="white", bg="red",command=lambda: Testfunc("40"))
Class40.grid(row=6,column=0)
Class41 = tk.Button(root, text="Demolisher",fg="white", bg="red",command=lambda: Testfunc("41"))
Class41.grid(row=7,column=0)
Submit = tk.Button(root,text="submit",command=SubmitLoadout)
Submit.grid(row=7,column=1,columnspan=2)
OPauto = tk.Button(root,text="OP Auto",command=OPModuleEdit)
OPauto.grid(row = 8, column= 0)
Auto = tk.Button(root,text="Auto Module Edit", command=lambda: AutoModuleEdit(Autopower.get()))
Auto.grid(row=8,column=1)
Autopower = tk.Entry(root)
Autopower.grid(row=8,column=2)
Testfunc("10")
root.mainloop()
