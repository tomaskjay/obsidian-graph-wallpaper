import os
import re
import time
import math
import ctypes
import matplotlib
matplotlib.use("Agg")  # Headless backend to avoid Tkinter/thread errors

import matplotlib.pyplot as plt
import networkx as nx
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ----------------------------
# CONFIGURATIONS
# ----------------------------
VAULT_PATH = r"C:\Users\Tomas\Main Obsidian Vault"
OUTPUT_IMAGE = r"C:\Users\Tomas\OneDrive\Desktop\Projects\obsidian-graph-wallpaper\wallpaper-pics\obsidian_graph.png"

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
    """

    # Regex to capture [[filename.xyz]] style links
    # (This handles e.g. [[Note.md]], [[image.png]], [[doc.pdf]], etc.)
    wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")

    G = nx.Graph()

    # 1) Collect all files in the vault
    #    We'll store them by their "base filename" (note) + extension
    #    so that .md and .png with the same base won't collapse into one node.
    file_dict = {}  # key = full_filename (e.g., "MyNote.md"), value = full path
    for root, dirs, files in os.walk(vault_directory):
        for filename in files:
            # Example: "image.png" or "MyNote.md"
            full_path = os.path.join(root, filename)
            file_dict[filename] = full_path

    # 2) Build edges by parsing each .md file’s wikilinks
    for md_name, md_path in file_dict.items():
        # Skip if not .md
        if not md_name.lower().endswith(".md"):
            continue

        # Add node for the .md file
        if not G.has_node(md_name):
            G.add_node(md_name)

        # Parse content for wikilinks
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            links = wikilink_pattern.findall(content)
            
            for link in links:
                # If link is something like "Note.md#SomeSection" or "Note.png|alias"
                # we just want the actual filename portion
                # We'll strip off subpaths (# or |).
                link_clean = re.split(r"[#|]", link)[0].strip()

                # If the link doesn't specify .md, Obsidian might guess "Note" -> "Note.md"
                # but let's keep it simple: if there's no '.' extension, assume .md
                if "." not in link_clean:
                    link_clean += ".md"

                # If that file actually exists in vault, connect them
                if link_clean in file_dict:
                    # Add that node if not present
                    if not G.has_node(link_clean):
                        G.add_node(link_clean)
                    # Add edge
                    G.add_edge(md_name, link_clean)

    return G

def draw_graph_and_save(G, output_path):
    """
    - No labels.
    - Node color depends on whether it's .md or not.
    - Node size depends on node degree (larger = more connections).
    - Use a force-directed layout with parameters that push leaf nodes outward.
    """

    plt.clf()
    fig = plt.figure(figsize=(10, 8))
    # Light background
    fig.patch.set_facecolor("white")

    # 1) Split nodes by type: markdown vs attachment
    md_nodes = [n for n in G.nodes if n.lower().endswith(".md")]
    attachment_nodes = [n for n in G.nodes if not n.lower().endswith(".md")]

    # 2) Node sizes: e.g. base size + factor*degree
    #    If you want them more spread out, increase the factor
    node_sizes = []
    for n in G.nodes():
        deg = G.degree(n)
        size = 30 + (deg * 5)  # tweak the constants as you like
        node_sizes.append(size)

    # 3) Force-directed layout with a higher "k" so nodes spread out more.
    #    For a large graph, try increasing iterations or adjusting k.
    pos = nx.spring_layout(G, k=1.5, iterations=200, center=(0, 0))

    # 4) Draw edges (in a light gray)
    nx.draw_networkx_edges(
        G, pos, 
        alpha=0.4, 
        edge_color="gray", 
        width=1.0
    )

    # 5) Draw markdown nodes (blue/gray)
    #    We have to pick out their sizes from our node_sizes list in the same order.
    md_nodes_sorted = list(md_nodes)  # freeze the order
    md_sizes = []
    for node in md_nodes_sorted:
        md_sizes.append(30 + (G.degree(node) * 5))

    nx.draw_networkx_nodes(
        G, pos,
        nodelist=md_nodes_sorted,
        node_size=md_sizes,
        node_color="#6D7A8D",  # a muted gray-blue
        alpha=0.9
    )

    # 6) Draw attachments (orange)
    attach_nodes_sorted = list(attachment_nodes)
    attach_sizes = []
    for node in attach_nodes_sorted:
        attach_sizes.append(30 + (G.degree(node) * 5))

    nx.draw_networkx_nodes(
        G, pos,
        nodelist=attach_nodes_sorted,
        node_size=attach_sizes,
        node_color="#F5C277",  # a soft orange
        alpha=0.9
    )

    # 7) No labels
    #    If you want node names off entirely, just omit drawing them.

    plt.axis("off")
    plt.tight_layout()

    # 8) Save
    plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()

def update_wallpaper():
    G = build_vault_graph(VAULT_PATH)
    draw_graph_and_save(G, OUTPUT_IMAGE)
    set_wallpaper_windows(OUTPUT_IMAGE)
    print("[INFO] Wallpaper updated.")

class VaultChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        print(f"[DEBUG] Change detected: {event.event_type} - {event.src_path}")
        update_wallpaper()

if __name__ == "__main__":
    # Initial draw
    update_wallpaper()

    # Watch for changes
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

