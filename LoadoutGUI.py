#gui with tkinter
import tkinter as tk
from tkinter import Menu, ttk
from tkinter import filedialog
import getpass
import re
import os
from tkinter import messagebox


uwu = 0
username = getpass.getuser()
filename = "C:/Users/"+username+"/AppData/Local/Synthetik/Save.sav"
tfilename = "C:/Users/"+username+"/AppData/Local/Synthetik/TEMPORARYSAVE.txt"

def browsefiles():
    global filename
    global tfilename
    filename = filedialog.askopenfilename(initialdir="/", title="Select a file", filetypes=(("Save files","*.sav*"),("All files","*.*")))
    filepath = filename.rsplit("/",1)[0]
    tfilename = filepath +"/TEMPORARYSAVE.txt"
    print(filepath[0])

if not os.path.exists(filename):
    if uwu == 0:
        messagebox.showinfo('Synthetik','Sorry, your save file is not where I thought it would be! Could you please find it for me?')
    elif uwu == 1:
        messagebox.showinfo('Synfwetik','Sowwy UwU, yowr swave fiwe is nwot whewe I toht it wood bwe! OwO! could you pwease fwind it fwwor me UwU?')
    browsefiles()

# setup main tkinter window name and frame. Configure frame to fill white space and for widgets to expand to fill space
root = tk.Tk()
root.title("Synthetik Loadout Editor")
main_frame = ttk.Frame(root, padding=(20))
main_frame.grid(column=0, row=0) #, sticky=('N', 'W', 'E', 'S'))
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

items = []
VarSmodules = []
VarPistols =[]
DoubleModules = []
CurrentModPowers = []
OptionMod1 = tk.StringVar(main_frame)
OptionMod2 = tk.StringVar(main_frame)
OptionMod3 = tk.StringVar(main_frame)
OptionMod4 = tk.StringVar(main_frame)
OptionMod5 = tk.StringVar(main_frame)
OptionMod6 = tk.StringVar(main_frame)
PistolMod = tk.StringVar(main_frame)

PowerMod1 = tk.StringVar(main_frame)
PowerMod2 = tk.StringVar(main_frame)
PowerMod3 = tk.StringVar(main_frame)
PowerMod4 = tk.StringVar(main_frame)
PowerMod5 = tk.StringVar(main_frame)
PowerMod6 = tk.StringVar(main_frame)


def setsave():
    global VarSmodules
    VarSmodules.clear()
    global DoubleModules
    DoubleModules.clear()
    global VarPistols
    VarPistols.clear()
    with open(filename, "r") as Save:
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
setsave()


Gun = ttk.Combobox(main_frame, textvariable = PistolMod)
Gun['values'] = VarPistols
Gun.grid(row=0,column=1,columnspan=2)
Core = ttk.Combobox(main_frame, textvariable = OptionMod1)
Core['values'] = VarSmodules
Core.grid(row=1,column=1)

CorePower = tk.Entry(main_frame, textvariable = PowerMod1)
CorePower.grid(row=1,column=2)

StartItem = ttk.Combobox(main_frame, textvariable = OptionMod2)
StartItem['values'] = VarSmodules
StartItem.grid(row=2,column=1)

SIPower = tk.Entry(main_frame, textvariable = PowerMod2)
SIPower.grid(row=2,column=2)

Item1 = ttk.Combobox(main_frame, textvariable = OptionMod3)
Item1['values'] = VarSmodules
Item1.grid(row=3,column=1)

I1Power = tk.Entry(main_frame,textvariable= PowerMod3)
I1Power.grid(row=3,column=2)

Item2 = ttk.Combobox(main_frame,textvariable = OptionMod4)
Item2['values'] = VarSmodules
Item2.grid(row=4,column=1)

I2Power = tk.Entry(main_frame,textvariable= PowerMod4)
I2Power.grid(row=4,column=2)

Mod1 = ttk.Combobox(main_frame, textvariable =OptionMod5)
Mod1['values'] = VarSmodules
Mod1.grid(row=5,column=1)

M1Power = tk.Entry(main_frame,textvariable=PowerMod5)
M1Power.grid(row=5,column=2)

