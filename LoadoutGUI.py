#gui with tkinter
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
OptionMod1 = tk.StringVar(root)
OptionMod2 = tk.StringVar(root)
OptionMod3 = tk.StringVar(root)
OptionMod4 = tk.StringVar(root)
OptionMod5 = tk.StringVar(root)
OptionMod6 = tk.StringVar(root)
PistolMod = tk.StringVar(root)


with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
    for line in Save:
        if line.startswith("tpoints_obj_perk") or line.startswith("tpoints_obj_item") or line.startswith("tpoints_obj_artefact"):
            P = re.search("obj_\w+(\d+)?_\w+",line).group()
            VarSmodules.append(P)
        elif line.startswith("tpoints_obj_weapon"):
            P = re.search("obj_\w+(\d+)?_\w+",line).group()
            VarPistols.append(P)
            

Gun = ttk.Combobox(root, textvariable = PistolMod)
Gun['values'] = VarPistols
Gun.grid(row=0,column=1)
Core = ttk.Combobox(root, textvariable = OptionMod1)
Core['values'] = VarSmodules
Core.grid(row=1,column=1)
StartItem = ttk.Combobox(root, textvariable = OptionMod2)
StartItem['values'] = VarSmodules
StartItem.grid(row=2,column=1)
Item1 = ttk.Combobox(root, textvariable = OptionMod3)
Item1['values'] = VarSmodules
Item1.grid(row=3,column=1)
Item2 = ttk.Combobox(root,textvariable = OptionMod4)
Item2['values'] = VarSmodules
Item2.grid(row=4,column=1)
Mod1 = ttk.Combobox(root, textvariable =OptionMod5)
Mod1['values'] = VarSmodules
Mod1.grid(row=5,column=1)
Mod2 = ttk.Combobox(root,textvariable = OptionMod6)
Mod2['values'] = VarSmodules
Mod2.grid(row=6,column=1)
Loadout = ["9","7","6","5","4","3","0"]
Currentclass = ""



def Testfunc(subclass):
    global Currentclass
    Currentclass = subclass
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "r") as Save:
        items.clear()
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
    PistolMod.set(VarPistols[VarPistols.index(items[0])])
    OptionMod1.set(VarSmodules[VarSmodules.index(items[6])])
    OptionMod2.set(VarSmodules[VarSmodules.index(items[5])])
    OptionMod3.set(VarSmodules[VarSmodules.index(items[4])])
    OptionMod4.set(VarSmodules[VarSmodules.index(items[3])])
    OptionMod5.set(VarSmodules[VarSmodules.index(items[2])])
    OptionMod6.set(VarSmodules[VarSmodules.index(items[1])])

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
    with open("C:/Users/"+username+"/AppData/Local/Synthetik/save.sav", "w") as Save, open("C:/Users/"+username+"/Downloads/Tsave.txt", "r") as Tsave:
        for line in Tsave:
            Save.write(line)


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
Submit.grid(row=7,column=1)
Testfunc("10")
root.mainloop()
