"""Tkinter front end for the Beam Designer."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import csv
import textwrap

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from beam_calculations import Load, analyze_beam

PAPER, WHITE, INK, NAVY = "#EAF2FA", "#FFFFFF", "#23272F", "#23395B"
TEAL, BLUE, ORANGE = "#2A7886", "#0072B2", "#D55E00"


class BeamDesigner:
    def __init__(self, root):
        self.root = root
        root.title("Beam Designer")
        root.geometry("1360x900")
        root.minsize(900, 650)
        root.configure(bg=PAPER)
        self.current_file = None
        self.latest_results = None
        self.loads = [dict(kind="uniform", magnitude="2", direction="Downward", start="0", end="15")]
        self.vars = {}
        self._make_styles()
        self._build_menu()
        header = ttk.Frame(root, style="Header.TFrame", padding=(16, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Beam Designer", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Beam response and preliminary design checks", style="Sub.TLabel").pack(side="left", padx=18)
        self.mascot = tk.Canvas(header, width=56, height=48, bg=NAVY, highlightthickness=0)
        self.mascot.pack(side="right")
        self._draw_mascot(0)

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.workspace = ttk.Frame(self.tabs, style="App.TFrame")
        self.game_tab = ttk.Frame(self.tabs, style="App.TFrame")
        self.tabs.add(self.workspace, text="Beam analysis")
        self.tabs.add(self.game_tab, text="Cougar pinball")
        self._build_workspace()
        self._build_pinball()
        self.refresh()

    def _make_styles(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except tk.TclError: pass
        s.configure("App.TFrame", background=PAPER)
        s.configure("Header.TFrame", background=NAVY)
        s.configure("Title.TLabel", background=NAVY, foreground="white", font=("Georgia", 20, "bold"))
        s.configure("Sub.TLabel", background=NAVY, foreground="#D9E2EF", font=("Arial", 10))
        s.configure("Panel.TFrame", background=WHITE, relief="solid", borderwidth=1)
        s.configure("Section.TLabel", background=WHITE, foreground=NAVY, font=("Georgia", 12, "bold"))
        s.configure("TLabel", background=WHITE, foreground=INK, font=("Arial", 9))
        s.configure("TButton", padding=5)

    def _build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._save_design)
        file_menu.add_command(label="Open…", accelerator="Ctrl+O", command=self._open_design)
        menu.add_cascade(label="File", menu=file_menu)
        menu.add_command(label="Export results", command=self._export_results)
        menu.add_command(label="Calculation sheet (PDF)", command=self._export_calculation_sheet)
        self.root.configure(menu=menu)
        self.root.bind("<Control-s>", lambda _event: self._save_design())
        self.root.bind("<Control-o>", lambda _event: self._open_design())

    def _read_design(self):
        support = self.vars["support"].get()
        span = float(self.vars["span"].get())
        E, S, I, Fb = (float(self.vars[k].get()) for k in ("E", "S", "I", "Fb"))
        member = self.vars["member"].get()
        limit_type = self.vars["limit_type"].get()
        custom_limit = float(self.vars["custom_limit"].get()) if limit_type == "Custom" else None
        loads = []
        for item in self.loads:
            common = {"kind": item["kind"], "magnitude": float(item["magnitude"]), "direction": item["direction"]}
            if item["kind"] == "point": common["position"] = float(item["position"])
            elif item["kind"] == "uniform":
                common["start"] = float(item["start"]); common["end"] = float(item["end"])
            else: raise ValueError("Unknown load type")
            loads.append(common)
        analyze_beam(support, span, [Load(**item) for item in loads], E, I, S, Fb, custom_limit)
        return {"version": 1, "support": support, "span_ft": span, "member": member,
                "properties": {"E_ksi": E, "S_in3": S, "I_in4": I, "allowable_ksi": Fb},
                "deflection_limit": {"type": limit_type, "custom_in": custom_limit}, "loads": loads}

    @staticmethod
    def _validate_design(data):
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Unsupported or invalid beam file version")
        if data.get("support") not in ("Simply supported", "Cantilever"):
            raise ValueError("Invalid support type in file")
        if data.get("member") not in ("W18x35 (example properties)", "Custom properties"):
            raise ValueError("Invalid section selection in file")
        limit = data.get("deflection_limit")
        props = data.get("properties")
        raw_loads = data.get("loads")
        if not isinstance(limit, dict) or limit.get("type") not in ("L / 360", "Custom"):
            raise ValueError("Invalid deflection limit in file")
        if not isinstance(props, dict) or not isinstance(raw_loads, list):
            raise ValueError("Missing member properties or load list")
        loads=[]
        for item in raw_loads:
            if not isinstance(item, dict): raise ValueError("Invalid load entry")
            kind=item.get("kind")
            loads.append(Load(kind, float(item["magnitude"]), item["direction"],
                              position=float(item.get("position",0)),
                              start=float(item.get("start",0)), end=float(item.get("end",0))))
        custom = float(limit["custom_in"]) if limit["type"] == "Custom" else None
        analyze_beam(data["support"], float(data["span_ft"]), loads,
                     float(props["E_ksi"]), float(props["I_in4"]), float(props["S_in3"]),
                     float(props["allowable_ksi"]), custom)
        return data

    def _save_design(self):
        try: data = self._read_design()
        except (ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("Cannot save beam", f"Check the beam inputs before saving.\n\n{exc}", parent=self.root); return
        path = self.current_file or filedialog.asksaveasfilename(
            parent=self.root, title="Save beam design", defaultextension=".json",
            filetypes=[("Beam design (JSON)", "*.json"), ("All files", "*.*")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as stream: json.dump(data, stream, indent=2)
            self.current_file = path
            self.root.title(f"Beam Designer — {os.path.basename(path)}")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self.root)

    def _open_design(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open beam design",
            filetypes=[("Beam design (JSON)", "*.json"), ("All files", "*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as stream: data = self._validate_design(json.load(stream))
            self.vars["support"].set(data["support"]); self.vars["span"].set(data["span_ft"])
            self.vars["member"].set(data["member"])
            props=data["properties"]
            for key, source in (("E","E_ksi"),("S","S_in3"),("I","I_in4"),("Fb","allowable_ksi")):
                self.vars[key].set(props[source])
            limit=data["deflection_limit"]
            self.vars["limit_type"].set(limit["type"])
            if limit["custom_in"] is not None: self.vars["custom_limit"].set(limit["custom_in"])
            self.loads=[]
            for item in data["loads"]:
                load={key:str(item[key]) for key in item}
                self.loads.append(load)
            self.current_file=path
            self._render_load_editors(); self.refresh()
            self.root.title(f"Beam Designer — {os.path.basename(path)}")
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("Open failed", f"Could not open this beam file.\n\n{exc}", parent=self.root)

    def _var(self, name, value):
        v = tk.StringVar(value=str(value)); self.vars[name] = v
        return v

    def _build_workspace(self):
        self.workspace.columnconfigure(1, weight=1); self.workspace.rowconfigure(0, weight=1)
        left = ttk.Frame(self.workspace, style="Panel.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left.configure(width=340); left.grid_propagate(False)
        right = ttk.Frame(self.workspace, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1); right.rowconfigure(2, weight=1)
        ttk.Label(left, text="Model inputs", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self._choice(left, "Support", "support", ["Simply supported", "Cantilever"])
        self._entry(left, "Span (ft)", "span", "30")
        self._choice(left, "Member", "member", ["W18x35 (example properties)", "Custom properties"])
        self._entry(left, "Elastic modulus E (ksi)", "E", "29000")
        self._entry(left, "Section modulus S (in³)", "S", "39.4")
        self._entry(left, "Moment of inertia I (in⁴)", "I", "510")
        self._entry(left, "Allowable bending Fb (ksi)", "Fb", "36")
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Loads", style="Section.TLabel").pack(anchor="w")
        self.load_frame = ttk.Frame(left, style="Panel.TFrame"); self.load_frame.pack(fill="x", pady=5)
        buttons = ttk.Frame(left, style="Panel.TFrame"); buttons.pack(fill="x")
        ttk.Button(buttons, text="+ Point load", command=lambda:self.add_load("point")).pack(side="left")
        ttk.Button(buttons, text="+ Uniform load", command=lambda:self.add_load("uniform")).pack(side="left", padx=4)
        self.load_editor = []
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Deflection limit", style="Section.TLabel").pack(anchor="w")
        self._choice(left, "Limit type", "limit_type", ["L / 360", "Custom"])
        self._entry(left, "Custom limit (in)", "custom_limit", "1.0")
        ttk.Label(left, text="Multiple loads supported. Downward loads are negative.", wraplength=300).pack(anchor="w", pady=8)
        for key in ("support", "span", "E", "S", "I", "Fb", "limit_type", "custom_limit"):
            self.vars[key].trace_add("write", lambda *_: self.refresh())

        beam_panel = ttk.Frame(right, style="Panel.TFrame", padding=8); beam_panel.grid(row=0,column=0,sticky="ew",pady=(0,8))
        ttk.Label(beam_panel,text="Beam and applied loads",style="Section.TLabel").pack(anchor="w")
        self.beam_fig=Figure(figsize=(8,1.7),dpi=90); self.beam_ax=self.beam_fig.add_subplot(111)
        self.beam_canvas=FigureCanvasTkAgg(self.beam_fig,master=beam_panel); self.beam_canvas.get_tk_widget().pack(fill="x")
        result_bar=ttk.Frame(right,style="App.TFrame"); result_bar.grid(row=1,column=0,sticky="ew",pady=(0,5))
        result_bar.columnconfigure(0,weight=1)
        self.reaction_label=ttk.Label(result_bar,text="",style="Section.TLabel"); self.reaction_label.grid(row=0,column=0,sticky="w")
        self.plot_frame=ttk.Frame(right,style="App.TFrame"); self.plot_frame.grid(row=2,column=0,sticky="nsew")
        self.plot_frame.columnconfigure((0,1),weight=1); self.plot_frame.rowconfigure((0,1),weight=1)
        self.fig=Figure(figsize=(8,5),dpi=90,facecolor=WHITE)
        self.axes=[self.fig.add_subplot(221),self.fig.add_subplot(222),self.fig.add_subplot(223),self.fig.add_subplot(224)]
        self.plot_canvas=FigureCanvasTkAgg(self.fig,master=self.plot_frame); self.plot_canvas.get_tk_widget().grid(row=0,column=0,columnspan=2,sticky="nsew")
        self.status=ttk.Label(right,text="",wraplength=850); self.status.grid(row=3,column=0,sticky="w",pady=6)
        self._render_load_editors()

    def _choice(self,parent,label,key,values):
        row=ttk.Frame(parent,style="Panel.TFrame"); row.pack(fill="x",pady=2)
        ttk.Label(row,text=label,width=22).pack(side="left")
        box=ttk.Combobox(row,textvariable=self._var(key,values[0]),values=values,state="readonly",width=20); box.pack(side="left",fill="x",expand=True)
        if key=="member": box.bind("<<ComboboxSelected>>",self._member_changed)

    def _entry(self,parent,label,key,value):
        row=ttk.Frame(parent,style="Panel.TFrame"); row.pack(fill="x",pady=2)
        ttk.Label(row,text=label,width=22).pack(side="left")
        ttk.Entry(row,textvariable=self._var(key,value),width=12).pack(side="left",fill="x",expand=True)

    def _member_changed(self,*_):
        if self.vars["member"].get().startswith("W18"):
            for k,v in (("E","29000"),("S","39.4"),("I","510"),("Fb","36")): self.vars[k].set(v)

    def add_load(self,kind):
        if kind=="point": self.loads.append(dict(kind=kind,magnitude="5",direction="Downward",position="15"))
        else: self.loads.append(dict(kind=kind,magnitude="0.5",direction="Downward",start="0",end=self.vars["span"].get()))
        self._render_load_editors(); self.refresh()

    def _render_load_editors(self):
        for w in self.load_frame.winfo_children(): w.destroy()
        self.load_editor=[]
        for i,load in enumerate(self.loads):
            card=ttk.Frame(self.load_frame,style="Panel.TFrame"); card.pack(fill="x",pady=3)
            title=ttk.Frame(card,style="Panel.TFrame"); title.pack(fill="x")
            ttk.Label(title,text=f"{i+1}. {load['kind'].title()} load",style="Section.TLabel").pack(side="left")
            ttk.Button(title,text="Remove",command=lambda j=i:self.remove_load(j)).pack(side="right")
            keys=[("Magnitude (kip/ft)" if load['kind']=="uniform" else "Magnitude (kip)","magnitude")]
            keys.append(("Direction","direction"))
            keys += ([ ("Start (ft)","start"),("End (ft)","end") ] if load['kind']=="uniform" else [("Position (ft)","position")])
            for label,key in keys:
                row=ttk.Frame(card,style="Panel.TFrame"); row.pack(fill="x")
                ttk.Label(row,text=label,width=17).pack(side="left")
                if key=="direction":
                    v=tk.StringVar(value=load[key]); widget=ttk.Combobox(row,textvariable=v,values=["Downward","Upward"],state="readonly",width=12)
                else:
                    v=tk.StringVar(value=load[key]); widget=ttk.Entry(row,textvariable=v,width=14)
                widget.pack(side="left",fill="x",expand=True)
                v.trace_add("write",lambda *_args,j=i,k=key,var=v:self._load_changed(j,k,var.get()))

    def _load_changed(self,i,key,value):
        if i<len(self.loads): self.loads[i][key]=value; self.refresh()
    def remove_load(self,i): self.loads.pop(i); self._render_load_editors(); self.refresh()

    def refresh(self):
        if not hasattr(self,"axes"): return
        try:
            span=float(self.vars["span"].get()); E=float(self.vars["E"].get()); I=float(self.vars["I"].get()); S=float(self.vars["S"].get()); Fb=float(self.vars["Fb"].get())
            loads=[]
            for d in self.loads:
                if d["kind"]=="point": loads.append(Load("point",float(d["magnitude"]),d["direction"],position=float(d["position"])))
                else: loads.append(Load("uniform",float(d["magnitude"]),d["direction"],start=float(d["start"]),end=float(d["end"])))
            lim=float(self.vars["custom_limit"].get()) if self.vars["limit_type"].get()=="Custom" else None
            r=analyze_beam(self.vars["support"].get(),span,loads,E,I,S,Fb,lim)
        except (ValueError,TypeError) as e:
            self.latest_results=None
            self.status.configure(text=f"Check inputs: {e}",foreground="#9B2C20"); return
        self.latest_results=r
        self._draw_beam(span)
        self.reaction_label.configure(text=f"Reactions: left {r.reaction_left_kip:.3f} kip   |   right {r.reaction_right_kip:.3f} kip")
        titles=[("Shear V(x)",r.shear_kip,"kip",TEAL),("Moment M(x)",r.moment_kip_ft,"kip-ft",BLUE),("Deflection v(x)",r.deflection_in,"in",ORANGE)]
        for ax,(title,y,unit,color) in zip(self.axes[:3],titles):
            ax.clear(); ax.plot(r.x_ft,y,color=color,lw=2); ax.axhline(0,color="#aab2ba",lw=.7); ax.set_title(title,loc="left",color=NAVY); ax.set_xlabel("Position x (ft)"); ax.set_ylabel(unit); ax.grid(alpha=.18)
            ex=r.extrema["shear" if title.startswith("Shear") else "moment" if title.startswith("Moment") else "deflection"]
            ax.text(.99,.97,f"max {ex['max']:.3f} at {ex['max_x_ft']:.2f} ft\nmin {ex['min']:.3f} at {ex['min_x_ft']:.2f} ft",transform=ax.transAxes,ha="right",va="top",fontsize=7)
        ax=self.axes[3]; ax.clear(); ax.axis("off")
        defl=float(max(abs(r.deflection_in)))
        bend_ok=r.bending_stress_ksi<=Fb; defl_ok=defl<=r.deflection_limit_in
        ax.text(.04,.9,"Design checks",fontsize=12,color=NAVY,weight="bold")
        ax.text(.04,.67,f"Bending: {'PASS' if bend_ok else 'FAIL'}  |  {r.bending_stress_ksi:.3f} / {Fb:.3f} ksi",fontsize=10,color="#23623a" if bend_ok else "#9b2c20")
        ax.text(.04,.43,f"Deflection: {'PASS' if defl_ok else 'FAIL'}  |  {defl:.4f} / {r.deflection_limit_in:.4f} in",fontsize=10,color="#23623a" if defl_ok else "#9b2c20")
        ax.text(.04,.17,"Shear strength is not checked.",fontsize=9,color=INK)
        self.fig.tight_layout(); self.plot_canvas.draw_idle()
        self.status.configure(text="Analysis updated. Educational design aid; verify engineering assumptions before use.",foreground=INK)

    def _export_results(self):
        if self.latest_results is None:
            messagebox.showerror("Cannot export results", "Enter valid beam inputs before exporting.", parent=self.root)
            return
        path=filedialog.asksaveasfilename(parent=self.root,title="Export beam results",
            defaultextension=".csv",filetypes=[("CSV file (Excel)","*.csv"),("All files","*.*")])
        if not path: return
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as stream:
                writer=csv.writer(stream)
                writer.writerow(["x (ft)","V (kip)","M (kip-ft)","v (in)"])
                r=self.latest_results
                writer.writerows(zip(r.x_ft,r.shear_kip,r.moment_kip_ft,r.deflection_in))
            self.status.configure(text=f"Results exported to {os.path.basename(path)}",foreground=INK)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)

    def _export_calculation_sheet(self):
        if self.latest_results is None:
            messagebox.showerror("Cannot create calculation sheet", "Enter valid beam inputs before exporting.", parent=self.root)
            return
        path=filedialog.asksaveasfilename(parent=self.root,title="Save calculation sheet",
            defaultextension=".pdf",filetypes=[("PDF document","*.pdf"),("All files","*.*")])
        if not path: return
        try:
            data=self._read_design(); r=self.latest_results
            load_text=[]
            for i,load in enumerate(data["loads"],1):
                if load["kind"]=="point":
                    load_text.append(f"{i}: point {load['magnitude']:g} kip {load['direction'].lower()} at {load['position']:g} ft")
                else:
                    load_text.append(f"{i}: uniform {load['magnitude']:g} kip/ft {load['direction'].lower()} from {load['start']:g} to {load['end']:g} ft")
            limit_text=(f"L/360 = {r.deflection_limit_in:.4f} in" if data["deflection_limit"]["type"]=="L / 360"
                        else f"Custom = {r.deflection_limit_in:.4f} in")
            p=data["properties"]
            info=(f"Support: {data['support']}    Span: {data['span_ft']:g} ft    Section: {data['member']}\n"
                  f"E: {p['E_ksi']:g} ksi    S: {p['S_in3']:g} in^3    I: {p['I_in4']:g} in^4    Allowable Fb: {p['allowable_ksi']:g} ksi\n"
                  f"Deflection limit: {limit_text}\nLoads: " + ("; ".join(load_text) if load_text else "None"))
            info_lines="\n".join(textwrap.wrap(info, width=168, break_long_words=False, break_on_hyphens=False))
            line_count=info_lines.count("\n")+1
            chart_top=max(.60,.84-line_count*.022)
            figure=Figure(figsize=(11.7,8.3),facecolor="white")
            figure.text(.045,.975,"BYU",ha="left",va="top",fontsize=17,weight="bold",color=NAVY)
            figure.text(.5,.975,"BEAM DESIGN CALCULATION SHEET",ha="center",va="top",fontsize=15,weight="bold",color=NAVY)
            figure.text(.045,.925,info_lines,ha="left",va="top",fontsize=max(6,9-line_count*.12),color=INK,family="sans-serif")
            bend_ok=r.bending_stress_ksi<=float(self.vars["Fb"].get())
            deflection=float(max(abs(r.deflection_in)))
            defl_ok=deflection<=r.deflection_limit_in
            summary=(f"Reactions: left {r.reaction_left_kip:.3f} kip; right {r.reaction_right_kip:.3f} kip     "
                     f"Bending: {'PASS' if bend_ok else 'FAIL'} ({r.bending_stress_ksi:.3f} / {float(self.vars['Fb'].get()):.3f} ksi)     "
                     f"Deflection: {'PASS' if defl_ok else 'FAIL'} ({deflection:.4f} / {r.deflection_limit_in:.4f} in)")
            figure.text(.045,chart_top-.035,summary,ha="left",va="top",fontsize=9,color=INK)
            colors=[TEAL,BLUE,ORANGE]
            series=[(r.shear_kip,"Shear V(x)","V (kip)"),(r.moment_kip_ft,"Moment M(x)","M (kip-ft)"),(r.deflection_in,"Deflection v(x)","v (in)")]
            bottom=.12
            height=max(.28,chart_top-.20)
            for i,(values,title,ylabel) in enumerate(series):
                ax=figure.add_axes([.07+i*.31,bottom,.27,height])
                ax.plot(r.x_ft,values,color=colors[i],lw=1.7)
                ax.axhline(0,color="#9aa4ad",lw=.6)
                ax.set_title(title,fontsize=10,color=NAVY,loc="left")
                ax.set_xlabel("Position x (ft)",fontsize=8); ax.set_ylabel(ylabel,fontsize=8)
                ax.tick_params(labelsize=7); ax.grid(alpha=.18)
            figure.text(.97,.035,"Educational design aid",ha="right",fontsize=7,color="#69717b")
            with PdfPages(path) as pdf:
                pdf.savefig(figure,bbox_inches="tight")
            self.status.configure(text=f"Calculation sheet saved to {os.path.basename(path)}",foreground=INK)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("PDF export failed", str(exc), parent=self.root)

    def _draw_beam(self,span):
        ax=self.beam_ax; ax.clear(); ax.set_xlim(-.05*span,1.05*span); ax.set_ylim(-1.5,2.5); ax.axis("off")
        # Low contrast watermark behind the model.
        ax.text(.5,.53,"BYU",transform=ax.transAxes,ha="center",va="center",fontsize=48,weight="bold",color="#23395B",alpha=.07,zorder=0)
        ax.plot([0,span],[0,0],color=NAVY,lw=7,zorder=2)
        if self.vars["support"].get()=="Cantilever":
            ax.plot([0,0],[-.45,.5],color=NAVY,lw=2); ax.fill_betweenx([-.45,.5],-.15,0,color=NAVY,alpha=.4)
        else:
            ax.scatter([0,span],[-.35,-.35],marker="^",s=120,color=NAVY)
        for d in self.loads:
            try:
                m=float(d["magnitude"]); up=d["direction"]=="Upward"
                if d["kind"]=="point":
                    x=float(d["position"]); ax.annotate("",(x,.12 if up else -.12),(x,1.1 if up else -1.1),arrowprops=dict(arrowstyle="->",color=ORANGE,lw=1.5)); ax.text(x,1.2 if up else -1.35,f"{m:g} kip",ha="center",color=ORANGE,fontsize=8)
                else:
                    a,b=sorted((float(d["start"]),float(d["end"]))); y=.95 if up else -.95; ax.plot([a,b],[y,y],color=ORANGE)
                    for x in [a+(b-a)*j/8 for j in range(9)]: ax.annotate("",(x,.08 if up else -.08),(x,y),arrowprops=dict(arrowstyle="->",color=ORANGE,lw=1))
                    ax.text((a+b)/2,y+(0.12 if up else -0.25),f"{m:g} kip/ft",ha="center",color=ORANGE,fontsize=8)
            except ValueError: pass
        ax.text(span/2,-.55,f"{span:g} ft",ha="center",va="top",fontsize=9)
        self.beam_fig.tight_layout(); self.beam_canvas.draw_idle()

    def _draw_mascot(self,step):
        self.mascot.delete("all"); x=18+(step%4)*5
        self.mascot.create_oval(x,13,x+26,39,fill="#174A7E",outline="#9DB7D1",width=2)
        self.mascot.create_oval(x+6,21,x+10,25,fill="white",outline="")
        self.mascot.create_oval(x+17,21,x+21,25,fill="white",outline="")
        self.mascot.create_polygon(x+10,31,x+16,31,x+13,34,fill="#D55E00",outline="")
        self.root.after(500,self._draw_mascot,step+1)

    def _build_pinball(self):
        top=ttk.Frame(self.game_tab,style="App.TFrame",padding=10); top.pack(fill="x")
        ttk.Label(top,text="Cougar Pinball",style="Section.TLabel").pack(side="left")
        self.score=0; self.balls=3; self.ball=None; self.left_flipper=False; self.right_flipper=False
        self.bumper_contacts=set()
        self.score_label=ttk.Label(top,text="Score: 0   Balls: 3"); self.score_label.pack(side="right")
        self.board=tk.Canvas(self.game_tab,width=720,height=520,bg="#111b30",highlightthickness=3,highlightbackground=NAVY)
        self.board.pack(padx=20,pady=10,expand=True)
        controls=ttk.Frame(self.game_tab,style="App.TFrame"); controls.pack(fill="x",padx=20,pady=8)
        ttk.Button(controls,text="Launch ball (Space)",command=self._launch).pack(side="left")
        self.game_status=ttk.Label(controls,text="← / → to flip; click left/right side also works."); self.game_status.pack(side="left",padx=12)
        self.board.bind("<Button-1>",self._pointer_flipper); self.board.bind("<ButtonRelease-1>",lambda e:self._release_flippers())
        self.root.bind_all("<KeyPress-Left>",lambda e:self._set_flipper("left",True)); self.root.bind_all("<KeyRelease-Left>",lambda e:self._set_flipper("left",False))
        self.root.bind_all("<KeyPress-Right>",lambda e:self._set_flipper("right",True)); self.root.bind_all("<KeyRelease-Right>",lambda e:self._set_flipper("right",False))
        self.root.bind_all("<space>",lambda e:self._launch())
        self._paint_pinball()

    def _launch(self):
        if self.ball is None and self.balls>0:
            self.balls-=1; self.ball=[570.,430.,-3.8,-8.,9.]; self.bumper_contacts.clear(); self.game_status.configure(text="Ball in play")
    def _set_flipper(self,side,state):
        if self.tabs.index(self.tabs.select())==1: setattr(self,side+"_flipper",state)
    def _pointer_flipper(self,event): self._set_flipper("left" if event.x<360 else "right",True)
    def _release_flippers(self): self.left_flipper=False; self.right_flipper=False

    @staticmethod
    def _circle_segment_contact(x,y,r,x1,y1,x2,y2):
        """Return a collision normal and corrected ball position for a paddle hit."""
        dx,dy=x2-x1,y2-y1
        length2=dx*dx+dy*dy
        t=0 if length2==0 else max(0,min(1,((x-x1)*dx+(y-y1)*dy)/length2))
        px,py=x1+t*dx,y1+t*dy
        nx,ny=x-px,y-py
        distance=(nx*nx+ny*ny)**.5
        paddle_radius=7
        if distance>=r+paddle_radius: return None
        if distance<1e-8:
            length=max(1,(dx*dx+dy*dy)**.5)
            nx,ny=-dy/length,dx/length
            if ny>0: nx,ny=-nx,-ny
            distance=0
        else:
            nx,ny=nx/distance,ny/distance
        return (nx,ny,px+nx*(r+paddle_radius),py+ny*(r+paddle_radius))

    def _paint_pinball(self):
        c=self.board; c.delete("all"); c.create_rectangle(95,30,625,490,outline="#8fb8e8",width=5)
        c.create_text(360,55,text="COUGAR PINBALL",fill="#f2c14e",font=("Arial",18,"bold"))
        bumpers=[(270,140,28),(450,140,28),(360,240,32),(245,300,20),(475,300,20)]
        for x,y,r in bumpers:
            c.create_oval(x-r,y-r,x+r,y+r,fill=BLUE,outline="white",width=2); c.create_text(x,y,text="BYU",fill="white",font=("Arial",10,"bold"))
        left_tip=(200,405) if self.left_flipper else (410,425)
        right_tip=(310,405) if self.right_flipper else (540,425)
        c.create_line(300,425,*left_tip,fill="white",width=13,capstyle="round")
        c.create_line(420,425,*right_tip,fill="white",width=13,capstyle="round")
        if self.ball:
            x,y,vx,vy,r=self.ball; vy+=.22; x+=vx; y+=vy
            if x<108 or x>612: vx=-vx*.85; x=min(612,max(108,x))
            if y<70: vy=abs(vy)
            touching=set()
            for idx,(bx,by,br) in enumerate(bumpers):
                dx,dy=x-bx,y-by; d=max(1e-8,(dx*dx+dy*dy)**.5)
                if d<r+br:
                    touching.add(idx)
                    nx,ny=dx/d,dy/d
                    x,y=bx+nx*(r+br+.5),by+ny*(r+br+.5)
                    velocity_toward=vx*nx+vy*ny
                    if velocity_toward<0: vx-=2*velocity_toward*nx; vy-=2*velocity_toward*ny
                    if idx not in self.bumper_contacts: self.score+=100
            self.bumper_contacts=touching
            for side,pivot,tip,active in (("left",(300,425),left_tip,self.left_flipper),("right",(420,425),right_tip,self.right_flipper)):
                contact=self._circle_segment_contact(x,y,r,*pivot,*tip)
                if contact:
                    nx,ny,x,y=contact
                    velocity_toward=vx*nx+vy*ny
                    if velocity_toward<0:
                        vx-=2*velocity_toward*nx; vy-=2*velocity_toward*ny
                    if active:
                        vy=-max(7.0,abs(vy)*0.9)
                        vx += 2.2 if side=="left" else -2.2
            if y>495:
                self.ball=None; self.game_status.configure(text="Ball lost. Launch the next one." if self.balls else "Game over. Launch to start again.")
            else:
                self.ball=[x,y,vx,vy,r]; c.create_oval(x-r,y-r,x+r,y+r,fill="#fff4cf",outline="white")
        self.score_label.configure(text=f"Score: {self.score}   Balls: {self.balls}")
        self.root.after(25,self._paint_pinball)


def main():
    root=tk.Tk(); BeamDesigner(root); root.mainloop()


if __name__=="__main__": main()
