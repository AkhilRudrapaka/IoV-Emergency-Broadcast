import os
import random
import xml.etree.ElementTree as ET


def build_connection_map(con_file="network/temp.con.xml", net_file="network/road.net.xml"):
    """
    Parses connection XML or network XML to map valid edge transitions in SUMO.
    Excludes internal junction edges (starting with ':').
    """
    conn_map = {}

    if os.path.exists(net_file):
        tree = ET.parse(net_file)
        root = tree.getroot()

        # Gather plain edge IDs
        edge_ids = set()
        for edge in root.findall('edge'):
            eid = edge.attrib.get('id', '')
            if eid and not eid.startswith(':'):
                edge_ids.add(eid)

        for conn in root.findall('connection'):
            f = conn.attrib.get('from')
            t = conn.attrib.get('to')
            if f and t and not f.startswith(":") and not t.startswith(":"):
                if f in edge_ids and t in edge_ids:
                    conn_map.setdefault(f, set()).add(t)

    valid_edges = list(conn_map.keys())
    return valid_edges, {k: list(v) for k, v in conn_map.items()}


def generate_random_route(valid_edges, edge_next, min_length=5, max_length=12):
    """
    Generates a valid sequence of connected edges in the 5x5 urban network without U-turns.
    """
    start_edge = random.choice(valid_edges)
    route = [start_edge]
    curr = start_edge

    length = random.randint(min_length, max_length)
    for _ in range(length - 1):
        next_candidates = edge_next.get(curr, [])
        valid_candidates = [e for e in next_candidates if len(route) < 2 or e != route[-2]]
        if not valid_candidates:
            valid_candidates = next_candidates
        if not valid_candidates:
            break
        curr = random.choice(valid_candidates)
        route.append(curr)

    return " ".join(route)


def generate_route_file(num_vehicles, output_file, duration=100.0, seed=42):
    """
    Generates a SUMO .rou.xml file for 5x5 urban grid with gradual departures,
    lane-change attributes, and randomized vehicle dynamics.
    """
    random.seed(seed)
    valid_edges, edge_next = build_connection_map()

    if not valid_edges:
        print(f"[GenerateRoutes] Warning: No valid edges found for {output_file}")
        return

    root = ET.Element("routes")

    # Define car vType with safety, lane change parameters, and speed dynamics
    vtype = ET.SubElement(root, "vType", {
        "id": "car",
        "accel": "2.6",
        "decel": "4.5",
        "sigma": "0.5",
        "length": "5.0",
        "minGap": "2.5",
        "maxSpeed": "22.0",
        "lcStrategic": "1.0",
        "lcCooperative": "1.0",
        "lcSpeedGain": "1.0"
    })

    depart_interval = duration / max(num_vehicles, 1)

    for i in range(num_vehicles):
        depart_time = round(i * depart_interval, 2)
        route_str = generate_random_route(valid_edges, edge_next)

        veh = ET.SubElement(root, "vehicle", {
            "id": f"v{i}",
            "type": "car",
            "depart": f"{depart_time:.2f}"
        })
        ET.SubElement(veh, "route", {
            "edges": route_str
        })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"[GenerateRoutes] Created 5x5 route file '{output_file}' with {num_vehicles} vehicles.")


def generate_all_route_files(densities=[50, 100, 200, 250, 300, 500]):
    for density in densities:
        out_path = f"network/routes_{density}.rou.xml"
        generate_route_file(density, out_path)
    generate_route_file(250, "network/routes.rou.xml")


if __name__ == "__main__":
    generate_all_route_files()
