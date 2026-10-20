"""Generated XML-only MPQ fixture for archive queries, never loaded by Editor."""
import subprocess
from pathlib import Path

OBJECTS = b'''<PlacedObjects Version="27">
<ObjectUnit Id="1" UnitType="Marine" Name="Scout Alpha" Player="1" Position="8,12,0"/>
<ObjectUnit Id="2" UnitType="Marine" Name="Scout Bravo" Player="2" Position="48,36,0"/>
<ObjectDoodad Id="1" Type="Rock" Position="16,24,1.5"/>
<ObjectPoint Id="3" Name="Rally" Position="32,24,0"/>
<ObjectCamera Id="4" Name="Overview" Position="32,24,40"/>
<ObjectUnit Id="5" UnitType="MissingPosition" Player="1"/>
</PlacedObjects>'''
TERRAIN = b'<terrain version="115"><heightMap dim="65 49" offset="0 0 0" scale="1 1 1"/></terrain>'


def create_archive(directory, tool):
    directory = Path(directory)
    components = directory / 'components'
    components.mkdir(parents=True)
    (components / 'Objects').write_bytes(OBJECTS)
    (components / 't3Terrain.xml').write_bytes(TERRAIN)
    archive = directory / 'SavedObjects.SC2Map'
    subprocess.run([str(tool), 'create', str(components), '--output', str(archive), '--game', 'starcraft2'],
                   check=True, capture_output=True, timeout=30,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return archive
