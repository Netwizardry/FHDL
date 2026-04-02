import os
import glob

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if "Status: Active" in content or "Version: v4.0" in content:
        return # Already has metadata

    lines = content.split('\n')
    title_index = -1
    for i, line in enumerate(lines):
        if line.startswith('# '):
            title_index = i
            break
            
    if title_index != -1:
        meta = """
**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5
"""
        lines.insert(title_index + 1, meta)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

for file in glob.glob('docs/spec/*.md'):
    update_file(file)
