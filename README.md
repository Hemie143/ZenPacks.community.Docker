Goal
----
Monitor Docker containers. The commercial ZenPack has a flaw, as it remodels the containers only every 12 hours (default modeling period of Zenoss).

This ZenPack creates new instances of containers during the data collection, by default every 5 minutes, without changing the period of the modeler. 

Protocol
--------
SSH

Commands used:

docker -v

sudo docker ps --no-trunc

sudo docker stats --no-stream --no-trunc

zProperties
-----------
- zDockerContainerModeled: 
  - type: lines
  - default: .*
  - Comments: Defines the containers to monitor. Each line is a separate regex.


Releases
--------
- 2.0.0 (05/10/2022)
Re-written the ZenPack to be compatible/approved for Zenoss Cloud. There is no longer a modeling occuring during each polling cycle. 
The ZenPack doesn't generate new instances for each new container. The idea is to monitor specific containers which names are matching a regex pattern. 

- 1.2.0 (24/05/2022)
Added event classes

- 1.1.0 (24/05/2022)
Zenoss Cloud compatibility
Corrected cycle time
Added invalidation filters

- 1.0.0 (07/12/2021)
Discovery of live containers
Data collection of metrics presented in docker stats

- Next features / Bugs
  - Remove the custom ssh/sftp client
  - Don't rely on specific docker output formatting,
