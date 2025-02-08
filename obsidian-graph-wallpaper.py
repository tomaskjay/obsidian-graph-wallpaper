import os
import re
import time
import math
import ctypes
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Change both paths: first is the location of your vault, second is the location of where you want the output png
VAULT_PATH = r"C:\Users\Tomas\Main Obsidian Vault"
OUTPUT_IMAGE = r"C:\Users\Tomas\OneDrive\Pictures\Wallpaper Pic\obsidian_graph.png"

def set_wallpaper_windows(image_path):
    """
    Update the Windows desktop wallpaper.
    """
    ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, 0)

def build_vault_graph(vault_directory):
    """
    1) Parse .md files for wikilinks: [[...]]
    2) Also track attachments (non-.md files) so we can represent them as orange nodes.
    3) Create edges from an .md note to any file (md or not) if we see a wikilink referencing it.
    4) Remove orphan (degree-0) nodes so they don't appear in the graph.
    """
    wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")
    G = nx.Graph()

    file_dict = {}
    for root, dirs, files in os.walk(vault_directory):
        for filename in files:
            full_path = os.path.join(root, filename)
            file_dict[filename] = full_path

    for md_name, md_path in file_dict.items():
        if not md_name.lower().endswith(".md"):
            continue

        if not G.has_node(md_name):
            G.add_node(md_name)

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            links = wikilink_pattern.findall(content)
            
            for link in links:
                link_clean = re.split(r"[#|]", link)[0].strip()
                if "." not in link_clean:
                    link_clean += ".md"

                if link_clean in file_dict:
                    if not G.has_node(link_clean):
                        G.add_node(link_clean)
                    G.add_edge(md_name, link_clean)

    # Remove orphan (degree-0) nodes
    orphans = [n for n in G.nodes() if G.degree(n) == 0]
    G.remove_nodes_from(orphans)

    return G

def enforce_min_distance(pos, min_dist=0.05, iterations=10):
    """
    After the layout is computed, push nodes apart if they are
    closer than min_dist. 'iterations' is how many times we'll
    repeat this procedure. Higher => more separation, but slower.
    """
    nodes = list(pos.keys())
    for _ in range(iterations):
        moved = False
        for i in range(len(nodes)):
            for j in range(i+1, len(nodes)):
                n1, n2 = nodes[i], nodes[j]
                x1, y1 = pos[n1]
                x2, y2 = pos[n2]
                dx = x2 - x1
                dy = y2 - y1
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < min_dist and dist > 1e-9:
                    overlap = 0.5 * (min_dist - dist)
                    ux = dx / dist
                    uy = dy / dist
                    pos[n1] = (x1 - overlap * ux, y1 - overlap * uy)
                    pos[n2] = (x2 + overlap * ux, y2 + overlap * uy)
                    moved = True
        if not moved:
            break

def draw_graph_and_save(G, output_path):
    """
    Draw the graph:
      - Larger spring force for leaf edges
      - Place isolated nodes in a ring (if any remain)
      - Enforce min distance to avoid node collisions
      - Straight line edges (no connectionstyle)
    """
    plt.clf()
    fig = plt.figure(figsize=(12, 12))
    fig.patch.set_facecolor("#F0F0F0")

    # Give leaf edges a higher weight
    for u, v in G.edges():
        if G.degree(u) == 1 or G.degree(v) == 1:
            G[u][v]['weight'] = 5.0
        else:
            G[u][v]['weight'] = 1.0

    # Identify isolates vs. connected nodes
    isolates = [n for n in G.nodes if G.degree(n) == 0]
    connected_nodes = [n for n in G.nodes if G.degree(n) > 0]
    H = G.subgraph(connected_nodes)

    # Spring layout
    pos_connected = nx.spring_layout(
        H,
        k=3.0,
        iterations=500,
        seed=42,
        weight='weight'
    )
    pos = dict(pos_connected)

    # Place isolated nodes (if any remain) in a ring around the bounding box
    if isolates:
        xs = [p[0] for p in pos_connected.values()]
        ys = [p[1] for p in pos_connected.values()]
        if xs and ys:
            center_x = (min(xs) + max(xs)) / 2
            center_y = (min(ys) + max(ys)) / 2
            radius = max((max(xs) - center_x), (max(ys) - center_y)) + 0.5
        else:
            center_x = 0
            center_y = 0
            radius = 1

        angle_step = 2 * math.pi / max(len(isolates), 1)
        for i, node in enumerate(isolates):
            angle = i * angle_step
            ix = center_x + radius * math.cos(angle)
            iy = center_y + radius * math.sin(angle)
            pos[node] = (ix, iy)

    # Enforce minimum distance to avoid node overlap
    enforce_min_distance(pos, min_dist=0.05, iterations=15)

    # Separate MD vs. attachments
    md_nodes = [n for n in G.nodes if n.lower().endswith(".md")]
    attachment_nodes = [n for n in G.nodes if not n.lower().endswith(".md")]

    # Node sizes
    node_sizes = {n: 10 + (G.degree(n) * 3) for n in G.nodes()}

    # Draw edges (no connectionstyle => no warning)
    nx.draw_networkx_edges(
        G,
        pos,
        alpha=0.4,
        edge_color="#D3D3D3",
        width=0.75
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=md_nodes,
        node_size=[node_sizes[n] for n in md_nodes],
        node_color="#6D7A8D",
        alpha=0.9
    )
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=attachment_nodes,
        node_size=[node_sizes[n] for n in attachment_nodes],
        node_color="#F5C277",
        alpha=0.9
    )

    plt.axis("off")
    ax = plt.gca()
    ax.set_aspect("equal", "box")

    plt.tight_layout()
    plt.savefig(output_path, dpi=400, facecolor=fig.get_facecolor())
    plt.close()

def update_wallpaper():
    G = build_vault_graph(VAULT_PATH)
    draw_graph_and_save(G, OUTPUT_IMAGE)
    set_wallpaper_windows(OUTPUT_IMAGE)
    print("[INFO] Wallpaper updated.")

class VaultChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        print(f"[UPDATE] Change detected: {event.event_type} - {event.src_path}")
        update_wallpaper()

if __name__ == "__main__":
    update_wallpaper()
    event_handler = VaultChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, VAULT_PATH, recursive=True)
    observer.start()

    print("[INFO] Watching vault for changes. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
