#LoadoutEditor.py
#remaking LoadoutGUI from the ground up with classes and such.

from http.client import ImproperConnectionState
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.ttk import Notebook
import getpass
import re
import os


#The UI is made using Tkinter, (now as a class rather than a free-floating function)
#running through a tutorial called Tkinter with Examples to get myself familiar with classes. 
class Root(tk.Tk):
    def __init__(self):
        super().__init__()
        #title
        self.title("Synthetik Loadout Editor v3.0")
        #geometry, I think it's important to put this before any packing.
        self.geometry("700x400")
        ATitle = tk.Label(self, text="Synthetik Editor", bg="Lightgrey",fg="black", padx=10,pady=5)
        ATitle.pack(side=tk.TOP)
        
        #make a submit button, used on every class. add a command to submit everything on current tab.
        self.submit_button = tk.Button(self, text="SUBMIT")
        self.submit_button.pack(side=tk.BOTTOM, fill=tk.X)

        self.Button_frame = tk.Frame(self)
        self.Power_frame = tk.Frame(self)
        self.Token_frame = tk.Frame(self)
        self.Button_frame.pack(side=tk.LEFT)

        #button frame start
        #all the classes. needs command to switch color of the whole thing.
        self.Riot_button = tk.Button(self.Button_frame, text="Riot Guard",fg="white", bg="blue", command=lambda:Change_class("10"))
        self.Riot_button.pack(fill=tk.X)
        self.Breach_button = tk.Button(self.Button_frame, text="Breacher",fg="white", bg="blue")
        self.Breach_button.pack(fill=tk.X)
        self.Snipe_button = tk.Button(self.Button_frame, text="Sniper",fg="white", bg="darkblue")
        self.Snipe_button.pack(fill=tk.X)
        self.Kill_button = tk.Button(self.Button_frame, text="Assassin",fg="white", bg="darkblue")
        self.Kill_button.pack(fill=tk.X)
        self.Raid_button = tk.Button(self.Button_frame, text="Raider",fg="white", bg="darkgreen")
        self.Raid_button.pack(fill=tk.X)
        self.Heavy_button = tk.Button(self.Button_frame, text="Heavy Gunner",fg="white", bg="darkgreen")
        self.Heavy_button.pack(fill=tk.X)
        self.Engi_button = tk.Button(self.Button_frame, text="Engineer",fg="white", bg="red")
        self.Engi_button.pack(fill=tk.X)
        self.Demo_button = tk.Button(self.Button_frame, text="Demolisher",fg="white", bg="red")
        self.Demo_button.pack(fill=tk.X)
        #button frame end

        #unchanging variables start here
        #get the user's name
        username = getpass.getuser()
        #user's actual save,
        filename = "C:/Users/"+username+"/AppData/Local/Synthetik/Save.sav"
        #current code has to do some switching around with the files, can't just edit the save as-is.
        tfilename = "C:/Users/"+username+"/AppData/Local/Synthetik/TEMPORARYSAVE.txt"

        #there's some excess values at 8,2, and 1. this helps identify which values in the save the program should check.
        Save_Loadout = ["9","7","6","5","4","3","0"]

        #since the modules/pistols wont ever change, I just made it permanent
        VarSmodules = ["obj_item130_riotguard","obj_item54_c4","obj_item132_dynamite","obj_item98_minisentry","obj_artefact_tactical","obj_artefact_instagib","obj_artefact_madness","obj_artefact_mysterybonus","obj_artefact_terrorlevel","obj_artefact_ricochet","obj_artefact_elemental","obj_artefact_friendlyfire","obj_artefact_ultradrop","obj_artefact_itemupgrade","obj_artefact_pistol","obj_artefact_buff","obj_artefact_powerup","obj_artefact_strafe","obj_artefact_crit","obj_artefact_shop","obj_artefact_healing","obj_artefact_slowdown","obj_artefact_weaponcarry","obj_perk_force","obj_perk_sunrise","obj_perk_dodgeheat","obj_perk_transmutate","obj_perk_heatcontrol","obj_perk_elementalpower","obj_perk_heatrecharge","obj_perk_itemcdvariant","obj_perk_focus","obj_perk_selfrepair","obj_perk_ammoregen","obj_perk_pistolextender","obj_perk_hframe","obj_perk_grenadier","obj_perk_heatup","obj_perk_statusextender","obj_perk_engineer","obj_perk_demolisher","obj_item110_spider","obj_item126_missiledrone","obj_item80_masterkey","obj_item38_grenade_toxic","obj_item71_sentry","obj_item101_resonator","obj_perk_drill","obj_perk_killer","obj_perk_cover","obj_perk_scarred","obj_perk_combo","obj_perk_holdbreath","obj_perk_wepupgrade","obj_perk_edge","obj_perk_reloadsurge","obj_perk_fieldration","obj_perk_drone1","obj_perk_specializedammo","obj_perk_powerstep","obj_perk_reloadstack","obj_perk_classweapon","obj_perk_raider","obj_perk_squadleader","obj_perk_assaultgunner","obj_perk_commando","obj_item124_gunner","obj_item86_commandoflare","obj_item123_cover","obj_item109_reloader2","obj_item55_stim","obj_item37_grenade_plasma","obj_item81_tanto","obj_perk_healthy","obj_perk_diehard","obj_perk_stealback","obj_perk_reactivereload","obj_perk_standstill","obj_perk_powertuning","obj_perk_specialized","obj_perk_perfection","obj_perk_longrange","obj_perk_discipline","obj_perk_dance","obj_perk_backstab","obj_perk_dodgeboost","obj_perk_ejectsurge","obj_perk_headshotammo","obj_perk_marksman","obj_perk_assassin","obj_item122_targetcpu","obj_item94_dagger","obj_item115_decoy","obj_item83_grenade_smoke","obj_item97_minelaser","obj_item82_flare","obj_item79_bolt","obj_item35_grenade_flash","obj_perk_reloadsurge2","obj_perk_return","obj_perk_berserk","obj_perk_scavengerbits","obj_perk_scraparmor","obj_perk_lowhpregen","obj_perk_shieldoc","obj_perk_shotgunmaster","obj_perk_enrage","obj_perk_fortify","obj_perk_killshield","obj_perk_aegis","obj_perk_closer","obj_perk_recovery","obj_perk_warmup","obj_perk_iframe","obj_perk_breacher","obj_perk_riotguard","obj_item99_battlecry","obj_item100_breachingcharge","obj_item12_reflector","obj_item33_shieldburst","obj_item121_tomahawk","obj_item69_taser","obj_item36_grenade_stun","obj_item6_reloader","obj_item64_chalice","obj_item63_cellreplacer","obj_item18_potion","obj_item8_injection","obj_item30_methadone","obj_item7_vial","obj_perk_randomperk"]
        VarPistols =["obj_weapon_TEC_84","obj_weapon_SUP_67","obj_weapon_DE_94","obj_weapon_A9_55","obj_weapon_REP_11","obj_weapon_HLP_64","obj_weapon_LSP_21","obj_weapon_DE_61","obj_weapon_HON_34","obj_weapon_REV_9","obj_weapon_MC_62","obj_weapon_CP_38","obj_weapon_G17_63","obj_weapon_PXS_10","obj_weapon_PTL_6"]
        #Shownmodules is going to be the more readable version of VarSmodules that will be used. I'm having Lawro#0858 make a list to use; done
        ShownModules = ["Guardian", "Composite 4", "Neutrino Bomb", "Seth-Up Suitcase Sentry", "Mode: Tactical", "Mode: Hyper Adrenaline", "Mode: Madness", "Mode: Mystery Bonus", "PU-55", "Hobb-S", "Rynn", "Rhett", "Kevv", "Zion", "Luka", "Savnt", "Pure 759", "Cario", "Taro", "Aeon-FFD", "Kokova", "Mael", "Ensiferum","Force Unleashed", "Sun Rising", "Unceasing", "Transmutate", "Calculated", "Elemental Power", "Overdrive", "Well Oiled", "Focus", "Inner Fire", "Multiply", "Weapons Deal", "Chromatic Alloy", "Grenadier", "Forged By Fire", "Status Extender ", "Core: Drone Zeal", "Core: HE-Ammo", "Spider Mines", "Missile Drone", "Dragon’s Masterkey", "Acid Grenade", "LMG Sentry Turret", "Seismic Resonator","Drill", "Killer", "Take Cover", "Scarred", "Madness", "Hold Breath", "Pack A Punch", "On The Edge", "Press The Attack", "Field Rat0ons", "Drone Mod", "Specialized Ammo", "Charge", "Routine", "Weapon Drop", "Core: Looter", "Core: Squad Leader", "Core: Suppression", "Core: Commando", "Onslaught System", "Road Flare", "Hard Light Cover", "Special Ammo Supply", "Stim Pack", "Plasma Grenade", "Reverbing Blade", "Against The Odds", "Die Hard", "Blood Borne", "Keeping Cool", "Freeze!", "Power Tuning", "DMR Conversion", "Perfection", "Keeping Distance", "Discipline", "Shadow Dance", "Backstab", "Evasive Maneuvers", "Switch Position", "Head Hunter", "Core: Spotter", "Core: Professional", "Targeting Laser", "Scoundrel’s Dagger", "Decoy", "Smoke Grenade", "Laser Mine", "Flare Gun", "’Helsing’ Power Bolt", "TP Grenade Flash", "Push Forward", "Wicked", "Berserk", "Bits And Pieces", "Scrap Plating", "Stimulants", "Shield Overclock", "Weapon Mastery", "Enrage", "Fortify Position", "Shielded", "Aegis MK5 Platinum", "Into Battle", "Recovery", "Warmup", "I-Frame", "Core: Charge", "Core: Unyielding", "Battlecry Module", "Breaching Charge", "RV Rebuke System", "Shieldburst", "Tomahawk", "Auto Taser", "Stun Grenade","Field Supply", "Lifeblood", "Cell Replacer", "Unidentified Potion", "Overdose", "Methadone","Health Vial", "Random Module"]
        ShownPistols = ["TEC-9.95 Personal","P25 Overdrive","Titanium Eagle","Auto 9/45","57 Fusion Classic","PPQ-H Laser Pistol","Kaida Laser Pistol","Desert Eagle .50","Kaida Model H","Last Breath","Master Chief","XM2 Coil Pistol","G17 Undercover","PXS Covert Ops","P33 Compact"]

        #variables start here
        
        #todo:x local mod save file, (hopefully for adding memory to the project)
        #Modsave = "C:/Users/"+username+"/AppData/Local/Synthetik/MODSAVE.txt"
        #the default current class. should be changed to read the value from the Mod save, eventually.
        self.currentclass = "10"
       
        #Tokens already in the save
        self.Tokens = []
        #items & perks in loadout
        self.Perks = []

        #browse_files helps the user find their file. 
        def browse_files(save_filename, temp_save_filename):
            filepath = save_filename.rsplit("/",1)[0]
            new_save_filename = filedialog.askopenfilename(initialdir="/", title="Select a file", filetypes=(("Save files","*.sav*"),("All files","*.*")))
            if new_save_filename:
                save_filename = new_save_filename
                filepath = save_filename.rsplit("/",1)[0]
                temp_save_filename = filepath +"/TEMPORARYSAVE.txt"
            print(filepath[0])

            return save_filename, temp_save_filename

        #this just makes sure the save file is where it should be, otherwise it calls browsefiles.
        if not os.path.exists(filename):
            messagebox.showinfo('Synthetik','Sorry, your save file is not where I thought it would be! Could you please find it for me?')
            filename, tfilename = browse_files(filename, tfilename)

        #whenever 
        def Change_class(subclass):
            #change 'global' current class to whatever subclass was selected
            self.currentclass = subclass
            #open the save file
            with open(filename, "r") as Save:
                for line in Save:
                    if line.startswith("perkslot"):
                        #for every slot needed in the loadout of the current class
                        for num in Save_Loadout:
                            if line.startswith("perkslot"+num+"class"+ self.currentclass):
                                #find the perk's name, and append it to the list of perks.
                                P = re.search("obj_\w+(\d+)?_\w+",line).group()
                                self.Perks.append(P)
                            else:
                                continue
                    #find all tokens.
                    elif line.startswith("wbonus") or line.startswith("wplus") or line.startswith("wminus"):
                        self.Tokens.append(line)
                    elif line.startswith("ibonus") or line.startswith("iplus") or line.startswith("iminus"):
                        self.Tokens.append(line)
                    else:
                        continue
            return
        

        Change_class("10")
        



if __name__ == "__main__":
    root = Root()
    root.mainloop()