Mod2 = ttk.Combobox(main_frame,textvariable = OptionMod6)
Mod2['values'] = VarSmodules
Mod2.grid(row=6,column=1)

M2Power = tk.Entry(main_frame,textvariable=PowerMod6)
M2Power.grid(row=6,column=2)

Loadout = ["9","7","6","5","4","3","0"]
Currentclass = "10"



def Testfunc(subclass):
    global Currentclass
    Currentclass = subclass
    CurrentModPowers.clear()
    items.clear()
    with open(filename, "r") as Save:
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
    with open(filename, "r") as Save:
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
    with open(filename, "r") as Save, open(tfilename, "w") as Tsave:
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
            elif line.startswith("tpoints_"):
                if line.startswith("tpoints_"+OptionMod1.get()):
                    Tsave.write(re.sub('"-?\d+(\.\d+)?"','"'+PowerMod1.get()+'"',line))
                elif line.startswith("tpoints_"+OptionMod2.get()):
                    Tsave.write(re.sub('"-?\d+(\.\d+)?"','"'+PowerMod2.get()+'"',line))
                elif line.startswith("tpoints_"+OptionMod3.get()):
                    Tsave.write(re.sub('"-?\d+(\.\d+)?"','"'+PowerMod3.get()+'"',line))
                elif line.startswith("tpoints_"+OptionMod4.get()):
                    Tsave.write(re.sub('"-?\d+(\.\d+)?"','"'+PowerMod4.get()+'"',line))
                elif line.startswith("tpoints_"+OptionMod5.get()):
                    Tsave.write(re.sub('"-?\d+(\.\d+)?"','"'+PowerMod5.get()+'"',line))
                elif line.startswith("tpoints_"+OptionMod6.get()):
                    Tsave.write(re.sub('"-?\d+(\.\d+)?"','"'+PowerMod6.get()+'"',line))
                else:
                    Tsave.write(line)
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
    with open(filename, "w") as Save, open(tfilename, "r") as Tsave:
        for line in Tsave:
            Save.write(line)
    setsave()


def AutoModuleEdit(power):
    if re.search("(-?(0|[1-9]\d*)?(\.\d+)?(?<=\d)(e-?(0|[1-9]\d*))?|0x[0-9a-f]+)",power) == None:
        if uwu == 0:
            messagebox.showinfo('Power error','Sorry, you pressed the AutoModule button without putting a good input in! Try using only numbers this time, okay?')
        elif uwu == 1:
            messagebox.showinfo('UwO','Sowwy UwU, yow pwessed the AutoModule buttwon wifouf pwutwing a gwood input in! Try uswing only numbwars dis twime, :3 ohkway?')
        return
    with open(filename, "r") as Save, open(tfilename, "w") as Tsave:
        TruePower = '"' + power + '"'
        for line in Save:
            if line.startswith("tpoints_obj_perk_"):
                Tsave.write(re.sub('"-?\d+(\.\d+)?"', TruePower, line))
                continue
            Tsave.write(line)
    Safetywindow()

def OPModuleEdit():
    OPpower=["10.000000","2.500000","2.000000","3.000000","-7.000000","7.000000","30.000000","50.000000","10.000000","15.000000","6.000000","4.000000","4.000000","5.000000","10.000000","3.000000","1.000000","1.000000","8.000000","7.000000","5.000000","10.000000","7.000000","2.500000","40.000000","7.000000","5.000000","20.000000","-0.000100","10.000000","7.000000","7.000000","3.000000","1","1","1","1","15.000000","10.000000","8.000000","4.000000","5.500000","2.900000","1.600000","10.000000","7.000000","5.000000","6.000000","20.000000","20.000000","2.500000","10.000000","1","1","10.000000","20.000000","20.000000","30.000000","20.00000","20.000000","4.000000","5.000000","10.000000","2.500000","10.000000","2.00000","7.000000","7.000000","-34.000000","12.000000","1","1","1"]
    messagebox.showinfo("Ymmv","Overpowered module power editing (your mileage may vary)")
    with open(filename, "r") as Save, open(tfilename, "w") as Tsave:
        j = 0
        for line in Save:
            if line.startswith("tpoints_obj_perk_"):
                item = OPpower[j]
                ActiveLine = '"' + item + '"'
                Tsave.write(re.sub('"-?\d+(\.\d+)?"', ActiveLine, line))
                j += 1
                continue
            Tsave.write(line)
    Safetywindow()

