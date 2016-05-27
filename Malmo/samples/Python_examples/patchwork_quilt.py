# --------------------------------------------------------------------------------------------------------------------
# Copyright (C) Microsoft Corporation.  All rights reserved.
# --------------------------------------------------------------------------------------------------------------------
# Stress test of the maze decorator and mission lifecycle - populates the playing arean with 30,000 small (16x16) mazes,
# one at a time, and runs each mission for 1 second, recording commands and video.

import MalmoPython
import os
import errno
import random
import sys
import time
import json
import uuid

def GetMissionXML( current_seed, xorg, yorg, zorg, iteration ):
    return '''<?xml version="1.0" encoding="UTF-8" ?>
    <Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://ProjectMalmo.microsoft.com Mission.xsd">
        <About>
            <Summary>Tiny Maze #''' + str(iteration) + '''</Summary>
        </About>

        <ServerSection>
            <ServerInitialConditions>
                <Time>
                    <StartTime>14000</StartTime>
                    <AllowPassageOfTime>true</AllowPassageOfTime>
                </Time>
            </ServerInitialConditions>
            <ServerHandlers>
                <FlatWorldGenerator generatorString="3;7,220*1,5*3,2;3;,biome_1" />
                <MazeDecorator>
                    <SizeAndPosition length="16" width="16" xOrigin="''' + str(xorg) + '''" yOrigin="''' + str(yorg) + '''" zOrigin="''' + str(zorg) + '''" height="8"/>
                    <GapProbability variance="0.4">0.5</GapProbability>
                    <Seed>''' + str(current_seed) + '''</Seed>
                    <MaterialSeed>random</MaterialSeed>
                    <AllowDiagonalMovement>false</AllowDiagonalMovement>
                    <StartBlock fixedToEdge="true" type="emerald_block" height="1"/>
                    <EndBlock fixedToEdge="true" type="redstone_block" height="8"/>
                    <PathBlock type="glowstone stained_glass dirt" colour="WHITE ORANGE MAGENTA LIGHT_BLUE YELLOW LIME PINK GRAY SILVER CYAN PURPLE BLUE BROWN GREEN RED BLACK" height="1"/>
                    <FloorBlock type="stone"/>
                    <SubgoalBlock type="beacon sea_lantern glowstone"/>
                    <OptimalPathBlock type="dirt grass snow"/>
                    <GapBlock type="stained_hardened_clay lapis_ore sponge air" colour="WHITE ORANGE MAGENTA LIGHT_BLUE YELLOW LIME PINK GRAY SILVER CYAN PURPLE BLUE BROWN GREEN RED BLACK" height="3" heightVariance="3"/>
                    <Waypoints quantity="10">
                        <WaypointItem>cookie</WaypointItem>
                    </Waypoints>
                </MazeDecorator>
            </ServerHandlers>
        </ServerSection>

        <AgentSection mode="Survival">
            <Name>James Bond</Name>
            <AgentStart>
                <Placement x="-204" y="81" z="217"/>
            </AgentStart>
            <AgentHandlers>
                <ObservationFromMazeOptimalPath />
                <ContinuousMovementCommands turnSpeedDegs="840">
                    <ModifierList type="deny-list"> <!-- Example deny-list: prevent agent from strafing -->
                        <command>strafe</command>
                    </ModifierList>
                </ContinuousMovementCommands>
                <VideoProducer>
                    <Width>320</Width>
                    <Height>240</Height>
                </VideoProducer>
                <AgentQuitFromTouchingBlockType>
                    <Block type="redstone_block" />
                </AgentQuitFromTouchingBlockType>
                <AgentQuitFromTimeUp timeLimitMs="1000"/>
            </AgentHandlers>
        </AgentSection>

    </Mission>'''

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)  # flush print output immediately
validate = True
agent_host = MalmoPython.AgentHost()

# Create a pool of Minecraft Mod clients:
my_client_pool = MalmoPython.ClientPool()
# Add the default client - port 10000 on the local machine:
my_client = MalmoPython.ClientInfo("127.0.0.1", 10000)
my_client_pool.add(my_client)
# Add extra clients here:
# eg my_client_pool.add(MalmoPython.ClientInfo("127.0.0.1", 10001)) etc

# Create a unique identifier - different each time this script is run.
# In multi-agent missions all agents must pass the same experimentID, in order to prevent agents from joining the wrong experiments.
experimentID = uuid.uuid4()

# Create a folder to put our recordings - the platform will not create missing folders itself, it will simply throw an exception.
recordingsDirectory="QuiltRecordings"
try:
    os.makedirs(recordingsDirectory)
except OSError as exception:
    if exception.errno != errno.EEXIST: # ignore error if already existed
        raise

# Run 30000 missions consecutively:
for iRepeat in range(0, 30000):
    # Find the point at which to create the maze:
    xorg = (iRepeat % 64) * 16
    zorg = ((iRepeat / 64) % 64) * 16
    yorg = 200 + ((iRepeat / (64*64)) % 64) * 8

    print "Mission " + str(iRepeat) + " --- starting at " + str(xorg) + ", " + str(yorg) + ", " + str(zorg)

    # Create a mission:
    my_mission = MalmoPython.MissionSpec(GetMissionXML(iRepeat, xorg, yorg, zorg, iRepeat), validate)
    
    launchedMission=False
    while not launchedMission:
        try:
            # Set up a recording - MUST be done once for each mission - don't do this outside the loop!
            my_mission_record = MalmoPython.MissionRecordSpec(recordingsDirectory + "//" + "Quilt_" + str(iRepeat) + ".tgz")
            my_mission_record.recordCommands()
            my_mission_record.recordMP4(24,400000)
            # And attempt to start the mission:
            agent_host.startMission( my_mission, my_client_pool, my_mission_record, 0, str(experimentID) )
            launchedMission=True
        except RuntimeError as e:
            print "Error starting mission",e
            print "Waiting and retrying"
            time.sleep(1)

    print "Waiting for the mission to start",
    world_state = agent_host.getWorldState()
    while not world_state.is_mission_running:
        sys.stdout.write(".")
        time.sleep(0.1)
        world_state = agent_host.getWorldState()
    print

    # main loop:
    while world_state.is_mission_running:
        world_state = agent_host.getWorldState()
        while world_state.number_of_observations_since_last_state < 1 and world_state.is_mission_running:
            time.sleep(0.05)
            world_state = agent_host.getWorldState()

        if world_state.is_mission_running:
            msg = world_state.observations[0].text
            ob = json.loads(msg)
            current_yaw_delta = ob.get(u'yawDelta', 0)
            current_speed = 1-abs(current_yaw_delta)
            
            try:
                agent_host.sendCommand( "move " + str(current_speed) )
                agent_host.sendCommand( "turn " + str(current_yaw_delta) )
            except RuntimeError as e:
                print "Failed to send command:",e
                pass

    print "Mission has stopped."
    time.sleep(0.5)  # Short pause to allow the Mod to get ready for the next mission.