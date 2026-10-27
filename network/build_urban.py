"""Rebuild the landscaped boulevard network with SUMO's netconvert."""
import math
from pathlib import Path
import subprocess
import os
import xml.etree.ElementTree as ET

import sumo


def build():
    folder = Path(__file__).resolve().parent
    nodes, edges, scenery = ET.Element('nodes'), ET.Element('edges'), ET.Element('additional')
    positions = {}
    for i, x in enumerate((0, 160, 390, 610, 820)):
        for j, y in enumerate((0, 170, 370, 590, 800)):
            name = f'{chr(65 + i)}{j}'
            positions[name] = (x, y)
            px, py = positions[name]
            ET.SubElement(nodes, 'node', id=name, x=f'{px:.2f}', y=f'{py:.2f}',
                          type='traffic_light' if 0 < i < 4 and 0 < j < 4 else 'priority')
    for i in range(5):
        for j in range(5):
            a = f'{chr(65 + i)}{j}'
            for di, dj in ((1, 0), (0, 1)):
                if i + di >= 5 or j + dj >= 5:
                    continue
                b = f'{chr(65 + i + di)}{j + dj}'
                x1, y1 = positions[a]
                x2, y2 = positions[b]
                shape = f'{x1:.2f},{y1:.2f} {x2:.2f},{y2:.2f}'
                for start, end in ((a, b), (b, a)):
                    ET.SubElement(edges, 'edge', {'id': f'{start}{end}', 'from': start, 'to': end,
                        'numLanes': '3' if j == 2 and di else '2', 'speed': '13.89',
                        'name': 'Garden Boulevard' if j == 2 and di else f'{chr(65+i)} District Way',
                        'shape': shape if start == a else ' '.join(reversed(shape.split()))})
    for i in range(4):
        for j in range(4):
            corners = [positions[f'{chr(65 + c)}{r}'] for c, r in
                       ((i, j), (i+1, j), (i+1, j+1), (i, j+1))]
            cx, cy = (sum(p[k] for p in corners) / 4 for k in (0, 1))
            park = (i + j) % 3 == 0
            shape = ' '.join(f'{cx + (x-cx)*0.68:.2f},{cy + (y-cy)*0.68:.2f}' for x, y in corners)
            ET.SubElement(scenery, 'poly', id=f'block-{i}-{j}', shape=shape,
                          color='218,237,224' if park else '231,235,244', fill='true', layer='-5')
            if park:
                for dx, dy in ((-30, -25), (25, 20), (25, -25), (-30, 20)):
                    tree = ' '.join(f'{cx+dx+8*math.cos(a):.2f},{cy+dy+8*math.sin(a):.2f}'
                                    for a in (k*math.tau/16 for k in range(16)))
                    ET.SubElement(scenery, 'poly', id=f'tree-{i}-{j}-{dx}-{dy}', shape=tree,
                                  color='101,165,136', fill='true', layer='-4')
                water = ' '.join(f'{cx+22*math.cos(a):.2f},{cy+15*math.sin(a):.2f}'
                                 for a in (k*math.tau/32 for k in range(32)))
                ET.SubElement(scenery, 'poly', id=f'pond-{i}-{j}', shape=water,
                              color='161,208,225', fill='true', layer='-3')
            else:
                for dx, dy in ((-28, -23), (25, 23)):
                    shape = ' '.join(f'{cx+dx+x:.2f},{cy+dy+y:.2f}' for x,y in
                                     ((-20,-15),(20,-15),(20,15),(-20,15)))
                    ET.SubElement(scenery, 'poly', id=f'building-{i}-{j}-{dx}', shape=shape,
                                  color='165,183,211' if (i+j)%2 else '183,173,210', fill='true', layer='-4')
                    roof = ' '.join(f'{cx+dx+x:.2f},{cy+dy+y:.2f}' for x,y in
                                    ((-17,-12),(17,-12),(17,12),(-17,12)))
                    ET.SubElement(scenery, 'poly', id=f'roof-{i}-{j}-{dx}', shape=roof,
                                  color='211,221,237' if (i+j)%2 else '227,219,240', fill='true', layer='-3')
    for root, name in ((nodes, 'urban.nod.xml'), (edges, 'urban.edg.xml'), (scenery, 'urban.add.xml')):
        ET.indent(root)
        ET.ElementTree(root).write(folder / name, encoding='utf-8', xml_declaration=True)
    binary = Path(sumo.SUMO_HOME) / 'bin' / ('netconvert.exe' if os.name == 'nt' else 'netconvert')
    subprocess.run([str(binary), '-n', str(folder/'urban.nod.xml'), '-e', str(folder/'urban.edg.xml'),
                    '-o', str(folder/'urban.net.xml'), '--offset.disable-normalization',
                    '--junctions.corner-detail', '12', '--junctions.internal-link-detail', '12',
                    '--no-turnarounds', 'true'], check=True)


if __name__ == '__main__':
    build()