def NewDailyRun():
    with open(filename,"r") as Save, open(tfilename,"w") as Tsave:
        for line in Save:
            if line.startswith("drun"):
                Tsave.write(re.sub('"-?\d+(\.\d+)?"','"1.000000"',line))
            else:
                Tsave.write(line)
    Safetywindow()

def MaxData():
    with open(filename,"r") as Save, open(tfilename,"w") as Tsave:
        for line in Save:
            if line.startswith("currency"):
                Tsave.write(re.sub('"-?\d+(\.\d+)?"','"1000.000000"',line))
            else:
                Tsave.write(line)
    Safetywindow()

def CheatCodeReturn():
    with open(filename,"r") as Save, open(tfilename,"w") as Tsave:
        for line in Save:
            if line.startswith("statist"):
                Tsave.write(re.sub('"-?\d+(\.\d+)?"','"0.000000"',line))
            else:
                Tsave.write(line)
    Safetywindow()

def spliting(Class):
    return [char for char in Class]

def AutoWeaponSpawnEdit():
    Subclass = spliting(Currentclass)
    realclass = Subclass[0] + "_" + Subclass[1]
    weplist = list()
    with open(filename, "r") as Save:
        for line in Save:
            if line.startswith("wbonus_"+realclass):
                wepID = re.search('"\d+\.', line)
                wepID = wepID.group()
                weplist.append(wepID[1:-1])
        if len(weplist) == 0:
            if uwu == 0:
                messagebox.showinfo("Token Error","Sorry, would you go add a power token to the weapon(s) you want?")
            elif uwu == 1:
                messagebox.showinfo("Towken Ewwow","Sowwy UwU, wwould you gow awdd a powwa towken two the weapon(s) you want?")
            return
    with open(filename, "r") as Save, open(tfilename, "w") as Tsave:
        if len(weplist) != 0:
            if uwu == 0:
                messagebox.showinfo("Just so you know","Setting Drop chances for tokened weapons to 10000, and all others to -100.\n This only works for one run, one time per weapon pickup.\n(this does not stop weapon shops from spawning with 4 other weapons)")
            elif uwu == 1:
                messagebox.showinfo("just so uwu know","setting dwop chances fow tokened weapons tuwu 10000, awnd aww othews tuwu -100.\n thiws onwy wowks fow owne wun, owne time pew weapon pickup.\n(this does nowt stowp weapon shops fwom spawning with 4 othew weapons)")
            for line in Save:
                if line.startswith("wdropchange"):
                    for weapon in weplist:
                        if line.startswith("wdropchange"+weapon+"="):
                            Tsave.write(re.sub('"-?\d+\.\d+"','"10000.000000"',line))
                            break
                        else:
                            continue
                    if not(line.startswith("wdropchange"+weapon+"=")):
                        Tsave.write(re.sub('"-?\d+\.\d+"','"-100.000000"',line))
                elif line.startswith("wunlock"):
                    for weapon in weplist:
                        if line.startswith("wunlock"+weapon+"="):
                            Tsave.write(re.sub('"-?\d+\.\d+"','"0.000000"',line))
                            break
                        elif not(line.startswith("wdropchange"+weapon+"=")):
                            Tsave.write(line)
                    else:
                        Tsave.write(line)
                else:
                    Tsave.write(line)
    Safetywindow()

