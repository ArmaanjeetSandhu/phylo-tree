"""
This module contains functions to compare two directory structures and
display them side by side with highlighting of differences.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from recursivist.core import (
    compile_regex_patterns,
    generate_color_for_extension,
    get_directory_structure,
    sort_files_by_type,
)

logger = logging.getLogger(__name__)


def compare_directory_structures(
    dir1: str,
    dir2: str,
    exclude_dirs: Optional[List[str]] = None,
    ignore_file: Optional[str] = None,
    exclude_extensions: Optional[Set[str]] = None,
    exclude_patterns: Optional[List[Union[str, Pattern]]] = None,
    include_patterns: Optional[List[Union[str, Pattern]]] = None,
) -> Tuple[Dict, Dict, Set[str]]:
    """
    Compare two directory structures and return both structures and a combined set of extensions.

    Args:
        dir1: Path to the first directory
        dir2: Path to the second directory
        exclude_dirs: List of directory names to exclude
        ignore_file: Name of ignore file (like .gitignore)
        exclude_extensions: Set of file extensions to exclude
        exclude_patterns: List of patterns to exclude
        include_patterns: List of patterns to include (overrides exclusions)

    Returns:
        Tuple of (structure1, structure2, combined_extensions)
    """
    structure1, extensions1 = get_directory_structure(
        dir1,
        exclude_dirs,
        ignore_file,
        exclude_extensions,
        exclude_patterns=exclude_patterns,
        include_patterns=include_patterns,
    )
    structure2, extensions2 = get_directory_structure(
        dir2,
        exclude_dirs,
        ignore_file,
        exclude_extensions,
        exclude_patterns=exclude_patterns,
        include_patterns=include_patterns,
    )

    combined_extensions = extensions1.union(extensions2)

    return structure1, structure2, combined_extensions


def build_comparison_tree(
    structure: Dict,
    other_structure: Dict,
    tree: Tree,
    color_map: Dict[str, str],
    parent_name: str = "Root",
) -> None:
    """
    Build a tree structure with highlighted differences.

    Args:
        structure: Dictionary representation of the current directory structure
        other_structure: Dictionary representation of the comparison directory structure
        tree: Rich Tree object to build upon
        color_map: Mapping of file extensions to colors
        parent_name: Name of the parent directory
    """
    if "_files" in structure:
        files_in_other = other_structure.get("_files", []) if other_structure else []
        for file in sort_files_by_type(structure["_files"]):
            ext = os.path.splitext(file)[1].lower()
            color = color_map.get(ext, "#FFFFFF")

            if file not in files_in_other:
                colored_text = Text(f"📄 {file}", style=f"{color} on green")
                tree.add(colored_text)
            else:
                colored_text = Text(f"📄 {file}", style=color)
                tree.add(colored_text)

    for folder, content in sorted(structure.items()):
        if folder != "_files":
            other_content = other_structure.get(folder, {}) if other_structure else {}

            if folder not in (other_structure or {}):
                subtree = tree.add(Text(f"📁 {folder}", style="green"))
            else:
                subtree = tree.add(f"📁 {folder}")

            build_comparison_tree(content, other_content, subtree, color_map, folder)

    if other_structure and "_files" in other_structure:
        files_in_this = structure.get("_files", [])
        for file in sort_files_by_type(other_structure["_files"]):
            if file not in files_in_this:
                ext = os.path.splitext(file)[1].lower()
                color = color_map.get(ext, "#FFFFFF")
                colored_text = Text(f"📄 {file}", style=f"{color} on red")
                tree.add(colored_text)

    if other_structure:
        for folder in sorted(other_structure.keys()):
            if folder != "_files" and folder not in structure:
                subtree = tree.add(Text(f"📁 {folder}", style="red"))
                build_comparison_tree(
                    {}, other_structure[folder], subtree, color_map, folder
                )


def display_comparison(
    dir1: str,
    dir2: str,
    exclude_dirs: Optional[List[str]] = None,
    ignore_file: Optional[str] = None,
    exclude_extensions: Optional[Set[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    use_regex: bool = False,
) -> None:
    """
    Display two directory trees side by side with highlighted differences.

    Args:
        dir1: Path to the first directory
        dir2: Path to the second directory
        exclude_dirs: List of directory names to exclude
        ignore_file: Name of ignore file (like .gitignore)
        exclude_extensions: Set of file extensions to exclude
        exclude_patterns: List of patterns to exclude
        include_patterns: List of patterns to include (overrides exclusions)
        use_regex: Whether to treat patterns as regex instead of glob patterns
    """
    if exclude_dirs is None:
        exclude_dirs = []
    if exclude_extensions is None:
        exclude_extensions = set()
    if exclude_patterns is None:
        exclude_patterns = []
    if include_patterns is None:
        include_patterns = []

    exclude_extensions = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in exclude_extensions
    }

    # Compile regex patterns if needed - make sure patterns are List[str]
    compiled_exclude = compile_regex_patterns(exclude_patterns, use_regex)
    compiled_include = compile_regex_patterns(include_patterns, use_regex)

    structure1, structure2, extensions = compare_directory_structures(
        dir1,
        dir2,
        exclude_dirs,
        ignore_file,
        exclude_extensions,
        exclude_patterns=compiled_exclude,
        include_patterns=compiled_include,
    )

    color_map = {ext: generate_color_for_extension(ext) for ext in extensions}

    console = Console()
    tree1 = Tree(Text(f"📂 {os.path.basename(dir1)}", style="bold"))
    tree2 = Tree(Text(f"📂 {os.path.basename(dir2)}", style="bold"))

    build_comparison_tree(structure1, structure2, tree1, color_map)
    build_comparison_tree(structure2, structure1, tree2, color_map)

    legend_text = Text()
    legend_text.append("Legend: ", style="bold")
    legend_text.append("Green background ", style="on green")
    legend_text.append("= Only in left directory, ")
    legend_text.append("Red background ", style="on red")
    legend_text.append("= Only in right directory")

    if exclude_patterns or include_patterns:
        pattern_info = []
        if exclude_patterns:
            pattern_type = "Regex" if use_regex else "Glob"
            pattern_info.append(
                f"{pattern_type} exclusion patterns: {', '.join(str(p) for p in exclude_patterns)}"
            )
        if include_patterns:
            pattern_type = "Regex" if use_regex else "Glob"
            pattern_info.append(
                f"{pattern_type} inclusion patterns: {', '.join(str(p) for p in include_patterns)}"
            )

        if pattern_info:
            pattern_panel = Panel(
                "\n".join(pattern_info), title="Applied Patterns", border_style="blue"
            )
            console.print(pattern_panel)

    legend_panel = Panel(legend_text, border_style="dim")

    console.print(legend_panel)
    console.print(
        Columns(
            [
                Panel(
                    tree1,
                    title=f"Directory 1: {os.path.basename(dir1)}",
                    border_style="blue",
                ),
                Panel(
                    tree2,
                    title=f"Directory 2: {os.path.basename(dir2)}",
                    border_style="green",
                ),
            ],
            equal=True,
            expand=True,
        )
    )


def export_comparison(
    dir1: str,
    dir2: str,
    format_type: str,
    output_path: str,
    exclude_dirs: Optional[List[str]] = None,
    ignore_file: Optional[str] = None,
    exclude_extensions: Optional[Set[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    use_regex: bool = False,
) -> None:
    """
    Export directory comparison to various formats.

    Args:
        dir1: Path to the first directory
        dir2: Path to the second directory
        format_type: Export format ('txt' or 'html')
        output_path: Path where the export file will be saved
        exclude_dirs: List of directory names to exclude
        ignore_file: Name of ignore file (like .gitignore)
        exclude_extensions: Set of file extensions to exclude
        exclude_patterns: List of patterns to exclude
        include_patterns: List of patterns to include (overrides exclusions)
        use_regex: Whether to treat patterns as regex instead of glob patterns

    Raises:
        ValueError: If the format_type is not supported
    """
    if exclude_dirs is None:
        exclude_dirs = []
    if exclude_extensions is None:
        exclude_extensions = set()
    if exclude_patterns is None:
        exclude_patterns = []
    if include_patterns is None:
        include_patterns = []

    exclude_extensions = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in exclude_extensions
    }

    # Compile regex patterns if needed - make sure patterns are List[str]
    compiled_exclude = compile_regex_patterns(exclude_patterns, use_regex)
    compiled_include = compile_regex_patterns(include_patterns, use_regex)

    structure1, structure2, _ = compare_directory_structures(
        dir1,
        dir2,
        exclude_dirs,
        ignore_file,
        exclude_extensions,
        exclude_patterns=compiled_exclude,
        include_patterns=compiled_include,
    )

    comparison_data = {
        "dir1": {"path": dir1, "name": os.path.basename(dir1), "structure": structure1},
        "dir2": {"path": dir2, "name": os.path.basename(dir2), "structure": structure2},
        "metadata": {
            "exclude_patterns": [str(p) for p in exclude_patterns],
            "include_patterns": [str(p) for p in include_patterns],
            "pattern_type": "regex" if use_regex else "glob",
        },
    }

    if format_type == "txt":
        _export_comparison_to_txt(comparison_data, output_path)
    elif format_type == "html":
        _export_comparison_to_html(comparison_data, output_path)
    else:
        raise ValueError(f"Unsupported format: {format_type}")


def _export_comparison_to_txt(
    comparison_data: Dict[str, Any], output_path: str
) -> None:
    """Export comparison to text format with ASCII representation."""

    def _build_txt_tree(
        structure: Dict[str, Any], prefix: str = "", is_last: bool = True
    ) -> List[str]:
        lines = []
        items = list(sorted(structure.items()))

        for i, (name, content) in enumerate(items):
            if name == "_files":
                continue

            is_last_item = i == len(items) - 1 or (
                i == len(items) - 2 and "_files" in structure
            )

            if is_last_item:
                lines.append(f"{prefix}└── 📁 {name}")
                new_prefix = prefix + "    "
            else:
                lines.append(f"{prefix}├── 📁 {name}")
                new_prefix = prefix + "│   "

            if isinstance(content, dict):
                lines.extend(_build_txt_tree(content, new_prefix, is_last_item))

        if "_files" in structure:
            files = sort_files_by_type(structure["_files"])
            for i, file in enumerate(files):
                is_last_file = i == len(files) - 1
                if is_last_file:
                    lines.append(f"{prefix}└── 📄 {file}")
                else:
                    lines.append(f"{prefix}├── 📄 {file}")

        return lines

    dir1_name = comparison_data["dir1"]["name"]
    dir2_name = comparison_data["dir2"]["name"]
    dir1_structure = comparison_data["dir1"]["structure"]
    dir2_structure = comparison_data["dir2"]["structure"]

    dir1_lines = [f"📂 {dir1_name}"]
    dir1_lines.extend(_build_txt_tree(dir1_structure))

    dir2_lines = [f"📂 {dir2_name}"]
    dir2_lines.extend(_build_txt_tree(dir2_structure))

    max_width = max(len(line) for line in dir1_lines) + 4
    combined_lines = ["Directory Comparison:"]
    combined_lines.append("=" * 80)
    combined_lines.append(f"Left: {comparison_data['dir1']['path']}")
    combined_lines.append(f"Right: {comparison_data['dir2']['path']}")

    # Add pattern information if available
    metadata = comparison_data.get("metadata", {})
    if metadata.get("exclude_patterns") or metadata.get("include_patterns"):
        combined_lines.append("-" * 80)
        pattern_type = metadata.get("pattern_type", "glob")

        if metadata.get("exclude_patterns"):
            combined_lines.append(
                f"Exclude {pattern_type} patterns: {', '.join(metadata['exclude_patterns'])}"
            )

        if metadata.get("include_patterns"):
            combined_lines.append(
                f"Include {pattern_type} patterns: {', '.join(metadata['include_patterns'])}"
            )

    combined_lines.append("=" * 80)

    for i in range(max(len(dir1_lines), len(dir2_lines))):
        left = dir1_lines[i] if i < len(dir1_lines) else ""
        right = dir2_lines[i] if i < len(dir2_lines) else ""
        combined_lines.append(f"{left:<{max_width}} | {right}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(combined_lines))


def _export_comparison_to_html(
    comparison_data: Dict[str, Any], output_path: str
) -> None:
    """Export comparison to HTML format."""
    import html

    def _build_html_tree(
        structure: Dict[str, Any], include_differences: bool = False
    ) -> str:
        html_content = ["<ul>"]

        for name, content in sorted(structure.items()):
            if name != "_files":
                dir_class = ""
                if include_differences:
                    other_structure = (
                        comparison_data["dir2"]["structure"]
                        if structure == comparison_data["dir1"]["structure"]
                        else comparison_data["dir1"]["structure"]
                    )
                    if name not in other_structure:
                        dir_class = ' class="directory-unique"'

                html_content.append(
                    f'<li{dir_class}><span class="directory">📁 {html.escape(name)}</span>'
                )
                html_content.append(_build_html_tree(content, include_differences))
                html_content.append("</li>")

        if "_files" in structure:
            for file in sort_files_by_type(structure["_files"]):
                file_class = ""
                if include_differences:
                    other_structure = (
                        comparison_data["dir2"]["structure"]
                        if structure == comparison_data["dir1"]["structure"]
                        else comparison_data["dir1"]["structure"]
                    )
                    other_files = other_structure.get("_files", [])
                    if file not in other_files:
                        file_class = ' class="file-unique"'

                html_content.append(
                    f'<li{file_class}><span class="file">📄 {html.escape(file)}</span></li>'
                )

        html_content.append("</ul>")
        return "\n".join(html_content)

    dir1_name = html.escape(comparison_data["dir1"]["name"])
    dir2_name = html.escape(comparison_data["dir2"]["name"])
    dir1_path = html.escape(comparison_data["dir1"]["path"])
    dir2_path = html.escape(comparison_data["dir2"]["path"])

    # Pattern information
    pattern_info_html = ""
    metadata = comparison_data.get("metadata", {})
    if metadata.get("exclude_patterns") or metadata.get("include_patterns"):
        pattern_type = metadata.get("pattern_type", "glob").capitalize()
        pattern_items = []

        if metadata.get("exclude_patterns"):
            patterns = [html.escape(p) for p in metadata.get("exclude_patterns", [])]
            pattern_items.append(
                f"<dt>Exclude {pattern_type} Patterns:</dt><dd>{', '.join(patterns)}</dd>"
            )

        if metadata.get("include_patterns"):
            patterns = [html.escape(p) for p in metadata.get("include_patterns", [])]
            pattern_items.append(
                f"<dt>Include {pattern_type} Patterns:</dt><dd>{', '.join(patterns)}</dd>"
            )

        if pattern_items:
            pattern_info_html = f"""
            <div class="pattern-info">
                <h3>Applied Patterns</h3>
                <dl>
                    {''.join(pattern_items)}
                </dl>
            </div>
            """

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Directory Comparison - {dir1_name} vs {dir2_name}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
            }}
            .comparison-container {{
                display: flex;
                border: 1px solid #ccc;
            }}
            .directory-tree {{
                flex: 1;
                padding: 15px;
                overflow: auto;
                border-right: 1px solid #ccc;
            }}
            .directory-tree:last-child {{
                border-right: none;
            }}
            h1, h2 {{
                text-align: center;
            }}
            h3 {{
                margin-top: 0;
                padding: 10px;
                background-color: #f0f0f0;
                border-bottom: 1px solid #ccc;
            }}
            ul {{
                list-style-type: none;
                padding-left: 20px;
            }}
            .directory {{
                color: #2c3e50;
                font-weight: bold;
            }}
            .file {{
                color: #34495e;
            }}
            .file-unique {{
                background-color: #fcf3cf;
            }}
            .directory-unique {{
                background-color: #fcf3cf;
            }}
            .legend {{
                margin-bottom: 20px;
                padding: 10px;
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            .legend-item {{
                display: inline-block;
                margin-right: 20px;
            }}
            .legend-color {{
                display: inline-block;
                width: 15px;
                height: 15px;
                margin-right: 5px;
                vertical-align: middle;
            }}
            .legend-unique {{
                background-color: #fcf3cf;
            }}
            .pattern-info {{
                margin-bottom: 20px;
                padding: 10px;
                background-color: #f0f8ff;
                border: 1px solid #add8e6;
                border-radius: 4px;
            }}
            dt {{
                font-weight: bold;
                margin-top: 10px;
            }}
            dd {{
                margin-left: 20px;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>Directory Comparison</h1>
        {pattern_info_html}
        <div class="legend">
            <div class="legend-item">
                <span class="legend-color legend-unique"></span>
                <span>Unique to this directory</span>
            </div>
        </div>
        <div class="comparison-container">
            <div class="directory-tree">
                <h3>📂 {dir1_name}</h3>
                <p><em>Path: {dir1_path}</em></p>
                {_build_html_tree(comparison_data["dir1"]["structure"], True)}
            </div>
            <div class="directory-tree">
                <h3>📂 {dir2_name}</h3>
                <p><em>Path: {dir2_path}</em></p>
                {_build_html_tree(comparison_data["dir2"]["structure"], True)}
            </div>
        </div>
    </body>
    </html>
    """

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
