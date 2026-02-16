"""
Topic Cluster Visualization Module.
Generates an interactive HTML visualization of the clustered topics using D3.js.
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Any

from utils.logger import log


def save_interactive_visualization(clusters: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Generate a self-contained HTML file with D3.js visualization.
    
    Args:
        clusters: List of cluster dictionaries from topic_clusterer.py
        output_path: Path to save the HTML file (e.g., output/clusters.html)
    """
    if not clusters:
        log.warning("No clusters to visualize.")
        return

    # Prepare data for D3.js
    nodes = []
    links = []
    
    # We need a unique ID for each node
    article_id_counter = 0
    
    # 1. Create nodes for each article
    for cluster_idx, cluster in enumerate(clusters):
        cluster_topic = cluster.get("representative_title", f"Topic {cluster_idx + 1}")
        cluster_size = cluster.get("article_count", 0)
        
        # Add a node for the cluster center (invisible gravity well)
        center_id = f"center_{cluster_idx}"
        
        # Add article nodes
        for article in cluster.get("articles", []):
            nodes.append({
                "id": article_id_counter,
                "title": article.get("title", "No Title"),
                "source": article.get("source_name", "Unknown"),
                "snippet": article.get("summary", "")[:100] + "...",
                "cluster": cluster_idx,
                "cluster_topic": cluster_topic,
                "url": article.get("link", "#"),
                # Initial random position for "spawn" effect
                "x": random.randint(100, 800),
                "y": random.randint(100, 600),
                "val": 5 + (len(article.get("summary", "")) / 100) # Size based on content length
            })
            article_id_counter += 1

    # Convert to JSON string
    data_json = json.dumps({"nodes": nodes, "links": links})

    # HTML Template with embedded D3.js logic
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lens AI - Topic Cluster Universe</title>
    <style>
        body {{ margin: 0; background-color: #0f172a; color: white; font-family: 'Inter', sans-serif; overflow: hidden; }}
        #container {{ width: 100vw; height: 100vh; position: relative; }}
        .tooltip {{
            position: absolute;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid #334155;
            padding: 12px;
            border-radius: 8px;
            pointer-events: none;
            max-width: 300px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(4px);
            opacity: 0;
            transition: opacity 0.2s;
            z-index: 10;
        }}
        .tooltip h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #60a5fa; }}
        .tooltip p {{ margin: 0; font-size: 12px; color: #94a3b8; }}
        .controls {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(30, 41, 59, 0.8);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #334155;
        }}
        button {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.1s;
        }}
        button:hover {{ transform: scale(1.05); background: #2563eb; }}
        h1 {{ margin: 0 0 10px 0; font-size: 18px; }}
    </style>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div class="controls">
        <h1>🌌 Lens AI Topic Universe</h1>
        <p style="font-size: 12px; margin-bottom: 10px; opacity: 0.8">Drag nodes to play with physics.</p>
        <button onclick="explode()">💥 Explode</button>
        <button onclick="group()">🧲 Form Clusters</button>
    </div>
    <div id="container"></div>
    <div class="tooltip" id="tooltip"></div>

    <script>
        const data = {data_json};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        // Color scale for 20+ clusters
        const color = d3.scaleOrdinal(d3.schemeTableau10);

        // Physics Simulation
        const simulation = d3.forceSimulation(data.nodes)
            .force("charge", d3.forceManyBody().strength(-30)) // Repulsion
            .force("collide", d3.forceCollide().radius(d => d.val + 2).iterations(2)) // Collision
            .force("center", d3.forceCenter(width / 2, height / 2).strength(0.05)) // Global center gravity
            .force("x", d3.forceX().strength(0)) // Initially zero for chaos
            .force("y", d3.forceY().strength(0))
            .on("tick", ticked);

        // Create SVG
        const svg = d3.select("#container")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }}));

        const g = svg.append("g");

        // Render Nodes (Bubbles)
        const node = g.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .join("circle")
            .attr("r", d => d.val)
            .attr("fill", d => color(d.cluster))
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5)
            .attr("stroke-opacity", 0.6)
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        // Tooltip Interaction
        const tooltip = d3.select("#tooltip");
        
        node
            .on("mouseover", (event, d) => {{
                tooltip.style("opacity", 1)
                    .html(`<h3>${{d.title}}</h3><p><b>Source:</b> ${{d.source}}</p><p><b>Cluster:</b> ${{d.cluster_topic}}</p>`)
                    .style("left", (event.pageX + 15) + "px")
                    .style("top", (event.pageY - 15) + "px");
                d3.select(event.currentTarget).attr("stroke", "#fbbf24").attr("stroke-width", 3);
            }})
            .on("mouseout", (event) => {{
                tooltip.style("opacity", 0);
                d3.select(event.currentTarget).attr("stroke", "#fff").attr("stroke-width", 1.5);
            }})
            .on("click", (event, d) => {{
                if (d.url && d.url !== "#") window.open(d.url, "_blank");
            }});

        function ticked() {{
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
        }}

        // Drag functions
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}

        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}

        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        // Game Logic: Form Clusters
        function group() {{
            // Calculate cluster centers
            const clusters = {{}};
            data.nodes.forEach(d => {{
                if (!clusters[d.cluster]) clusters[d.cluster] = {{count: 0, x: 0, y: 0}};
                clusters[d.cluster].count++;
            }});
            
            // Arrange centers in a circle or grid
            const clusterIds = Object.keys(clusters);
            const radius = Math.min(width, height) * 0.35;
            const angleStep = (2 * Math.PI) / clusterIds.length;
            
            clusterIds.forEach((id, i) => {{
                clusters[id].targetX = width / 2 + radius * Math.cos(i * angleStep);
                clusters[id].targetY = height / 2 + radius * Math.sin(i * angleStep);
            }});
            
            simulation
                .force("x", d3.forceX(d => clusters[d.cluster].targetX).strength(0.15))
                .force("y", d3.forceY(d => clusters[d.cluster].targetY).strength(0.15))
                .force("charge", d3.forceManyBody().strength(-10)) // Reduce repulsion to pack tighter
                .alpha(1).restart();
        }}
        
        function explode() {{
            simulation
                .force("x", d3.forceX(width/2).strength(0.01)) // Weak center
                .force("y", d3.forceY(height/2).strength(0.01))
                .force("charge", d3.forceManyBody().strength(-60)) // Strong repulsion
                .alpha(1).restart();
        }}
        
        // Start game: Delay then group
        setTimeout(group, 1000); // 1s of chaos then form clusters
        
    </script>
</body>
</html>
    """
    
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        log.info(f"✨ Interactive visualization saved: {output_path}")
    except Exception as e:
        log.error(f"Failed to save visualization: {e}")