def AutoItemSpawnEdit():
    realclass = spliting(Currentclass)
    subclass = realclass[0] + "_" + realclass[1]
    itemlist = list()
    with open(filename, "r") as Save:
        for line in Save:
            if line.startswith("ibonus_"+subclass):
                itemID = re.search('"\d+\.', line)
                itemID = itemID.group()
                itemlist.append(itemID[1:-1])
        if len(itemlist) == 0:
            if uwu == 0:
                messagebox.showinfo("Towken Error","Sorry, would you go add a power token to the item you want?")
            elif uwu == 1:
                messagebox.showinfo("Towken Ewwow","Sowwy UwU, wwould you gow awdd a powwa towken two te itwem you want?")
            return
    with open(filename, "r") as Save, open(tfilename, "w") as Tsave:
        if len(itemlist) != 0:
            if uwu == 0:
                messagebox.showinfo("Just so you know","Setting Drop chances for tokened items to 100. Setting drop chances for all other items to -100.\nThis only works for one run, one time per item. OTHER ITEMS WILL NOT SPAWN\nThis might also be a bit off kilter- perhaps the tokened item ids do not corellate 1-1 with thier spawn ids")
            elif uwu == 1:
                messagebox.showinfo("just so uwu know","setting dwop chances fow tokened items tuwu 100. Setting dwop chances fow aww othew items tuwu -100.\nthis onwy wowks fow owne wun, owne time pew item. Othew items wiww nowt spawn\nthis might awso be a bit off kiwtew- pewhaps the tokened item ids duwu nowt cowewwate 1-1 with thiew spawn ids")
            for line in Save:
                if line.startswith("idropchange"):
                    for item in itemlist:
                        if line.startswith("idropchange "+item+"="):
                            Tsave.write(re.sub('"-?\d+\.\d+"','"10000.000000"',line))
                            break
                        else:
                            continue                        
                    if not(line.startswith("idropchange "+item+"=")):
                        Tsave.write(re.sub('"-?\d+\.\d+"','"-100.000000"',line))
                else:
                    Tsave.write(line)
    Safetywindow()

def weaponspawnreset():
    with open(filename,"r") as Save, open(tfilename,"w") as Tsave:
        for line in Save:
            if line.startswith("wdropchange"):
                Tsave.write(re.sub('"-?\d+\.\d+"','"0.000000"',line))
            else:
                Tsave.write(line)
    Safetywindow()
    

def itemspawnreset():
    with open(filename,"r") as Save, open(tfilename,"w") as Tsave:
        for line in Save:
            if line.startswith("idropchange"):
                Tsave.write(re.sub('"-?\d+\.\d+"','"0.000000"',line))
            else:
                Tsave.write(line)
    Safetywindow()

def undoresearch():
    with open(filename,"r") as Save, open(tfilename,"w") as Tsave:
        for line in Save:
            if line.startswith("resunlock"):
                Tsave.write(re.sub('"-?\d+\.\d+"','"0.000000"',line))
            else:
                Tsave.write(line)
    Safetywindow()

def openSave():
    os.startfile(filename)

def UwU():
    global uwu
    if uwu == 0:
        Class10.configure(text="Wiot Guawd")
        Class11.configure(text="Bweachew")
        Class20.configure(text="Sniwpew")
        Class21.configure(text="Asswsasswin")
        Class30.configure(text="Waidew")
        Class31.configure(text="Heavwy Gunnew")
        Class40.configure(text="Engineew")
        Class41.configure(text="Demolishew")
        Submit .configure(text="submwit")
        Auto.configure(text="Auto Mwoduwle Edwit")
        uwu = 1
    elif uwu == 1:
        Class10.configure(text="Riot Guard")
        Class11.configure(text="Breacher")
        Class20.configure(text="Sniper")
        Class21.configure(text="Assassin")
        Class30.configure(text="Raider")
        Class31.configure(text="Heavy Gunner")
        Class40.configure(text="Engineer")
        Class41.configure(text="Demolisher")
        Submit .configure(text="submit")
        Auto.configure(text="Auto Module Edit")
        uwu = 0
        

