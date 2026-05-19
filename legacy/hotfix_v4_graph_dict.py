#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

p = Path('local_cruncher_v4_deep_stacking.py')
if not p.exists():
    raise SystemExit('local_cruncher_v4_deep_stacking.py not found')

s = p.read_text(encoding='utf-8')

old = '    graph_cpu = np.asarray(graph, dtype=np.float32)\n'
new = '''    if isinstance(graph, dict):
        if "adjacency" in graph:
            graph_source = graph["adjacency"]
        elif "graph" in graph and isinstance(graph["graph"], dict) and "adjacency" in graph["graph"]:
            graph_source = graph["graph"]["adjacency"]
        else:
            raise TypeError(f"graph dict does not contain adjacency; keys={list(graph.keys())}")
    else:
        graph_source = graph
    graph_cpu = np.asarray(graph_source, dtype=np.float32)
'''

if new.strip() in s:
    print('OK: graph dict hotfix already applied')
    raise SystemExit(0)

if old not in s:
    raise SystemExit('Could not find graph_cpu assignment to patch')

s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('OK: graph dict hotfix applied')
