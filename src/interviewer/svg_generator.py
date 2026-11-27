"""
Pure-Python SVG generator for DAG mental model graphs.
No system-level dependencies (no graphviz binary required).
"""


def dag_to_svg(dag: dict) -> str:
    """Convert a DAG dict {nodes, edges} to an inline SVG string."""
    nodes = dag.get('nodes', [])
    edges = dag.get('edges', [])

    if not nodes:
        return ('<svg width="400" height="50" xmlns="http://www.w3.org/2000/svg">'
                '<text x="10" y="30" font-family="sans-serif" font-size="13" fill="#888">'
                'No graph data.</text></svg>')

    node_ids = {n['id'] for n in nodes}

    # Build parent/child maps
    parents  = {n['id']: [] for n in nodes}
    children = {n['id']: [] for n in nodes}
    for e in edges:
        s, t = e.get('source'), e.get('target')
        if s in node_ids and t in node_ids:
            children[s].append(t)
            parents[t].append(s)

    # Assign BFS levels (longest path from any root)
    levels = {}
    roots = [n['id'] for n in nodes if not parents[n['id']]]
    if not roots:
        roots = [nodes[0]['id']]
    for r in roots:
        levels[r] = 0
    queue = list(roots)
    while queue:
        nid = queue.pop(0)
        for child in children[nid]:
            new_lvl = levels[nid] + 1
            if child not in levels or levels[child] < new_lvl:
                levels[child] = new_lvl
                queue.append(child)
    for n in nodes:
        levels.setdefault(n['id'], 0)

    # Group nodes by level
    max_level = max(levels.values())
    by_level: dict = {}
    for n in nodes:
        by_level.setdefault(levels[n['id']], []).append(n)

    # Layout constants. Levels run top to bottom so the graph fits a narrow chat column.
    NODE_W, NODE_H = 155, 46
    H_GAP, V_GAP   = 18, 46
    PAD             = 22

    max_per_level = max(len(v) for v in by_level.values())
    canvas_w = max_per_level * (NODE_W + H_GAP) - H_GAP + 2 * PAD
    canvas_h = (max_level + 1) * (NODE_H + V_GAP) - V_GAP + 2 * PAD
    canvas_w = max(canvas_w, 300)
    canvas_h = max(canvas_h, 80)

    # Compute center positions
    pos: dict = {}
    for lvl in range(max_level + 1):
        level_nodes = by_level.get(lvl, [])
        total_w = len(level_nodes) * (NODE_W + H_GAP) - H_GAP
        start_x = (canvas_w - total_w) / 2
        cy = PAD + lvl * (NODE_H + V_GAP) + NODE_H / 2
        for i, n in enumerate(level_nodes):
            cx = start_x + i * (NODE_W + H_GAP) + NODE_W / 2
            pos[n['id']] = (cx, cy)

    # The viewBox lets the browser shrink a wide graph to the chat width instead of scrolling.
    parts = [
        f'<svg width="{int(canvas_w)}" height="{int(canvas_h)}" viewBox="0 0 {int(canvas_w)} {int(canvas_h)}" '
        f'xmlns="http://www.w3.org/2000/svg" style="font-family:sans-serif;max-width:100%;height:auto;">',
        '<defs>',
        '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="5" markerHeight="5" orient="auto">',
        '<path d="M0,0 L10,5 L0,10 Z" fill="#4a6fa5"/>',
        '</marker>',
        '</defs>',
    ]

    # Edges (drawn behind nodes), from the bottom of the source to the top of the target
    for e in edges:
        s, t = e.get('source'), e.get('target')
        if s not in pos or t not in pos:
            continue
        sx, sy = pos[s]
        tx, ty = pos[t]
        x1, y1 = sx, sy + NODE_H / 2
        x2, y2 = tx, ty - NODE_H / 2
        dy = (y2 - y1) * 0.55
        d = f"M{x1:.1f},{y1:.1f} C{x1:.1f},{y1+dy:.1f} {x2:.1f},{y2-dy:.1f} {x2:.1f},{y2:.1f}"
        parts.append(f'<path d="{d}" fill="none" stroke="#4a6fa5" '
                     f'stroke-width="1.5" marker-end="url(#arr)"/>')
        label = e.get('label', '').strip()
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + 4
            parts.append(f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                         f'font-size="10" fill="#6b7fa8" stroke="#f8faff" stroke-width="3" '
                         f'paint-order="stroke">{_esc(label)}</text>')

    # Nodes
    for n in nodes:
        nid = n['id']
        if nid not in pos:
            continue
        cx, cy = pos[nid]
        x, y = cx - NODE_W / 2, cy - NODE_H / 2
        is_root = not parents[nid]
        fill      = '#2563a8' if is_root else '#dbeafe'
        text_fill = 'white'   if is_root else '#1e3a5f'
        stroke    = '#2563a8'

        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_W}" height="{NODE_H}" '
                     f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

        lines = _wrap(n.get('label', ''), max_chars=20)
        line_h = 14
        total_text_h = len(lines) * line_h
        base_y = cy - total_text_h / 2 + line_h * 0.82

        for i, line in enumerate(lines):
            ty = base_y + i * line_h
            parts.append(f'<text x="{cx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                         f'font-size="12" font-weight="600" fill="{text_fill}">{_esc(line)}</text>')

    parts.append('</svg>')
    return '\n'.join(parts)


def _wrap(text: str, max_chars: int = 20) -> list:
    """Wrap text into lines of at most max_chars characters."""
    words = text.split()
    lines, current = [], ''
    for w in words:
        candidate = (current + ' ' + w).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [text]


def _esc(text: str) -> str:
    """Escape special XML characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