Class10 = tk.Button(main_frame, text="Riot Guard",fg="white", bg="blue",command=lambda: Testfunc("10"))
Class10.grid(row=0,column=0)
Class11 = tk.Button(main_frame, text="Breacher",fg="white", bg="blue",command=lambda: Testfunc("11"))
Class11.grid(row=1,column=0)
Class20 = tk.Button(main_frame, text="Sniper",fg="white", bg="darkblue",command=lambda: Testfunc("20"))
Class20.grid(row=2,column=0)
Class21 = tk.Button(main_frame, text="Assassin",fg="white", bg="darkblue",command=lambda: Testfunc("21"))
Class21.grid(row=3,column=0)
Class30 = tk.Button(main_frame, text="Raider",fg="white", bg="darkgreen",command=lambda: Testfunc("30"))
Class30.grid(row=4,column=0)
Class31 = tk.Button(main_frame, text="Heavy Gunner",fg="white", bg="darkgreen",command=lambda: Testfunc("31"))
Class31.grid(row=5,column=0)
Class40 = tk.Button(main_frame, text="Engineer",fg="white", bg="red",command=lambda: Testfunc("40"))
Class40.grid(row=6,column=0)
Class41 = tk.Button(main_frame, text="Demolisher",fg="white", bg="red",command=lambda: Testfunc("41"))
Class41.grid(row=7,column=0)
Submit = tk.Button(main_frame,text="submit",command=SubmitLoadout)
Submit.grid(row=7,column=1,columnspan=2)
Auto = tk.Button(main_frame,text="Auto Module Edit", command=lambda: AutoModuleEdit(Autopower.get()))
Auto.grid(row=8,column=1)
Autopower = tk.Entry(main_frame)
Autopower.grid(row=8,column=2)

def about():
    if uwu == 0:
        messagebox.showinfo('Synthetik Python Mod','By: Builder_Roberts\nMade for Synthetik 1!')
    elif uwu == 1:
        messagebox.showinfo('synthetik python mod','by: Buiwdew_Wobewts\nmade fow Synthetik 1!')

def notworking():
    if uwu == 0:
        messagebox.showinfo('Actual help','first: try opening and closing synthetik. Make sure Synthetik is closed. That will reset the save file to what Synthetik Needs.\nSecond: message @Mason on the discord. He is the creator of this after all.')
    elif uwu == 1:
        messagebox.showinfo('actuaw hewp','fiwst: twy opening awnd cwosing synthetik. Make suwe synthetik iws cwosed. Thawt wiww weset the save fiwe tuwu whawt synthetik needs.\nsecond: message @mason own the discowd. He iws the cweatow of thiws aftew aww.')

MenuBar = Menu(main_frame)
file = Menu(MenuBar,tearoff=0)
file.add_command(label="Open",command=browsefiles)
file.add_command(label="Show",command=openSave)
file.add_command(label="Exit",command=root.quit)
MenuBar.add_cascade(label="File",menu=file)

power = Menu(MenuBar,tearoff=0)
power.add_command(label="OPauto",command=OPModuleEdit)
power.add_command(label="Quick 1.6x",command=lambda: AutoModuleEdit("1.60000"))
MenuBar.add_cascade(label="Power",menu=power)

misc = Menu(MenuBar,tearoff=0)
misc.add_command(label="Daily Run Reset",command=NewDailyRun)
misc.add_command(label="Max Data",command=MaxData)
misc.add_command(label="Undo Research",command=undoresearch)
misc.add_command(label="UwU OwO",command=UwU)
misc.add_command(label="Cheat Code Reset",command=CheatCodeReturn)
MenuBar.add_cascade(label="Misc",menu=misc)

spawn = Menu(MenuBar,tearoff=0)
spawn.add_command(label="Item Spawn",command=AutoItemSpawnEdit)
spawn.add_command(label="Reset Item Spawn",command=itemspawnreset)
spawn.add_command(label="Weapon Spawn", command=AutoWeaponSpawnEdit)
spawn.add_command(label="Reset Weapon Spawn",command=weaponspawnreset)
MenuBar.add_cascade(label="Spawn",menu=spawn)

Helpbar = Menu(MenuBar,tearoff=0)
Helpbar.add_command(label="About",command=about)
Helpbar.add_command(label="Not working?",command=notworking)
MenuBar.add_cascade(label="Help",menu=Helpbar)


Testfunc(Currentclass)
root.configure(menu = MenuBar)
root.mainloop()