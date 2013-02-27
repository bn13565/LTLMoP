#!/usr/bin/env python
# -*- coding: utf-8 -*-
# generated by wxGlade 0.6.3 on Sun Mar 27 21:05:20 2011

import wx
import wx.grid
import wx.lib.buttons, wx.lib.delayedresult
import sys, os, re, copy
import numpy
import threading

# Climb the tree to find out where we are
p = os.path.abspath(__file__)
t = ""
while t != "src":
    (p, t) = os.path.split(p)
    if p == "":
        print "I have no idea where I am; this is ridiculous"
        sys.exit(1)

sys.path.append(os.path.join(p,"src","lib"))

import fsa, project
import mapRenderer
from specCompiler import SpecCompiler

# begin wxGlade: extracode
# end wxGlade

class EnvDummySensorHandler:
    def __init__(self, parent):
        self.parent = parent

    def __getitem__(self, name):
        if name == "initializing_handler":
            return {}
        else:
            return compile("self.sensor_handler.getSensorValue('%s')" % name, "<string>", "eval")

    def __contains__(self, name):
        return True

    def getSensorValue(self, name):
        m = re.match('^bit(\d+)$', name)
        if m is not None:
            # Handle region encodings specially
            # bit0 is MSB
            bitnum = int(m.group(1))
            # from http://www.daniweb.com/software-development/python/code/216539
            bs = "{0:0>{1}}".format(bin(self.parent.current_region)[2:], self.parent.num_bits)
            return bs[bitnum]
        else:
            return self.parent.actuatorStates[name]

class EnvDummyActuatorHandler:
    def __init__(self, parent):
        self.parent = parent

    def __getitem__(self, name):
        if name == "initializing_handler":
            return {}
        else:
            return compile("self.actuator_handler.setActuator('%s', new_val)" % name, "<string>", "eval")

    def __contains__(self, name):
        return True

    def setActuator(self,name,val):
        self.parent.sensorStates[name] = val
        try:
            for btn in self.parent.env_buttons:
                if btn.GetLabelText() == name:
                    if int(val) == 1:
                        btn.SetBackgroundColour(wx.Colour(0, 255, 0))
                        btn.SetValue(True)
                    else:
                        btn.SetBackgroundColour(wx.Colour(255, 0, 0))
                        btn.SetValue(False)
                    break
        except AttributeError:
            pass # The buttons haven't been created yet

class DummyMotionHandler:
    def __init__(self):
        pass
    def gotoRegion(self,a,b):
        return True

class MopsyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MopsyFrame.__init__
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.mopsy_frame_statusbar = self.CreateStatusBar(1, 0)
        self.window_1 = wx.SplitterWindow(self, wx.ID_ANY, style=wx.SP_3D | wx.SP_BORDER)
        self.window_1_pane_1 = wx.Panel(self.window_1, wx.ID_ANY)
        self.history_grid = wx.grid.Grid(self.window_1_pane_1, wx.ID_ANY, size=(1, 1))
        self.window_1_pane_2 = wx.Panel(self.window_1, wx.ID_ANY)
        self.panel_1 = wx.Panel(self.window_1_pane_2, wx.ID_ANY, style=wx.SUNKEN_BORDER | wx.TAB_TRAVERSAL)
        self.label_1 = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Your goal:")
        self.label_goal = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Wait patiently for Mopsy to load")
        self.label_5 = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Current environment state:")
        self.label_6 = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Please choose your response:")
        self.label_movingto = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Moving to XXX ...")
        self.label_8 = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Actuator states:")
        self.label_9 = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "Internal propositions:")
        self.label_violation = wx.StaticText(self.window_1_pane_2, wx.ID_ANY, "", style=wx.ST_NO_AUTORESIZE)
        self.button_next = wx.Button(self.window_1_pane_2, wx.ID_ANY, "Execute Move >>")

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self.onButtonNext, self.button_next)
        # end wxGlade

        self.coreCalculationLock = threading.Lock()
        self.dest_region = None
        self.current_region = None
        self.regionsToHide = []
        self.actuatorStates = {}
        self.sensorStates = {}

        self.panel_1.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.mapBitmap = None

        # Load in the project and map
        self.mopsy_frame_statusbar.SetStatusText("Loading project...", 0)
        self.compiler = SpecCompiler(sys.argv[1])
        self.proj = copy.deepcopy(self.compiler.proj)
        self.proj.rfi = self.proj.loadRegionFile(decomposed=True)
        self.Bind(wx.EVT_SIZE, self.onResize, self)
        self.panel_1.Bind(wx.EVT_PAINT, self.onPaint)
        self.panel_1.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBG)
        self.panel_1.Bind(wx.EVT_LEFT_DOWN, self.onMapClick)
        self.onResize()

        self.proj.determineEnabledPropositions()

        # Parse specification so we can give feedback
        self.mopsy_frame_statusbar.SetStatusText("Parsing specification...", 0)
        self.compiler._decompose()
        self.spec, self.tracebackTree, response = self.compiler._writeLTLFile()
        self.compiler._writeSMVFile() # to update propList

        if self.proj.compile_options["parser"] == "slurp":
            # Add SLURP to path for import
            p = os.path.dirname(os.path.abspath(__file__))
            sys.path.append(os.path.join(p, "..", "etc", "SLURP"))
            global chunks_from_gentree, line_to_chunks
            from ltlbroom.specgeneration import chunks_from_gentree, line_to_chunks
            self.tracebackChunks = chunks_from_gentree(self.tracebackTree)

        # Load in counter-strategy automaton
        self.envDummySensorHandler = EnvDummySensorHandler(self)
        self.envDummyActuatorHandler = EnvDummyActuatorHandler(self)
        self.dummyMotionHandler = DummyMotionHandler()
        self.proj.sensor_handler, self.proj.actuator_handler, self.proj.h_instance = [None]*3

        self.mopsy_frame_statusbar.SetStatusText("Loading environment counter-strategy...", 0)
        self.num_bits = int(numpy.ceil(numpy.log2(len(self.proj.rfi.regions))))  # Number of bits necessary to encode all regions
        region_props = ["bit" + str(n) for n in xrange(self.num_bits)]

        self.env_aut = fsa.Automaton(self.proj)
        self.env_aut.sensor_handler = self.envDummySensorHandler
        self.env_aut.actuator_handler = self.envDummyActuatorHandler
        self.env_aut.motion_handler = self.dummyMotionHandler
        # We are being a little tricky here by just reversing the sensor and actuator propositions
        # to create a sort of dual of the usual automaton
        self.env_aut.loadFile(self.proj.getFilenamePrefix() + ".aut", self.proj.enabled_actuators + self.proj.all_customs + region_props, self.proj.enabled_sensors, [])

        self.env_aut.current_region = None

        # Find first state in counterstrategy that seeks to falsify the given liveness
        if len(sys.argv) > 2:
            desired_jx = int(sys.argv[2])
            
            for s in self.env_aut.states:
                rank_str = s.transitions[0].rank
                m = re.search(r"\(\d+,(-?\d+)\)", rank_str)
                if m is None:
                    print "ERROR: Error parsing jx in automaton.  Are you sure the spec is unrealizable?"
                    return
                jx = int(m.group(1))

                if jx == desired_jx:
                    self.env_aut.current_state = s
                    break

            if self.env_aut.current_state is None:
                print "ERROR: could not find state in counterstrategy to falsify sys goal #{}".format(desired_jx)
                return
        else:
            self.env_aut.current_state = self.env_aut.states[0]

        # Internal aut housekeeping (ripped from chooseInitialState; hacky)
        self.env_aut.last_next_states = []
        self.env_aut.next_state = None
        self.env_aut.next_region = None

        #self.env_aut.dumpStates([self.env_aut.current_state])

        # Set initial sensor values
        self.env_aut.updateOutputs()

        # Figure out what actuator/custom-prop settings the system should start with
        for k,v in self.env_aut.current_state.inputs.iteritems():
            # Skip any "bitX" region encodings
            if re.match('^bit\d+$', k): continue
            self.actuatorStates[k] = int(v)

        # Figure out what region the system should start from
        self.current_region = self.regionFromEnvState(self.env_aut.current_state)
        self.dest_region = self.current_region

        # Create all the sensor/actuator buttons
        self.env_buttons = [] # This will later hold our buttons
        self.act_buttons = [] # This will later hold our buttons
        self.cust_buttons = [] # This will later hold our buttons

        actprops = dict((k,v) for k,v in self.actuatorStates.iteritems() if k in self.proj.enabled_actuators)
        custprops = dict((k,v) for k,v in self.actuatorStates.iteritems() if k in self.proj.all_customs)

        self.populateToggleButtons(self.sizer_env, self.env_buttons, self.sensorStates)
        self.populateToggleButtons(self.sizer_act, self.act_buttons, actprops)
        self.populateToggleButtons(self.sizer_prop, self.cust_buttons, custprops)

        # Make the env buttons not clickable (TODO: maybe replace with non-buttons)
        #for b in self.env_buttons:
        #    b.Enable(False)

        # Set up the logging grid
        self.history_grid.SetDefaultCellFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, ""))
        self.history_grid.SetLabelFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, ""))

        colheaders = self.proj.enabled_sensors + ["Region"] + self.proj.enabled_actuators + self.proj.all_customs
        self.history_grid.CreateGrid(0,len(colheaders))
        for i,n in enumerate(colheaders):
            self.history_grid.SetColLabelValue(i, " " + n + " ")
            self.history_grid.SetColSize(i,-1)  # Auto-size
        self.history_grid.EnableEditing(False)


        # Put initial condition into log
        self.appendToHistory()

        # Start initial environment move
        # All transitionable states have the same env move, so just use the first
        if (len(self.env_aut.current_state.transitions) >=1 ):
            self.env_aut.updateOutputs(self.env_aut.current_state.transitions[0])

        self.label_movingto.SetLabel("Stay in region " + self.env_aut.getAnnotatedRegionName(self.current_region))

        self.showCurrentGoal()
        self.applySafetyConstraints()

    def showCurrentGoal(self):
        rank_str = self.env_aut.current_state.transitions[0].rank
        m = re.search(r"\(\d+,(-?\d+)\)", rank_str)
        if m is None:
            print "ERROR: Error parsing jx in automaton.  Are you sure the spec is unrealizable?"
            return
        jx = int(m.group(1))-1 # minus 1 to account for auto-added []<>true

        if jx < 0:
            print "WARNING: negative jx"
            return

        goal_ltl = self.spec['SysGoals'].split('\n')[jx].strip()
        
        if self.proj.compile_options["parser"] == "structured":
            spec_line_num = None
            for ltl_frag, line_num in self.compiler.LTL2SpecLineNumber.iteritems():
                if ltl_frag.strip("\n\t &") == goal_ltl:
                    spec_line_num = line_num
                    break

            if spec_line_num is None:
                print "ERROR: Couldn't find goal {!r} in LTL->spec mapping".format(ltl_frag)
                return

            goal_spec = self.compiler.proj.specText.split("\n")[spec_line_num-1]
        elif self.proj.compile_options["parser"] == "slurp":
            canonical_goal_ltl = goal_ltl.lstrip().rstrip("\n\t &")
            goal_ltl_clean = self.compiler.reversemapping[canonical_goal_ltl]
            chunks = line_to_chunks(goal_ltl_clean, self.tracebackChunks)
            goal_spec = '{} (Because you said "{}")'.format(chunks[0].explanation, chunks[0].input)
        else:
            print "Unsupported parser type:", self.proj.compile_options["parser"]
            # TODO: make all parsers have the same interface

        #print jx, goal_ltl, spec_line_num, goal_spec
        self.label_goal.SetLabel(goal_spec.strip())

    def regionFromEnvState(self, state):
        # adaptation of fsa.py's regionFromState, to work with env_aut
        r_num = 0
        for bit in range(self.num_bits):
            if (int(state.inputs["bit" + str(bit)]) == 1):
                # bit0 is MSB
                r_num += int(2**(self.num_bits-bit-1))

        return r_num
    
    def regionToBitEncoding(self, region_index):
        bs = "{0:0>{1}}".format(bin(region_index)[2:], self.num_bits)
        return {"bit{}".format(i):int(v) for i,v in enumerate(bs)}

    def applySafetyConstraints(self):
        # If there is no next state, this implies that the system has no possible move (including staying in place)
        if len(self.env_aut.current_state.transitions[0].inputs) == 0:
            self.label_violation.SetLabel("Checkmate: no possible system moves.")
            for b in self.act_buttons + self.cust_buttons + [self.button_next]:
                b.Enable(False)
            self.regionsToHide = [r.name for r in self.proj.rfi.regions]

            self.onResize() # Force map redraw
            return

        # Determine transitionable regions

        goable = []
        goable_states = []

        # Look for any transition states that agree with our current outputs (ignoring dest_region)
        for s in self.env_aut.current_state.transitions:
            okay = True
            for k,v in s.inputs.iteritems():
                # Skip any "bitX" region encodings
                if re.match('^bit\d+$', k): continue
                if int(v) != int(self.actuatorStates[k]):
                    okay = False
                    break
            if okay:
                goable.append(self.proj.rfi.regions[self.regionFromEnvState(s)].name)
                goable_states.append(s)

        region_constrained_goable_states = [s for s in goable_states if (self.regionFromEnvState(s) == self.dest_region)]
        if region_constrained_goable_states == []:
            self.label_violation.SetLabel("Invalid move...")
            self.showCore()
            self.button_next.Enable(False)
        else:
            self.label_violation.SetLabel("")
            self.button_next.Enable(True)

        self.regionsToHide = list(set([r.name for r in self.proj.rfi.regions])-set(goable))

        self.onResize() # Force map redraw

    def appendToHistory(self):
        self.history_grid.AppendRows(1)
        newvals = [self.sensorStates[s] for s in self.proj.enabled_sensors] + \
                  [self.env_aut.getAnnotatedRegionName(self.current_region)] + \
                  [self.actuatorStates[s] for s in self.proj.enabled_actuators] + \
                  [self.actuatorStates[s] for s in self.proj.all_customs]
        lastrow = self.history_grid.GetNumberRows()-1

        for i,v in enumerate(newvals):
            if v == 0:
                self.history_grid.SetCellValue(lastrow,i,"False")
                self.history_grid.SetCellBackgroundColour(lastrow,i,wx.Colour(255, 0, 0))
            elif v == 1:
                self.history_grid.SetCellValue(lastrow,i,"True")
                self.history_grid.SetCellBackgroundColour(lastrow,i,wx.Colour(0, 255, 0))
            else:
                self.history_grid.SetCellValue(lastrow,i,v)
        self.history_grid.ClearSelection()
        self.history_grid.AutoSizeRow(lastrow)
        self.history_grid.MakeCellVisible(lastrow,0)
        self.history_grid.ForceRefresh()
        self.mopsy_frame_statusbar.SetStatusText("Currently in step #"+str(lastrow+2), 0)


    def stateToLTL(self, state, use_next=False):
        def decorate_prop(prop, polarity):
            if int(polarity) == 0:
                prop = "!"+prop
            if use_next:
                prop = "next({})".format(prop)
            return prop
            
        sys_state = " & ".join([decorate_prop("s."+p, v) for p,v in state.inputs.iteritems()])
        env_state = " & ".join([decorate_prop("e."+p, v) for p,v in state.outputs.iteritems()])
        return env_state + " & " + sys_state

    def showCore(self):
        """
        Display the part of the spec that explains why you can't
        set your next outputs to the state currently selected.
        """

        wx.lib.delayedresult.startWorker(self.displayCoreMessage, self.calculateCore, daemon=True)

    def displayCoreMessage(self, result):
        result = result.get()
        if result is None:
            # We've fallen behind
            # TODO: Abort previous core calcs so we don't display stale data
            self.label_violation.SetLabel("Invalid move.")
        else:
            self.label_violation.SetLabel("Invalid move because it violates: " + " and ".join([repr(s) for s in result]))
            self.label_violation.Wrap(self.label_violation.GetSize()[0])

    def calculateCore(self):
        # Don't let simultaneous calculations occur if events are triggered too fast
        if not self.coreCalculationLock.acquire(False):
            print "WARNING: Skipping core calculation because already busy with one."
            return

        # TODO: actually cache trans CNF
        # TODO: support SLURP parser

        ltl_current = self.stateToLTL(self.env_aut.current_state).strip()
        next_state = copy.deepcopy(self.env_aut.current_state.transitions[0])
        next_state.inputs.update(self.actuatorStates)
        next_state.inputs.update(self.regionToBitEncoding(self.dest_region))
        ltl_next = self.stateToLTL(next_state, use_next=True).strip()
        ltl_topo = self.spec['Topo'].replace('\n','').replace('\t','').strip()
        ltl_trans = [s.strip() for s in self.spec['SysTrans'].split('\n')]
        # note: strip()s make canonical (i.e. terminate in &, no whitespace on either side)
        guilty_ltl = self.compiler.unsatCores(ltl_topo, ltl_current, [ltl_next] + ltl_trans, 1, 1)
        print "Guilty LTL: ", guilty_ltl

        guilty_spec = []
        if self.proj.compile_options["parser"] == "structured":
            if guilty_ltl is not None:
                for ltl_frag, line_num in self.compiler.LTL2SpecLineNumber.iteritems():
                    ltl_frags_canonical = [s.strip() for s in ltl_frag.replace("\t","").split('\n')]
                    if not set(guilty_ltl).isdisjoint(ltl_frags_canonical):
                        guilty_spec.append(self.compiler.proj.specText.split("\n")[line_num-1])
        elif self.proj.compile_options["parser"] == "slurp":
            for ltl_frag in guilty_ltl:
                canonical_ltl_frag = ltl_frag.lstrip().rstrip("\n\t &")
                try:
                    guilty_clean = self.compiler.reversemapping[canonical_ltl_frag]
                except KeyError:
                    print "WARNING: LTL fragment {!r} not found in canon_ltl->LTL mapping".format(canonical_ltl_frag)
                    continue

                chunks = line_to_chunks(guilty_clean, self.tracebackChunks)
                if chunks:
                    guilty_spec.append('{} (Because you said "{}")'.format(chunks[0].explanation.replace("'",""), chunks[0].input))
                else:
                    print "WARNING: Canonical LTL fragment {!r} not found in spec->LTL mapping".format(guilty_clean)

        if self.spec['Topo'].replace('\n','').replace('\t','').strip() in guilty_ltl:
            guilty_spec.append("(topological constraints)")
    
        print "Guilty Spec: ", guilty_spec

        self.coreCalculationLock.release()

        return guilty_spec

    def onMapClick(self, event):
        x = event.GetX()/self.mapScale
        y = event.GetY()/self.mapScale
        for i, region in enumerate(self.proj.rfi.regions):
            if region.objectContainsPoint(x, y):
                self.dest_region = i

                if self.dest_region == self.current_region:
                    self.label_movingto.SetLabel("Stay in region " + self.env_aut.getAnnotatedRegionName(self.proj.rfi.regions.index(region)))
                else:
                    self.label_movingto.SetLabel("Move to region " + self.env_aut.getAnnotatedRegionName(self.proj.rfi.regions.index(region)))

                self.applySafetyConstraints()
                break

        self.onResize() # Force map redraw
        event.Skip()

    def populateToggleButtons(self, target_sizer, button_container, items):
        for item_name, item_val in items.iteritems():
            # Create the new button and add it to the sizer
            button_container.append(wx.lib.buttons.GenToggleButton(self.window_1_pane_2, -1, item_name))
            target_sizer.Add(button_container[-1], 1, wx.EXPAND, 0)

            # Set the initial value as appropriate
            if int(item_val) == 1:
                button_container[-1].SetValue(True)
                button_container[-1].SetBackgroundColour(wx.Colour(0, 255, 0))
            else:
                button_container[-1].SetValue(False)
                button_container[-1].SetBackgroundColour(wx.Colour(255, 0, 0))

            button_container[-1].SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))

            self.window_1_pane_2.Layout() # Update the frame
            self.Refresh()

            # Bind to event handler
            #self.Bind(wx.EVT_TOGGLEBUTTON, self.sensorToggle, button_container[-1])
            self.Bind(wx.EVT_BUTTON, self.sensorToggle, button_container[-1])

    def sensorToggle(self, event):
        btn = event.GetEventObject()
        if btn in self.env_buttons:
            return

        #print btn.GetLabelText() + "=" + str(btn.GetValue())

        self.actuatorStates[btn.GetLabelText()] = int(btn.GetValue())

        # TODO: Button background colour doesn't show up very well
        if btn.GetValue():
            btn.SetBackgroundColour(wx.Colour(0, 255, 0))
        else:
            btn.SetBackgroundColour(wx.Colour(255, 0, 0))

        self.Refresh()
        self.applySafetyConstraints()

        event.Skip()

    def onResize(self, event=None):
        size = self.panel_1.GetSize()
        self.mapBitmap = wx.EmptyBitmap(size.x, size.y)
        if self.dest_region is not None:
            hl = [self.proj.rfi.regions[self.dest_region].name]
        else:
            hl = []

        self.mapScale = mapRenderer.drawMap(self.mapBitmap, self.proj.rfi, scaleToFit=True, drawLabels=True, memory=True, highlightList=hl, deemphasizeList=self.regionsToHide)

        self.Refresh()
        self.Update()

        if event is not None:
            event.Skip()

    def onPaint(self, event=None):
        if self.mapBitmap is None:
            return

        if event is None:
            dc = wx.ClientDC(self.panel_1)
        else:
            pdc = wx.AutoBufferedPaintDC(self.panel_1)
            try:
                dc = wx.GCDC(pdc)
            except:
                dc = pdc
            else:
                self.panel_1.PrepareDC(pdc)

        dc.BeginDrawing()

        # Draw background
        dc.DrawBitmap(self.mapBitmap, 0, 0)

        # Draw robot
        if self.current_region is not None:
            [x,y] = map(lambda x: int(self.mapScale*x), self.proj.rfi.regions[self.current_region].getCenter())
            dc.DrawCircle(x, y, 5)

        dc.EndDrawing()

        if event is not None:
            event.Skip()

    def onEraseBG(self, event):
        # Avoid unnecessary flicker by intercepting this event
        pass

    def __set_properties(self):
        # begin wxGlade: MopsyFrame.__set_properties
        self.SetTitle("Counter-Strategy Visualizer")
        self.SetSize((1024, 666))
        self.mopsy_frame_statusbar.SetStatusWidths([-1])
        # statusbar fields
        mopsy_frame_statusbar_fields = ["Loading..."]
        for i in range(len(mopsy_frame_statusbar_fields)):
            self.mopsy_frame_statusbar.SetStatusText(mopsy_frame_statusbar_fields[i], i)
        self.label_1.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.label_5.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.label_6.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, ""))
        self.label_violation.SetForegroundColour(wx.Colour(255, 0, 0))
        self.label_violation.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, ""))
        self.button_next.SetDefault()
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: MopsyFrame.__do_layout
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_3 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_4 = wx.BoxSizer(wx.VERTICAL)
        sizer_5 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_prop = wx.BoxSizer(wx.HORIZONTAL)
        sizer_act = wx.BoxSizer(wx.HORIZONTAL)
        sizer_6 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_env = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2.Add(self.history_grid, 1, wx.EXPAND, 2)
        self.window_1_pane_1.SetSizer(sizer_2)
        sizer_3.Add(self.panel_1, 1, wx.EXPAND, 0)
        sizer_3.Add((10, 20), 0, 0, 0)
        sizer_4.Add((20, 10), 0, 0, 0)
        sizer_4.Add(self.label_1, 0, 0, 0)
        sizer_4.Add(self.label_goal, 0, wx.LEFT | wx.TOP | wx.BOTTOM | wx.EXPAND, 5)
        sizer_4.Add(self.label_5, 0, 0, 0)
        sizer_4.Add(sizer_env, 1, wx.EXPAND, 0)
        sizer_4.Add((20, 10), 0, 0, 0)
        sizer_4.Add(self.label_6, 0, 0, 0)
        sizer_6.Add(self.label_movingto, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        sizer_6.Add((20, 20), 0, 0, 0)
        sizer_4.Add(sizer_6, 1, wx.EXPAND, 0)
        sizer_4.Add(self.label_8, 0, 0, 0)
        sizer_4.Add(sizer_act, 1, wx.EXPAND, 0)
        sizer_4.Add(self.label_9, 0, 0, 0)
        sizer_4.Add(sizer_prop, 1, wx.EXPAND, 0)
        sizer_4.Add((20, 20), 0, 0, 0)
        sizer_5.Add(self.label_violation, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 0)
        sizer_5.Add(self.button_next, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        sizer_5.Add((20, 20), 0, 0, 0)
        sizer_4.Add(sizer_5, 2, wx.EXPAND, 0)
        sizer_3.Add(sizer_4, 1, wx.EXPAND, 0)
        sizer_3.Add((10, 20), 0, 0, 0)
        self.window_1_pane_2.SetSizer(sizer_3)
        self.window_1.SplitHorizontally(self.window_1_pane_1, self.window_1_pane_2)
        sizer_1.Add(self.window_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        self.Layout()
        # end wxGlade
        self.sizer_env = sizer_env
        self.sizer_act = sizer_act
        self.sizer_prop = sizer_prop

    def onButtonNext(self, event): # wxGlade: MopsyFrame.<event_handler>
        # TODO: full safety check
        self.current_region = self.dest_region
        self.appendToHistory()
        self.env_aut.runIteration()

        ### Make environment move

        # All transitionable states have the same env move, so just use the first
        self.env_aut.updateOutputs(self.env_aut.current_state.transitions[0])
        self.label_movingto.SetLabel("Stay in region " + self.env_aut.getAnnotatedRegionName(self.current_region))
        self.showCurrentGoal()
        self.applySafetyConstraints()

        event.Skip()

# end of class MopsyFrame


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s [spec_file] ([desired_jx])" % sys.argv[0]
        sys.exit(-1)

    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    mopsy_frame = MopsyFrame(None, -1, "")
    app.SetTopWindow(mopsy_frame)
    mopsy_frame.Show()
    app.MainLoop()
